# RecoStack — Kafka / Redpanda Event Streaming

## Image

We use the **official Redpanda** image directly:

```
docker.redpanda.com/redpandadata/redpanda:latest
```

Redpanda is a Kafka-compatible event streaming platform written in C++. It replaces
Apache Kafka with zero ZooKeeper dependency, lower latency, and a single binary.

## Why Not Confluent / Bitnami / etc.?

- **Redpanda is Kafka API–compatible** — any Kafka client (python, Java, Go) works
  without code changes.
- **Single binary** — no ZooKeeper, no schema registry (unless you want one). This
  drastically simplifies the Docker setup.
- **Developer mode** — we run with `--developer-mode` which disables production
  safeguards (data durability, fsync) — ideal for local dev, *not* for production.

## Files

| File | Purpose |
|------|---------|
| `init-topics.sh` | Creates the `user-events` topic via `rpk` |
| This README | Notes on the image choice |

## Usage

See the standalone `docker run` command in Phase 4 of the main build plan.
Full Docker Compose orchestration comes in Phase 11.