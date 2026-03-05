from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any
from urllib.parse import urlparse

import websocket

from hyperscribe.scribe.errors import ScribeTranscriptionError
from hyperscribe.scribe.models import TranscriptItem
from hyperscribe.scribe.nabla.auth import NablaAuth

logger = logging.getLogger(__name__)

_NABLA_API_VERSION = "2025-05-21"
_SPEECH_LOCALE = "ENGLISH_US"
_STREAM_ID = "stream1"
_MAX_IN_FLIGHT = 50
_END_TIMEOUT_SECONDS = 30


@dataclass
class NablaWsClient:
    auth: NablaAuth
    _ws: websocket.WebSocket | None = field(default=None, init=False, repr=False)
    _receiver_thread: Thread | None = field(default=None, init=False, repr=False)
    _items_queue: Queue[TranscriptItem] = field(default_factory=Queue, init=False, repr=False)
    _seq_id: int = field(default=0, init=False, repr=False)
    _ack_count: int = field(default=0, init=False, repr=False)
    _done: Event = field(default_factory=Event, init=False, repr=False)

    def connect(self) -> None:
        """Open WebSocket with subprotocol auth, send CONFIG, start receiver thread."""
        token = self.auth.get_access_token()
        ws_url = self._ws_url()
        try:
            self._ws = websocket.create_connection(
                ws_url,
                subprotocols=["transcribe-protocol", f"jwt-{token}"],
            )
        except websocket.WebSocketException as exc:
            raise ScribeTranscriptionError(f"Nabla WS connect failed: {exc}") from exc
        self._send_config()
        self._receiver_thread = Thread(target=self._receive_loop, daemon=True)
        self._receiver_thread.start()

    def send_audio_chunk(self, pcm_bytes: bytes) -> None:
        """Send base64-encoded PCM audio chunk. Blocks if max in-flight reached."""
        if self._ws is None:
            raise ScribeTranscriptionError("WebSocket not connected")
        while self._seq_id - self._ack_count >= _MAX_IN_FLIGHT:
            if self._done.wait(timeout=0.1):
                raise ScribeTranscriptionError("Session ended while waiting for flow control")
        self._seq_id += 1
        msg = json.dumps(
            {
                "type": "AUDIO_CHUNK",
                "payload": base64.b64encode(pcm_bytes).decode(),
                "stream_id": _STREAM_ID,
                "seq_id": self._seq_id,
            }
        )
        self._ws.send(msg)

    def drain_items(self) -> list[TranscriptItem]:
        """Non-blocking drain of received transcript items."""
        items: list[TranscriptItem] = []
        while True:
            try:
                items.append(self._items_queue.get_nowait())
            except Empty:
                break
        return items

    def end(self) -> None:
        """Send END message, wait for receiver thread to finish, close WebSocket."""
        if self._ws is None:
            return
        try:
            self._ws.send(json.dumps({"type": "END"}))
        except websocket.WebSocketException:
            logger.warning("Failed to send END message")
        self._done.wait(timeout=_END_TIMEOUT_SECONDS)
        try:
            self._ws.close()
        except websocket.WebSocketException:
            pass
        self._ws = None

    def _ws_url(self) -> str:
        parsed = urlparse(self.auth.base_url)
        return f"wss://{parsed.hostname}/v1/core/user/transcribe-ws?nabla-api-version={_NABLA_API_VERSION}"

    def _send_config(self) -> None:
        if self._ws is None:
            return
        config = {
            "type": "CONFIG",
            "encoding": "PCM_S16LE",
            "sample_rate": 16000,
            "speech_locales": [_SPEECH_LOCALE],
            "streams": [{"id": _STREAM_ID, "speaker_type": "unspecified"}],
            "enable_audio_chunk_ack": True,
        }
        self._ws.send(json.dumps(config))

    def _receive_loop(self) -> None:
        """Background thread: read WS messages, parse TRANSCRIPT_ITEM and ACK."""
        assert self._ws is not None
        try:
            while True:
                raw = self._ws.recv()
                if not raw:
                    break
                msg: dict[str, Any] = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type == "TRANSCRIPT_ITEM":
                    self._items_queue.put(self._parse_item(msg))
                elif msg_type == "AUDIO_CHUNK_ACK":
                    self._ack_count = int(msg.get("seq_id", self._ack_count))
                elif msg_type == "END":
                    break
        except Exception:
            logger.exception("Nabla WS receive loop error")
        finally:
            self._done.set()

    @staticmethod
    def _parse_item(msg: dict[str, Any]) -> TranscriptItem:
        return TranscriptItem(
            text=str(msg.get("text", "")),
            speaker=str(msg.get("speaker", "")),
            start_offset_ms=int(msg.get("start_offset_ms", 0)),
            end_offset_ms=int(msg.get("end_offset_ms", 0)),
            item_id=str(msg.get("id", "")),
            is_final=bool(msg.get("is_final", True)),
        )
