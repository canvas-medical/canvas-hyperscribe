"""Tests for transcript validation and timestamp anomaly detection."""

import pytest

from hyperscribe.libraries.transcript_validator import (
    TimestampAnomalyDetector,
    TranscriptValidationError,
)


class TestTimestampAnomalyDetector:
    """Test suite for TimestampAnomalyDetector class."""

    def test_valid_words_pass_validation(self):
        """Test that valid word-level timestamps pass validation."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        words = [
            {"text": "Hello", "start": 0.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": "world", "start": 0.5, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "test", "start": 1.0, "end": 1.5, "type": "word", "speaker_id": "speaker_0"},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)

        assert is_valid is True
        assert error_msg is None
        assert anomaly_details is None

    def test_empty_words_list_passes(self):
        """Test that empty words list passes validation."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        is_valid, error_msg, anomaly_details = detector.validate_elevenlabs_words([], raise_on_anomaly=False)

        assert is_valid is True
        assert error_msg is None
        assert anomaly_details is None

    def test_spacing_entries_ignored(self):
        """Test that spacing entries don't affect validation."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        words = [
            {"text": "Hello", "start": 0.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": " ", "start": 0.5, "end": 0.5, "type": "spacing", "speaker_id": "speaker_0"},
            {"text": "world", "start": 0.5, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)

        assert is_valid is True

    def test_identical_timestamps_detected_real_case(self):
        """Test detection of identical timestamps from real feedback case."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        # Simulating the real feedback case where ElevenLabs hallucinated
        # "and breast cancer removals, and she has a history of diabetes mellitus"
        # All hallucinated words have timestamp 5.759
        words = [
            {"text": "Her", "start": 3.559, "end": 3.719, "type": "word", "speaker_id": "speaker_0"},
            {"text": "past", "start": 3.759, "end": 3.959, "type": "word", "speaker_id": "speaker_0"},
            {"text": "surgical", "start": 4.0, "end": 4.539, "type": "word", "speaker_id": "speaker_0"},
            {"text": "history", "start": 4.579, "end": 5.059, "type": "word", "speaker_id": "speaker_0"},
            {"text": "includes", "start": 5.119, "end": 5.579, "type": "word", "speaker_id": "speaker_0"},
            {"text": "colon", "start": 5.639, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            # Hallucinated words all have the same timestamp
            {"text": "and", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "breast", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "cancer", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "removals", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "and", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "she", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "has", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "a", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "history", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "of", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "diabetes", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
            {"text": "mellitus", "start": 5.759, "end": 5.759, "type": "word", "speaker_id": "speaker_0"},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)

        assert is_valid is False
        assert error_msg is not None
        assert "Timestamp anomaly detected" in error_msg
        assert "consecutive words with identical timestamp" in error_msg
        assert anomaly_details is not None
        assert anomaly_details["type"] == "identical_timestamps"
        assert anomaly_details["consecutive_count"] >= 3
        assert "and breast cancer" in anomaly_details["hallucinated_text"]

    def test_identical_timestamps_raises_exception(self):
        """Test that identical timestamps raise exception when raise_on_anomaly=True."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        words = [
            {"text": "word1", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word2", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word3", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
        ]

        with pytest.raises(TranscriptValidationError) as exc_info:
            detector.validate_elevenlabs_words(words, raise_on_anomaly=True)

        assert "Timestamp anomaly detected" in str(exc_info.value)

    def test_two_identical_timestamps_passes(self):
        """Test that only 2 consecutive identical timestamps passes (below threshold)."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        words = [
            {"text": "word1", "start": 0.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word2", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word3", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word4", "start": 2.0, "end": 2.5, "type": "word", "speaker_id": "speaker_0"},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)

        assert is_valid is True

    def test_negative_timestamps_detected(self):
        """Test that negative timestamps are detected."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        words = [
            {"text": "word1", "start": -1.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)

        assert is_valid is False
        assert "Negative timestamp" in error_msg
        assert anomaly_details["type"] == "negative_timestamp"

    def test_invalid_range_detected(self):
        """Test that start > end is detected."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=3)

        words = [
            {"text": "word1", "start": 2.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)

        assert is_valid is False
        assert "Invalid timestamp range" in error_msg
        assert anomaly_details["type"] == "invalid_range"

    def test_custom_threshold(self):
        """Test that custom threshold for consecutive identical timestamps works."""
        detector = TimestampAnomalyDetector(min_consecutive_identical=5)

        # 4 consecutive identical - should pass with threshold of 5
        words = [
            {"text": "word1", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word2", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word3", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "word4", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
        ]

        is_valid, _, _ = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)
        assert is_valid is True

        # 5 consecutive identical - should fail
        words.append({"text": "word5", "start": 1.0, "end": 1.0, "type": "word", "speaker_id": "speaker_0"})

        is_valid, _, _ = detector.validate_elevenlabs_words(words, raise_on_anomaly=False)
        assert is_valid is False


class TestTranscriptSegmentValidation:
    """Test suite for transcript segment validation."""

    def test_valid_segments_pass(self):
        """Test that valid transcript segments pass validation."""
        detector = TimestampAnomalyDetector()

        segments = [
            {"speaker": "Clinician", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "Patient", "text": "Hi", "start": 1.0, "end": 2.0},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_transcript_segments(segments, raise_on_anomaly=False)

        assert is_valid is True
        assert error_msg is None
        assert anomaly_details is None

    def test_overlapping_segments_detected(self):
        """Test that overlapping segments are detected."""
        detector = TimestampAnomalyDetector()

        segments = [
            {"speaker": "Clinician", "text": "Hello", "start": 0.0, "end": 2.0},
            {"speaker": "Patient", "text": "Hi", "start": 1.5, "end": 3.0},  # Overlaps with previous
        ]

        is_valid, error_msg, anomaly_details = detector.validate_transcript_segments(segments, raise_on_anomaly=False)

        assert is_valid is False
        assert "Overlapping timestamps" in error_msg
        assert anomaly_details["type"] == "overlapping_segments"

    def test_segment_negative_timestamp(self):
        """Test that negative timestamps in segments are detected."""
        detector = TimestampAnomalyDetector()

        segments = [
            {"speaker": "Clinician", "text": "Hello", "start": -1.0, "end": 1.0},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_transcript_segments(segments, raise_on_anomaly=False)

        assert is_valid is False
        assert "Negative timestamp" in error_msg

    def test_segment_invalid_range(self):
        """Test that invalid ranges in segments are detected."""
        detector = TimestampAnomalyDetector()

        segments = [
            {"speaker": "Clinician", "text": "Hello", "start": 2.0, "end": 1.0},
        ]

        is_valid, error_msg, anomaly_details = detector.validate_transcript_segments(segments, raise_on_anomaly=False)

        assert is_valid is False
        assert "Invalid timestamp range" in error_msg
