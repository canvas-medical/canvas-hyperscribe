import json
from unittest.mock import MagicMock, patch

import pytest
import websocket

from hyperscribe.scribe.backend import ScribeTranscriptionError, TranscriptItem
from hyperscribe.scribe.clients.nabla.auth import NablaAuth
from hyperscribe.scribe.clients.nabla.ws_client import NablaWsClient


def _make_ws_client() -> tuple[NablaWsClient, MagicMock]:
    auth = MagicMock(spec=NablaAuth)
    auth.base_url = "https://us.nabla.com/api/server"
    auth.get_access_token.return_value = "test-token"
    client = NablaWsClient(auth=auth)
    return client, auth


def test_ws_url():
    client, _ = _make_ws_client()
    url = client._ws_url()
    assert url == "wss://us.nabla.com/v1/core/user/transcribe-ws?nabla-api-version=2025-05-21"


def test_connect():
    client, auth = _make_ws_client()
    mock_ws = MagicMock()

    target = "hyperscribe.scribe.clients.nabla.ws_client.websocket.create_connection"
    with patch(target, return_value=mock_ws) as mock_create:
        client.connect()

    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args
    assert "wss://us.nabla.com" in call_kwargs.args[0]
    assert call_kwargs.kwargs["subprotocols"] == ["transcribe-protocol", "jwt-test-token"]

    # CONFIG message should have been sent
    config_call = mock_ws.send.call_args
    config = json.loads(config_call.args[0])
    assert config["type"] == "CONFIG"
    assert config["encoding"] == "PCM_S16LE"
    assert config["sample_rate"] == 16000
    assert config["speech_locales"] == ["ENGLISH_US"]
    assert config["enable_audio_chunk_ack"] is True


def test_connect_failure():
    client, _ = _make_ws_client()

    with patch(
        "hyperscribe.scribe.clients.nabla.ws_client.websocket.create_connection",
        side_effect=websocket.WebSocketException("connection refused"),
    ):
        with pytest.raises(ScribeTranscriptionError, match="Nabla WS connect failed"):
            client.connect()


def test_send_audio_chunk():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    client._ws = mock_ws

    client.send_audio_chunk(b"\x00\x01\x02\x03")

    mock_ws.send.assert_called_once()
    msg = json.loads(mock_ws.send.call_args.args[0])
    assert msg["type"] == "AUDIO_CHUNK"
    assert msg["stream_id"] == "stream1"
    assert msg["seq_id"] == 1
    assert msg["payload"] == "AAECAw=="  # base64 of b"\x00\x01\x02\x03"


def test_send_audio_chunk_increments_seq_id():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    client._ws = mock_ws

    client.send_audio_chunk(b"\x00")
    client.send_audio_chunk(b"\x01")

    calls = mock_ws.send.call_args_list
    msg1 = json.loads(calls[0].args[0])
    msg2 = json.loads(calls[1].args[0])
    assert msg1["seq_id"] == 1
    assert msg2["seq_id"] == 2


def test_send_audio_chunk_not_connected():
    client, _ = _make_ws_client()
    with pytest.raises(ScribeTranscriptionError, match="not connected"):
        client.send_audio_chunk(b"\x00")


def test_drain_items_empty():
    client, _ = _make_ws_client()
    assert client.drain_items() == []


def test_drain_items_with_items():
    client, _ = _make_ws_client()
    item1 = TranscriptItem(text="hello", speaker="patient", start_offset_ms=0, end_offset_ms=100, item_id="i1")
    item2 = TranscriptItem(text="hi", speaker="practitioner", start_offset_ms=100, end_offset_ms=200, item_id="i2")
    client._items_queue.put(item1)
    client._items_queue.put(item2)

    result = client.drain_items()
    assert result == [item1, item2]
    assert client.drain_items() == []


def test_end():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    client._ws = mock_ws
    client._done.set()

    client.end()

    msg = json.loads(mock_ws.send.call_args.args[0])
    assert msg["type"] == "END"
    mock_ws.close.assert_called_once()
    assert client._ws is None


def test_end_no_connection():
    client, _ = _make_ws_client()
    client.end()  # should not raise


def test_receive_loop_transcript_item():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    messages = [
        json.dumps(
            {
                "type": "TRANSCRIPT_ITEM",
                "id": "item-1",
                "text": "I have a headache",
                "speaker": "patient",
                "start_offset_ms": 0,
                "end_offset_ms": 2000,
                "is_final": True,
            }
        ),
        json.dumps({"type": "END"}),
    ]
    mock_ws.recv.side_effect = messages
    client._ws = mock_ws

    client._receive_loop()

    items = client.drain_items()
    assert len(items) == 1
    assert items[0].text == "I have a headache"
    assert items[0].speaker == "patient"
    assert items[0].item_id == "item-1"
    assert items[0].is_final is True
    assert items[0].start_offset_ms == 0
    assert items[0].end_offset_ms == 2000
    assert client._done.is_set()


def test_receive_loop_audio_chunk_ack():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    messages = [
        json.dumps({"type": "AUDIO_CHUNK_ACK", "seq_id": 5}),
        json.dumps({"type": "END"}),
    ]
    mock_ws.recv.side_effect = messages
    client._ws = mock_ws

    client._receive_loop()

    assert client._ack_count == 5


def test_receive_loop_partial_and_final():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    messages = [
        json.dumps(
            {
                "type": "TRANSCRIPT_ITEM",
                "id": "item-1",
                "text": "I have",
                "speaker": "patient",
                "start_offset_ms": 0,
                "end_offset_ms": 500,
                "is_final": False,
            }
        ),
        json.dumps(
            {
                "type": "TRANSCRIPT_ITEM",
                "id": "item-1",
                "text": "I have a headache",
                "speaker": "patient",
                "start_offset_ms": 0,
                "end_offset_ms": 2000,
                "is_final": True,
            }
        ),
        json.dumps({"type": "END"}),
    ]
    mock_ws.recv.side_effect = messages
    client._ws = mock_ws

    client._receive_loop()

    items = client.drain_items()
    assert len(items) == 2
    assert items[0].is_final is False
    assert items[0].text == "I have"
    assert items[1].is_final is True
    assert items[1].text == "I have a headache"


def test_receive_loop_empty_recv_breaks():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    mock_ws.recv.return_value = ""
    client._ws = mock_ws

    client._receive_loop()

    assert client._done.is_set()


def test_receive_loop_exception_sets_done():
    client, _ = _make_ws_client()
    mock_ws = MagicMock()
    mock_ws.recv.side_effect = websocket.WebSocketConnectionClosedException("closed")
    client._ws = mock_ws

    client._receive_loop()

    assert client._done.is_set()


def test_parse_item():
    msg: dict[str, object] = {
        "id": "item-1",
        "text": "hello",
        "speaker": "patient",
        "start_offset_ms": 100,
        "end_offset_ms": 500,
        "is_final": False,
    }
    result = NablaWsClient._parse_item(msg)
    assert result == TranscriptItem(
        text="hello",
        speaker="patient",
        start_offset_ms=100,
        end_offset_ms=500,
        item_id="item-1",
        is_final=False,
    )


def test_parse_item_defaults():
    msg: dict[str, object] = {"type": "TRANSCRIPT_ITEM"}
    result = NablaWsClient._parse_item(msg)
    assert result.text == ""
    assert result.speaker == ""
    assert result.start_offset_ms == 0
    assert result.end_offset_ms == 0
    assert result.item_id == ""
    assert result.is_final is True
