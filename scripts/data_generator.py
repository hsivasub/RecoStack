"""
data_generator.py — Phase 5: Simulated Live Event Stream

Reads historical MovieLens ratings from data/raw/ml-latest-small/ratings.csv
and replays them as JSON events to the "user-events" Redpanda topic at a
configurable rate, simulating a live stream of user activity.

Usage:
    # Stream at 10 events per second (default)
    python scripts/data_generator.py

    # Stream at 100 events per second
    python scripts/data_generator.py --rate 100

    # Stream at 1 event per second and stop after 50
    python scripts/data_generator.py --rate 1 --max-events 50

    # Stream in real-time (events spaced by original timestamps)
    python scripts/data_generator.py --rate realtime
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "ml-latest-small"
RATINGS_PATH = DATA_DIR / "ratings.csv"

REDPANDA_TOPIC = "user-events"
REDPANDA_BOOTSTRAP_SERVERS = "localhost:9092"


# ---------------------------------------------------------------------------
# Event schema
# ---------------------------------------------------------------------------
def build_event(row: dict) -> str:
    """Convert a ratings.csv row dict into a JSON event string."""
    event = {
        "event_type": "rating",
        "user_id": int(row["userId"]),
        "movie_id": int(row["movieId"]),
        "rating": float(row["rating"]),
        "timestamp": int(row["timestamp"]),
        "datetime": datetime.fromtimestamp(int(row["timestamp"]), tz=UTC).isoformat(),
    }
    return json.dumps(event)


# ---------------------------------------------------------------------------
# Rate helpers
# ---------------------------------------------------------------------------
def parse_rate(value: str) -> tuple[str, float | None]:
    """Return (mode, events_per_second) where mode is 'fixed' or 'realtime'.

    If mode is 'fixed' the caller should sleep (1/eps) seconds between events.
    If mode is 'realtime' the caller should sleep according to inter-event
    deltas from the original timestamps.
    """
    if value.lower() == "realtime":
        return "realtime", None

    eps = float(value)
    if eps <= 0:
        raise argparse.ArgumentTypeError("Rate must be > 0 or 'realtime'")
    return "fixed", eps


# ---------------------------------------------------------------------------
# Producer — lazy import so the module is usable without kafka-python installed
# ---------------------------------------------------------------------------
def create_producer(bootstrap_servers: str):
    """Return a Kafka producer connected to *bootstrap_servers*."""
    import warnings
    warnings.filterwarnings("ignore", message="value_serializer does not implement")
    from kafka import KafkaProducer

    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: v.encode("utf-8"),
        acks=1,                  # leader acknowledgement only (fast enough for replay)
        retries=3,
        max_block_ms=60_000,     # generous timeout for first metadata fetch
        metadata_max_age_ms=30_000,
    )


def wait_for_metadata(producer, topic: str, timeout: float = 25.0) -> bool:
    """Block until the producer has metadata for *topic* (i.e. broker is reachable).

    Returns True if metadata arrived, False on timeout.
    """
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            partitions = producer.partitions_for(topic)
            if partitions:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Main replay loop
# ---------------------------------------------------------------------------
def replay(
    ratings: pd.DataFrame,
    *,
    rate_mode: str,
    eps: float | None,
    max_events: int | None,
    verbose: bool = True,
) -> int:
    """Replay *ratings* to the Redpanda topic.

    Returns the number of events actually produced.
    """
    if verbose:
        print(f"Connecting to Redpanda at {REDPANDA_BOOTSTRAP_SERVERS} ...", flush=True)

    try:
        producer = create_producer(REDPANDA_BOOTSTRAP_SERVERS)
    except Exception:
        print(
            "ERROR: Could not connect to Redpanda. Is it running?\n"
            f"       Expected at {REDPANDA_BOOTSTRAP_SERVERS}\n"
            "       Start it with:  docker run -d --name redpanda -p 9092:9092 "
            "-p 9644:9644 docker.redpanda.com/redpandadata/redpanda:latest "
            "redpanda start --mode dev-container --check=false",
            file=sys.stderr,
        )
        return 0

    # Wait until the producer has topic metadata (broker reachable)
    if not wait_for_metadata(producer, REDPANDA_TOPIC):
        print(
            f"ERROR: Timed out waiting for topic '{REDPANDA_TOPIC}' metadata.\n"
            f"       Check that the topic exists: "
            f"docker exec redpanda rpk topic list",
            file=sys.stderr,
        )
        producer.close()
        return 0

    # Sort by timestamp so we replay in chronological order
    ratings_sorted = ratings.sort_values("timestamp").reset_index(drop=True)

    total = len(ratings_sorted)
    if max_events:
        ratings_sorted = ratings_sorted.head(max_events)
        total = max_events

    if rate_mode == "realtime":
        # Use the first event's timestamp as the reference
        first_ts = int(ratings_sorted.iloc[0]["timestamp"])
        start_wall = time.time()

    produced = 0
    errors = 0
    start_time = time.time()

    print(f"Starting replay of {total:,} events at rate_mode='{rate_mode}'", flush=True)

    for idx, (_, row) in enumerate(ratings_sorted.iterrows()):
        # ----- Rate limiting -----
        if rate_mode == "fixed" and eps:
            time.sleep(1.0 / eps)
        elif rate_mode == "realtime":
            current_ts = int(row["timestamp"])
            elapsed_sim = current_ts - first_ts
            elapsed_wall = time.time() - start_wall
            sleep_for = elapsed_sim - elapsed_wall
            if sleep_for > 0:
                time.sleep(sleep_for)

        # ----- Produce -----
        event_str = build_event(row)
        try:
            future = producer.send(REDPANDA_TOPIC, event_str)
            future.get(timeout=30)  # block; first metadata fetch can be slow
            produced += 1
        except Exception as exc:
            errors += 1
            if errors <= 3:
                print(f"  Error producing event: {exc}", file=sys.stderr)
            elif errors == 4:
                print("  (suppressing further production errors)", file=sys.stderr)
            # If first few fail, break early
            if errors == 5:
                print("  Too many errors — aborting.", file=sys.stderr)
                break

        # ----- Progress -----
        if verbose and (idx + 1) % 5_000 == 0:
            elapsed = time.time() - start_time
            effective_rate = (idx + 1) / elapsed if elapsed > 0 else 0
            print(
                f"  [{idx+1:>6,}/{total:,}] "
                f"{effective_rate:.0f} evt/s  "
                f"{elapsed:.1f}s elapsed",
                flush=True,
            )

    # ----- Wrap-up -----
    producer.flush()
    producer.close()
    elapsed = time.time() - start_time
    effective_rate = produced / elapsed if elapsed > 0 else 0

    print("-" * 60, flush=True)
    print(f"  Produced:    {produced:>6,} events", flush=True)
    print(f"  Errors:      {errors:>6,}", flush=True)
    print(f"  Duration:    {elapsed:>6.1f}s", flush=True)
    print(f"  Avg rate:    {effective_rate:>6.0f} evt/s", flush=True)
    print("-" * 60, flush=True)

    return produced


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay historical MovieLens ratings as a live Redpanda event stream.",
    )
    parser.add_argument(
        "--rate",
        type=str,
        default="10",
        help="Events per second (integer > 0) or 'realtime' for original pacing (default: 10)",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Stop after producing this many events (default: all 100K)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-5K progress lines",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not RATINGS_PATH.exists():
        print(
            f"ERROR: Ratings file not found at {RATINGS_PATH}\n"
            "Run scripts/download_data.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    rate_mode, eps = parse_rate(args.rate)

    print(f"Loading ratings from {RATINGS_PATH} ...", flush=True)
    ratings = pd.read_csv(RATINGS_PATH)
    print(f"Loaded {len(ratings):,} ratings (users={ratings['userId'].nunique()}, "
          f"movies={ratings['movieId'].nunique()})", flush=True)

    produced = replay(ratings, rate_mode=rate_mode, eps=eps,
                       max_events=args.max_events, verbose=not args.quiet)

    if produced == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()