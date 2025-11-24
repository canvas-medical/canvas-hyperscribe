"""Transcript validation utilities to detect anomalies in transcription results."""

from typing import Any, Dict, List, Optional, Tuple


class TranscriptValidationError(Exception):
    """Exception raised when transcript validation fails."""

    pass


class TimestampAnomalyDetector:
    """Detects timestamp anomalies in transcription results that indicate hallucinated content."""

    def __init__(
        self,
        min_consecutive_identical: int = 3,
        min_word_duration: float = 0.001,
    ):
        """
        Initialize the timestamp anomaly detector.

        Args:
            min_consecutive_identical: Minimum number of consecutive words with identical
                timestamps to trigger an anomaly. Default is 3.
            min_word_duration: Minimum expected duration for a word in seconds. Default is 0.001.
        """
        self.min_consecutive_identical = min_consecutive_identical
        self.min_word_duration = min_word_duration

    def validate_elevenlabs_words(
        self, words: List[Dict[str, Any]], raise_on_anomaly: bool = True
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate word-level timestamps from ElevenLabs transcription results.

        Detects anomalies that indicate hallucinated content, such as:
        - Multiple consecutive words with identical timestamps
        - Invalid timestamp ranges (start >= end)
        - Negative timestamps

        Args:
            words: List of word dictionaries from ElevenLabs API response.
                Each dict should have 'text', 'start', 'end', 'type', 'speaker_id' keys.
            raise_on_anomaly: If True, raise TranscriptValidationError on anomaly.
                If False, return validation results without raising.

        Returns:
            Tuple of (is_valid, error_message, anomaly_details)
            - is_valid: True if no anomalies detected
            - error_message: Description of the anomaly if found, None otherwise
            - anomaly_details: Dict with details about the anomaly if found, None otherwise

        Raises:
            TranscriptValidationError: If raise_on_anomaly=True and an anomaly is detected.
        """
        if not words:
            return True, None, None

        # Track consecutive words with identical timestamps
        consecutive_identical: List[Dict[str, Any]] = []
        prev_timestamp = None

        # Process only 'word' type entries (skip 'spacing' and 'audio_event')
        word_entries = [w for w in words if w.get("type") == "word"]

        for i, word in enumerate(word_entries):
            start = word.get("start")
            end = word.get("end")
            text = word.get("text", "")

            # Validate timestamp sanity
            if start is None or end is None:
                continue

            if start < 0 or end < 0:
                error_msg = f"Negative timestamp detected at word '{text}': start={start}, end={end}"
                anomaly_details = {
                    "type": "negative_timestamp",
                    "word_index": i,
                    "word_text": text,
                    "start": start,
                    "end": end,
                }
                if raise_on_anomaly:
                    raise TranscriptValidationError(error_msg)
                return False, error_msg, anomaly_details

            if start > end:
                error_msg = f"Invalid timestamp range at word '{text}': start={start} > end={end}"
                anomaly_details = {
                    "type": "invalid_range",
                    "word_index": i,
                    "word_text": text,
                    "start": start,
                    "end": end,
                }
                if raise_on_anomaly:
                    raise TranscriptValidationError(error_msg)
                return False, error_msg, anomaly_details

            # Check for identical timestamps (hallucination indicator)
            current_timestamp = (start, end)

            if current_timestamp == prev_timestamp:
                # Same timestamp as previous word
                if not consecutive_identical:
                    # Start new sequence
                    consecutive_identical = [word_entries[i - 1], word]
                else:
                    # Continue sequence
                    consecutive_identical.append(word)

                # Check if we've hit the threshold
                if len(consecutive_identical) >= self.min_consecutive_identical:
                    hallucinated_text = " ".join([w.get("text", "") for w in consecutive_identical])
                    error_msg = (
                        f"Timestamp anomaly detected: {len(consecutive_identical)} consecutive "
                        f"words with identical timestamp ({start}, {end}). "
                        f"This indicates hallucinated content. Text: '{hallucinated_text}'"
                    )
                    anomaly_details = {
                        "type": "identical_timestamps",
                        "consecutive_count": len(consecutive_identical),
                        "timestamp": {"start": start, "end": end},
                        "hallucinated_text": hallucinated_text,
                        "word_indices": list(range(i - len(consecutive_identical) + 1, i + 1)),
                        "words": consecutive_identical,
                    }
                    if raise_on_anomaly:
                        raise TranscriptValidationError(error_msg)
                    return False, error_msg, anomaly_details
            else:
                # Different timestamp, reset consecutive counter
                consecutive_identical = []

            prev_timestamp = current_timestamp

        # No anomalies detected
        return True, None, None

    def validate_transcript_segments(
        self, segments: List[Dict[str, Any]], raise_on_anomaly: bool = True
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate speaker-level transcript segments for timestamp anomalies.

        Args:
            segments: List of transcript segments, each with 'speaker', 'text', 'start', 'end'.
            raise_on_anomaly: If True, raise TranscriptValidationError on anomaly.

        Returns:
            Tuple of (is_valid, error_message, anomaly_details)

        Raises:
            TranscriptValidationError: If raise_on_anomaly=True and an anomaly is detected.
        """
        if not segments:
            return True, None, None

        prev_segment = None

        for i, segment in enumerate(segments):
            start = segment.get("start")
            end = segment.get("end")
            text = segment.get("text", "")
            speaker = segment.get("speaker", "")

            # Validate timestamp sanity
            if start is None or end is None:
                continue

            if start < 0 or end < 0:
                error_msg = f"Negative timestamp at segment {i} ({speaker}): start={start}, end={end}"
                anomaly_details = {
                    "type": "negative_timestamp",
                    "segment_index": i,
                    "speaker": speaker,
                    "start": start,
                    "end": end,
                }
                if raise_on_anomaly:
                    raise TranscriptValidationError(error_msg)
                return False, error_msg, anomaly_details

            if start > end:
                error_msg = f"Invalid timestamp range at segment {i} ({speaker}): start={start} > end={end}"
                anomaly_details = {
                    "type": "invalid_range",
                    "segment_index": i,
                    "speaker": speaker,
                    "start": start,
                    "end": end,
                }
                if raise_on_anomaly:
                    raise TranscriptValidationError(error_msg)
                return False, error_msg, anomaly_details

            # Check for temporal consistency with previous segment
            if prev_segment is not None:
                prev_end = prev_segment.get("end")
                if prev_end is not None and start < prev_end:
                    error_msg = (
                        f"Overlapping timestamps at segment {i}: current start={start} < previous end={prev_end}"
                    )
                    anomaly_details = {
                        "type": "overlapping_segments",
                        "segment_index": i,
                        "current_speaker": speaker,
                        "previous_speaker": prev_segment.get("speaker", ""),
                        "current_start": start,
                        "previous_end": prev_end,
                    }
                    if raise_on_anomaly:
                        raise TranscriptValidationError(error_msg)
                    return False, error_msg, anomaly_details

            prev_segment = segment

        # No anomalies detected
        return True, None, None
