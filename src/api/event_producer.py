"""
Event Producer — Send rating events to Redpanda

When a user submits a rating via POST /rate, this service publishes the
event to the `user-events` Redpanda topic so downstream consumers (feature
pipelines, analytics) can process it in real time.

Gracefully degrades if Redpanda is not running — logs a warning and continues.

Environment variables:
    REDPANDA_BOOTSTRAP_SERVERS: Redpanda broker address (default: localhost:9092)
    REDPANDA_TOPIC: Topic name for user events (default: user-events)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from typing import Any

REDPANDA_TOPIC = os.getenv("REDPANDA_TOPIC", "user-events")
REDPANDA_BOOTSTRAP_SERVERS = os.getenv("REDPANDA_BOOTSTRAP_SERVERS", "localhost:9092")


class EventProducer:
    """
    Publishes user interaction events to Redpanda.

    Usage:
        producer = EventProducer()
        producer.initialize()
        producer.send_rating(user_id=1, movie_id=42, rating=4.5)
    """

    def __init__(self) -> None:
        self._producer: Any = None
        self._connected: bool = False

    def initialize(self) -> None:
        """Attempt to connect to Redpanda. Fail gracefully if unavailable."""
        try:
            import warnings
            warnings.filterwarnings("ignore", message="value_serializer does not implement")
            from kafka import KafkaProducer

            self._producer = KafkaProducer(
                bootstrap_servers=REDPANDA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: v.encode("utf-8"),
                acks=1,
                retries=3,
                max_block_ms=5_000,
            )
            # Quick connectivity check
            self._producer.metrics()  # raises if broker is unreachable
            self._connected = True
            print(f"[EventProducer] Connected to Redpanda at {REDPANDA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            print(f"[EventProducer] Redpanda unavailable ({e}); events will be logged only")
            self._connected = False

    def send_rating(
        self,
        user_id: int,
        movie_id: int,
        rating: float,
        timestamp: int | None = None,
    ) -> bool:
        """
        Publish a rating event to the user-events topic.

        Args:
            user_id: The user who rated.
            movie_id: The movie that was rated.
            rating: The rating value (0.5–5.0).
            timestamp: Unix timestamp. Defaults to now.

        Returns:
            True if the event was published (or logged), False on failure.
        """
        ts = timestamp or int(datetime.now(tz=UTC).timestamp())
        event = {
            "event_type": "rating",
            "user_id": user_id,
            "movie_id": movie_id,
            "rating": rating,
            "timestamp": ts,
            "datetime": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
        }

        if self._connected and self._producer is not None:
            try:
                future = self._producer.send(REDPANDA_TOPIC, json.dumps(event))
                _ = future.get(timeout=5)
                return True
            except Exception as e:
                print(f"[EventProducer] Failed to send event: {e}")
                return False
        else:
            # Log the event as a fallback
            print(f"[EventProducer] (logged) {json.dumps(event)}")
            return True

    def close(self) -> None:
        """Flush and close the producer connection."""
        if self._producer is not None:
            self._producer.flush()
            self._producer.close()

    @property
    def is_connected(self) -> bool:
        return self._connected