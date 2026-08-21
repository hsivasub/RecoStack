# RecoStack Build Progress

## Phase 1 — Project Scaffolding & Infrastructure Foundation
**Date**: 2026-07-27

### Files Created/Changed
```
RECOSTACK/
├── .gitignore
├── .venv/                          # Python virtual environment (Python 3.14)
├── pyproject.toml                   # Project metadata & dependencies
├── README.md                        # Project overview & quick start
├── PROGRESS.md                      # This file
├── config/{feast,grafana,mlflow,prometheus,redpanda}/
├── data/{features,model-artifacts}/
├── docker/{feast,grafana,kafka,mlflow,prometheus}/
├── docs/{api,architecture}/
├── scripts/
├── src/{api,feast,recommenders}/__init__.py
├── tests/{integration,unit}/__init__.py
```

### Summary
Established the complete directory skeleton for RecoStack, Python packaging via `pyproject.toml` with all core dependencies (numpy, pandas, scikit-learn, lightgbm, feast, mlflow, fastapi, redis, etc.), virtual environment, `.gitignore`, and `README.md`. All source packages have `__init__.py` files. The project structure now supports the phased addition of Feast feature definitions, ML model code, FastAPI endpoints, Docker services, and test suites.

### Note
- Python 3.14 is installed on this system rather than 3.12. The project's `requires-python = ">=3.12"` accommodates this. Dependencies were selected for Python 3.12+ compatibility.
- The `.gitignore` intentionally ignores `data/raw/` (dataset downloads) and `data/features/` (generated feature data); a `.gitkeep` pattern is included so the directories exist in the repo.
- No Docker Compose file yet — that comes in a later phase when we need to actually run services.

### Manual Steps Required
None. This phase is entirely automated and ready for Phase 2.

---

## Phase 2 — Data Acquisition & Exploration
**Date**: 2026-07-27

### Files Created
- `scripts/download_data.py` — Downloads MovieLens ml-latest-small (100K ratings, 610 users, 9,724 movies) from GroupLens and extracts to `data/raw/ml-latest-small/`
- `scripts/explore_data.py` — Loads `ratings.csv` and `movies.csv` with pandas; prints row counts, date range, unique users/items, rating distribution, sparsity, and genre breakdown

### Data Summary
| Metric | Value |
|---|---|
| Ratings | 100,836 |
| Users | 610 |
| Movies | 9,724 |
| Date range | 1996-03-29 → 2018-09-24 |
| Matrix size | 610 × 9,724 = 5,931,640 cells |
| Filled cells | 100,836 |
| **Sparsity** | **98.30%** (only 1.70% filled) |
| Mean rating | 3.50 / 5.0 |
| Median rating | 3.5 / 5.0 |
| Users with < 20 ratings | 0 (min is 20) |
| Movies with < 5 ratings | ~70% (median 3 ratings/movie) |
| Unique genres | 20 (Drama & Comedy dominate) |

### Key Takeaways
- **Extreme sparsity (98.3%)** is typical for recommendation problems — most users have rated only a tiny fraction of all movies. This drives the need for collaborative filtering or hybrid approaches in candidate generation (Phase 5+).
- **Long-tail item distribution**: median movie has only 3 ratings, while the most popular has 329. Cold-start items (few interactions) will need content-based signals.
- **Rating distribution is left-skewed** toward positive ratings (mean 3.5), which is standard for explicit feedback datasets.
### Manual Steps Required
None.

---

## Phase 3 — Architecture Documentation
**Date**: 2026-07-27

### Files Created
- `docs/architecture/ARCHITECTURE.md` — Full system architecture document

### Document Contents
| Section | Description |
|---|---|
| Overview | High-level principles (two-stage, feature store, streaming-first, local-only) |
| Component Responsibility Table | 9 components (Redpanda, Feast, Redis, Training Pipeline, MLflow, FastAPI, Prometheus, Grafana, Docker Compose) with roles, tech, and data ownership |
| End-to-End Data Flow | Mermaid flowchart covering 4 planes: Ingestion → Feature → Training → Serving, with a walkthrough |
| Design Decisions | 6 decisions explained with rationale (two-stage, Feast, Redpanda, local-only, LightGBM, Prometheus/Grafana) |
| Future-Proofing Notes | Where the doc is expected to diverge from reality as we build |

### Key Takeaways
- The architecture doc serves as a **north star** — every later phase builds toward this design, but we expect it to evolve as implementation reveals practical constraints.
- Writing architecture before code is standard practice in engineering teams: it forces explicit trade-off reasoning, aligns contributors, and surfaces disagreements early.
- Specific anticipated divergences: Feast complexity may force simplification, Redpanda may become optional for static data, and service boundaries may merge.

### Manual Steps Required
None.

---

## Phase 4 — Event Streaming Backbone (Redpanda)
**Date**: 2026-07-28

### Files Created
- `config/redpanda/redpanda.yaml` — Minimal single-node Redpanda config (port 9092 Kafka API, 9644 admin, developer mode, 7-day retention, 1 GB partition cap)
- `docker/kafka/init-topics.sh` — Shell script to create the `user-events` topic (3 partitions, 1 replica) via `rpk`
- `docker/kafka/README.md` — Documents using the official Redpanda image directly (no ZooKeeper, no Confluent wrapper)

### Why Redpanda Over Apache Kafka
| Factor | Redpanda | Apache Kafka |
|--------|----------|-------------|
| JVM required | No (C++) | Yes |
| ZooKeeper | None | Required |
| Single binary | Yes | No (broker + ZK + connect) |
| Kafka API | 100% compatible | Native |
| Developer mode | Yes (`--developer-mode`) | No equivalent |

The `user-events` topic will carry all user interaction events (ratings, clicks, purchases) from the API layer to:
- Feast offline store (batch feature computation → Phase 7)
- Real-time feature pipeline (online features → Phase 8)
- Future analytics consumers

### Standalone Test Command
```bash
# Start Redpanda (no config file mount needed — --mode dev-container sets defaults)
docker run -d --name redpanda \
  -p 9092:9092 \
  -p 9644:9644 \
  -v redpanda-data:/var/lib/redpanda/data \
  docker.redpanda.com/redpandadata/redpanda:latest \
  redpanda start --mode dev-container --check=false
```

Create topics: `docker exec redpanda rpk topic create user-events --partitions 3 --replicas 1`
Produce test: `Write-Output '{"user_id":1,"movie_id":42,"rating":4.5}' | docker exec -i redpanda rpk topic produce user-events`
Consume test: `docker exec redpanda rpk topic consume user-events --num 1`

> **⚠️ Mounting a custom `redpanda.yaml`** with `:ro` into `/etc/redpanda/` causes startup failure — the container's entrypoint (running as non-root UID 101) tries to `chown` a temp copy of the config and can't. For standalone dev, use `--mode dev-container` instead. The full Docker Compose file in Phase 11 will handle config via environment variables.

### Key Takeaways
- A message broker decouples producers (user actions) from consumers (feature pipelines, recommenders, analytics) — each reads at its own pace.
- Redpanda's single-binary, no-ZK model makes local dev trivial vs. classic Kafka.
- Event streams enable replay: if a feature bug is found, we can rewind and reprocess historical events.
- Full Docker Compose orchestration (tying Redpanda to other services) comes in Phase 11.

### Manual Steps Required
1. Run the `docker run` command above to start Redpanda
2. Run `docker exec redpanda rpk topic create user-events --partitions 3 --replicas 1`
3. (Optional) Produce a test message and verify consumption via the `rpk topic consume` command

---

## Phase 5 — Simulated Live Event Stream
**Date**: 2026-07-29

### Files Created
- `scripts/data_generator.py` — Reads historical MovieLens ratings and replays them as JSON events to the `user-events` Redpanda topic

### Usage
```bash
# Stream at 10 events per second (default)
python scripts/data_generator.py

# Stream at 100 events per second
python scripts/data_generator.py --rate 100

# Stream in real-time (paced by original timestamps)
python scripts/data_generator.py --rate realtime

# Stream only the first 50 events
python scripts/data_generator.py --rate 50 --max-events 50
```

### Event Schema
```json
{
  "event_type": "rating",
  "user_id": 1,
  "movie_id": 1,
  "rating": 4.0,
  "timestamp": 964982703,
  "datetime": "2000-08-01T00:00:00+00:00"
}
```

### Verification
- Successfully produced 20 test events, then all 100,836 ratings to `user-events`
- Events confirmed across all 3 partitions via `rpk topic consume`
- Average throughput: ~370 evt/s over the network
- kafka-python 3.x required `acks=1` (int) not `acks="1"` (string) — subtle API difference

### Key Takeaways
- Replaying historical data as a live stream is a standard testing strategy for streaming systems — it exercises the same pipeline code, the same consumer groups, and the same infrastructure as real traffic, without needing real users.
- In production, user events arrive sporadically with unpredictable inter-arrival times. The generator simulates this via `--rate` (fixed pacing) or `--rate realtime` (original timestamps).
- A data generator like this is also used for load testing, integration tests, and demo environments. Most streaming systems have a version of this pattern (e.g., `kafka-producer-perf-test`, Redpanda's own `rpk topic produce`).

### Manual Steps Required
None. The generator can be run whenever Redpanda is up and the `user-events` topic exists.

---

## Phase 6 — Experiment Tracking with MLflow
**Date**: 2026-07-31

### Files Created
- `config/mlflow/settings.env` — Environment variables for the MLflow Tracking Server (SQLite backend, local artifact root)
- `docker/mlflow/Dockerfile` — Multi-purpose MLflow server image (python:3.12-slim, exposes 5000)
- `scripts/mlflow_smoke_test.py` — End-to-end connectivity test logging a dummy run

### Usage
```bash
# Build the image
docker build -t recostack-mlflow -f docker/mlflow/Dockerfile .

# Run the server
docker run -d --name mlflow ^
  -p 5000:5000 ^
  -v mlflow-data:/mlflow ^
  --env-file config/mlflow/settings.env ^
  recostack-mlflow

# Open the UI
start http://localhost:5000
```

### Verification
- MLflow server started on `http://localhost:5000` and confirmed via browser
- Logged two runs to the `phase-6-smoke-test` experiment with dummy params/metrics (`dummy_rmse`, `dummy_precision`)
- Runs visible in the MLflow UI at `http://localhost:5000/#/experiments/1`
- Artifacts stored in the `mlflow-data` Docker volume at `/mlflow/artifacts/`
- Metadata stored in SQLite at `/mlflow/mlflow.db` (inside the volume)

### Key Takeaways
- **Model Registry** is a central catalog of all trained models with versioning, stage transitions (Staging → Production → Archived), lineage metadata (who trained it, on what data, with which hyperparams), and deployment annotations. Without one, answering "which exact model + data + params produced this result" becomes a hard problem because: (1) files get overwritten, (2) the same script run a week later produces different weights, (3) team members pick different random seeds, (4) no one remembers which training commit was used. MLflow's Tracking Server is the foundation — the registry layer comes when we actually train models (Phase 7+).
- The `sys.stdout.reconfigure(encoding="utf-8")` workaround was needed because MLflow prints a 🏃 emoji in its run URL, which crashes on Windows cp1252 terminals. This is a known MLflow-on-Windows friction point.
- SQLite is sufficient for single-user local dev (no separate DB server needed). For multi-user, swap to PostgreSQL via `MLFLOW_BACKEND_STORE_URI`.

### Manual Steps Required
None. The server is running at localhost:5000. Rebuild the image only if MLflow needs an upgrade.

---

## Phase 7 — Feature Store Setup (Feast)
**Date**: 2026-08-20

### Files Created/Changed
- `config/feast/feature_store.yaml` — Feast repo config (SQLite registry, Redis online store, Parquet offline store)
- `src/feast/entities.py` — Entity definitions (`user` with `join_keys=["user_id"]`, `movie` with `join_keys=["movie_id"]`)
- `src/feast/sources.py` — Data source definitions pointing to Parquet files in `data/features/`
- `src/feast/feature_views.py` — Three feature views (`user_stats`, `movie_stats`, `interactions`)
- `scripts/generate_feature_data.py` — Computes aggregate features from raw CSV → Parquet
- `scripts/apply_feast.py` — Registers all entities, sources, and feature views in the Feast registry

### Feature Views Registered

| Feature View | Entity | Features | Source |
|---|---|---|---|
| `user_stats` | user | `avg_rating`, `rating_count`, `rating_stddev`, `unique_genres_rated` | `data/features/user_stats.parquet` |
| `movie_stats` | movie | `avg_rating`, `rating_count`, `rating_stddev`, `genres` | `data/features/movie_stats.parquet` |
| `interactions` | user + movie | `rating`, `timestamp` | `data/features/interactions.parquet` |

### Verification
- **Feature generation**: 610 users, 9,724 movies, 100,836 interactions written as Parquet
- **Feast apply**: 3 feature views + 2 entities registered in SQLite registry
- **Historical retrieval**: All three feature views queried successfully via `get_historical_features()`
  - `user_stats` for user 1: avg_rating=3.95, rating_count=232, rating_stddev=0.80
  - `movie_stats` for movie 1 (Toy Story): genres=Adventure|Animation|Children|Comedy|Fantasy
  - `interactions` for user 1 + movie 1: rating=4.0, timestamp=964982703

### Key Takeaways
- **Feast's entity system** requires the entity's `value_type` to match the dtype of the join key column in the feature view schema. We had to align `ValueType.INT64` entities with `Int64` schema fields (not `Int32`).
- **`join_keys` parameter** on entities is critical — without it, Feast uses the entity name as the join column, which fails when the Parquet column is named `user_id` instead of `user`.
- **The `apply()` method** requires explicit object lists — `store.apply(objects=[...])` — not a no-arg call.
- **Registry path** must be a full SQLAlchemy URL (`sqlite:///absolute/path/to/registry.db`), not a plain file path.
- **Historical retrieval** works with a simple entity DataFrame containing the join key columns and `event_timestamp`. This is the foundation for training data generation in Phase 8.

### Manual Steps Required
None. Run `python scripts/generate_feature_data.py` to regenerate features, and `python scripts/apply_feast.py` to re-apply the registry if definitions change.