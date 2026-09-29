"""
Unit tests — Event Producer (src/api/event_producer.py)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.api.event_producer import EventProducer


class TestEventProducer:
    def test_initialize_fallback_when_redpanda_unavailable(self):
        """Should gracefully handle Redpanda being unreachable."""
        producer = EventProducer()
        producer.initialize()
        assert producer._connected is False
        assert producer._producer is None

    def test_send_rating_logs_when_disconnected(self, capsys):
        """When disconnected, send_rating should log the event and return True."""
        producer = EventProducer()
        producer._connected = False

        result = producer.send_rating(user_id=1, movie_id=42, rating=4.5)
        assert result is True

        captured = capsys.readouterr()
        assert "logged" in captured.out
        assert "42" in captured.out

    def test_send_rating_with_timestamp(self, capsys):
        """Should use the provided timestamp."""
        producer = EventProducer()
        producer._connected = False

        producer.send_rating(user_id=1, movie_id=42, rating=4.5, timestamp=1_000_000)
        captured = capsys.readouterr()
        assert '"timestamp": 1000000' in captured.out

    def test_send_rating_event_structure(self, capsys):
        """The logged JSON should match the expected event schema."""
        producer = EventProducer()
        producer._connected = False

        producer.send_rating(user_id=1, movie_id=42, rating=4.5, timestamp=1_000_000)
        captured = capsys.readouterr()
        # Extract the JSON part from the log line
        log_line = captured.out.strip()
        json_str = log_line.split("{", 1)[1].rsplit("}", 1)[0]
        event = json.loads("{" + json_str + "}")

        assert event["event_type"] == "rating"
        assert event["user_id"] == 1
        assert event["movie_id"] == 42
        assert event["rating"] == 4.5
        assert event["timestamp"] == 1_000_000
        assert "datetime" in event

    def test_close_when_no_producer(self):
        """close() should not raise when producer was never initialized."""
        producer = EventProducer()
        producer.close()  # should not raise

    def test_is_connected_property(self):
        producer = EventProducer()
        assert producer.is_connected is False

    @patch("src.api.event_producer.KafkaProducer")
    def test_initialize_success(self, mock_kafka):
        """When KafkaProducer connects, _connected should be True."""
        mock_instance = MagicMock()
        mock_kafka.return_value = mock_instance

        producer = EventProducer()
        producer.initialize()
        assert producer._connected is True
        assert producer._producer is not None

    @patch("src.api.event_producer.KafkaProducer")
    def test_send_rating_publishes(self, mock_kafka, capsys):
        """When connected, send_rating should call producer.send."""
        mock_instance = MagicMock()
        mock_kafka.return_value = mock_instance
        mock_instance.metrics.return_value = {}

        producer = EventProducer()
        producer.initialize()

        # Mock the send future
        mock_future = MagicMock()
        mock_instance.send.return_value = mock_future

        result = producer.send_rating(user_id=1, movie_id=42, rating=4.5)
        assert result is True
        mock_instance.send.assert_called_once()