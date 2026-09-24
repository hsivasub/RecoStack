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

---

## Phase 8 — Training Pipeline (Candidate Generation + Ranking)
**Date**: 2026-09-08

### Files Created/Changed
- `src/recommenders/candidate_generation.py` — SVD-based candidate generation model (TruncatedSVD, 50 latent factors)
- `src/recommenders/ranking.py` — LightGBM ranking model with pointwise regression (RMSE objective)
- `src/recommenders/training_pipeline.py` — Orchestrator: Feast feature retrieval → SVD training → LightGBM training → MLflow logging
- `scripts/train_models.py` — CLI entry point with `--dry-run`, `--svd-factors`, `--lgb-rounds` options
- `src/recommenders/__init__.py` — Updated with public API exports
- `scripts/generate_feature_data.py` — Added `unique_genres_rated` feature to user stats
- `src/feast/` → `src/feature_defs/` — Renamed to avoid shadowing the installed `feast` library

### Architecture

```
Feast (historical features)
        │
        ▼
┌─────────────────────────────────────────┐
│         Training Pipeline               │
│  ┌──────────────────────────────────┐   │
│  │ Stage 1: SVD Candidate Gen      │   │
│  │ TruncatedSVD (50 factors)       │   │
│  │ 610 users × 9,724 movies matrix │   │
│  │ → Top-100 candidates per user   │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │ Stage 2: LightGBM Ranking       │   │
│  │ 12 features (user + movie stats │   │
│  │ + derived features)             │   │
│  │ → Score & rank candidates       │   │
│  └──────────────────────────────────┘   │
│         ↓                               │
│  MLflow (params, metrics, artifacts)    │
└─────────────────────────────────────────┘
```

### Training Results

| Metric | Value |
|---|---|
| SVD training time | 4.5s |
| SVD training RMSE | 0.8155 |
| LightGBM training time | 5.1s |
| LightGBM best iteration | 115 rounds |
| Validation RMSE | 0.2335 |
| Validation MAE | 0.1213 |
| Training rows | 488 |
| Validation rows | 122 |
| Feature count | 12 |

### Top-5 Feature Importance (Gain)
1. **user_deviation** (3,468.7) — User's rating deviation from movie average
2. **movie_stats__avg_rating** (1,068.4) — Movie's average rating
3. **user_stats__avg_rating** (63.8) — User's average rating
4. **movie_stats__rating_stddev** (53.1) — Movie rating variance
5. **user_stats__rating_stddev** (45.7) — User rating variance

### Key Takeaways
- **Two-stage architecture works**: SVD narrows 9,724 → ~100 candidates cheaply; LightGBM scores only those 100 with rich features.
- **user_deviation dominates** feature importance — how much a user's rating differs from the movie's average is the strongest signal. This makes intuitive sense: if a user rates a movie 1.0 when the average is 4.0, that's highly informative.
- **SVD RMSE of 0.82** is reasonable for 50 factors on a 98.3% sparse matrix. More factors would improve reconstruction but risk overfitting.
- **LightGBM validation RMSE of 0.23** is excellent — the model generalizes well from 488 training examples.
- **Feast full_feature_names=True** was required because `user_stats` and `movie_stats` share column names (`avg_rating`, `rating_count`, `rating_stddev`). Feast prefixes them as `user_stats__avg_rating` and `movie_stats__avg_rating`.
- **Local package naming matters**: `src/feast/` shadows the installed `feast` library. Renamed to `src/feature_defs/`.
- **MLflow 3.14 on Python 3.14**: The MLflow server has compatibility issues with Python 3.14 (uvicorn multiprocess + importlib.abc.Traversable). Using local SQLite tracking (`sqlite:///`) works reliably.

### Manual Steps Required
None. Run `python scripts/train_models.py` to re-run the full pipeline. Use `--dry-run` to verify prerequisites without training.

### Next Phase
Phase 9 — Serving API (FastAPI endpoints for `/recommend` and `/rate`)

---

## Phase 9 — Serving API (FastAPI)
**Date**: 2026-09-18

### Files Created
- `src/api/models.py` — Pydantic request/response schemas (`RatingEvent`, `RecommendRequest`, `RecommendResponse`, `RatingResponse`, `HealthResponse`, `MovieInfo`)
- `src/api/feature_service.py` — Online feature retrieval with Feast Redis backend + Parquet fallback
- `src/api/recommend_service.py` — Two-stage inference orchestrator (SVD → LightGBM)
- `src/api/event_producer.py` — Redpanda event producer for rating events (graceful degradation)
- `src/api/app.py` — FastAPI application with `/health`, `/recommend`, `/rate` endpoints
- `scripts/run_api.py` — CLI entry point for `uvicorn`

### Architecture

```
┌─────────────┐     ┌─────────────────────────────────────────────┐
│  Client     │     │           FastAPI Server (:8000)            │
│             │     │                                             │
│ GET /recommend ──→│  RecommendService                           │
│             │     │  ├── SVDCandidateGenerator (loaded .pkl)    │
│             │     │  ├── LightGBMRanker (loaded .txt)           │
│             │     │  └── FeatureService                         │
│             │     │      ├── Feast online store (Redis)         │
│             │     │      └── Parquet fallback                   │
│             │     │                                             │
│ POST /rate  ──→│  EventProducer                                 │
│             │     │  └── Redpanda topic `user-events`           │
│             │     │      (or local log fallback)                │
└─────────────┘     └─────────────────────────────────────────────┘
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — models loaded, Redpanda connected, Feast available |
| GET | `/recommend?user_id=X&top_k=N` | Top-K recommendations (SVD → LightGBM) |
| POST | `/rate` | Submit a rating event (published to Redpanda) |
| GET | `/docs` | Interactive Swagger UI |

### Inference Flow (`/recommend`)

1. **SVD candidate generation**: `get_candidates(user_id, n_candidates=100)` — dot product of user embedding with all item embeddings, returns top-100 movie IDs
2. **Feature assembly**: Fetch user stats from `FeatureService` + movie stats for each candidate from Parquet/Feast; compute derived features (`user_deviation`, `movie_popularity_log`, `user_activity_log`, `genre_count`)
3. **LightGBM scoring**: `predict(feature_df)` → scores for all candidates
4. **Rank & return**: Sort by score descending, return top-K with movie title/genres

### Graceful Degradation

| Component | Unavailable Behavior |
|-----------|---------------------|
| **Feast/Redis** | Falls back to Parquet files in `data/features/` |
| **Redpanda** | Logs events to stdout instead of publishing |
| **Unknown user** | Uses average user features (cold-start fallback) |
| **Missing model files** | Returns 503 with descriptive error |

### Key Takeaways
- **Stateless inference**: Models are loaded once at startup and shared across requests. No per-request training or Feast connection setup.
- **Feature parity with training**: The derived features computed at inference time (`user_deviation`, `movie_popularity_log`, etc.) must exactly match the training pipeline's logic. Any discrepancy would cause silent prediction degradation.
- **Cold-start handling**: Unknown users get average feature values (3.5 avg rating, 0 count, 0 stddev). Unknown movies are simply skipped during candidate ranking.
- **Redpanda as optional**: The event producer degrades gracefully — if Redpanda isn't running, events are logged. This lets the API work in minimal dev mode without Docker.
- **FastAPI lifespan**: Using the `lifespan` context manager for startup (model loading, service init) and shutdown (producer flush/close) instead of deprecated `@app.on_event`.

### Manual Steps Required
1. Ensure trained models exist: `python scripts/train_models.py`
2. Ensure feature Parquet files exist: `python scripts/generate_feature_data.py`
3. Start the API: `python scripts/run_api.py`
4. Open docs: http://localhost:8000/docs
5. (Optional) Start Redpanda for event streaming: `docker start redpanda`

### Next Phase
Phase 10 — Monitoring & Observability (Prometheus metrics + Grafana dashboards)

---

## Phase 10 — Monitoring & Observability (Prometheus + Grafana)
**Date**: 2026-09-23

### Files Created
- `src/api/metrics.py` — Prometheus metrics definitions (counters, histograms, gauges) + ASGI middleware + `/metrics` handler
- `config/prometheus/prometheus.yml` — Prometheus scrape config (targets `host.docker.internal:8000` every 5s)
- `docker/prometheus/Dockerfile` — Prometheus image with baked-in scrape config
- `config/grafana/provisioning/datasources/prometheus.yml` — Auto-registers Prometheus datasource
- `config/grafana/provisioning/dashboards/dashboards.yml` — Auto-loads dashboard JSON files
- `config/grafana/dashboards/recostack-overview.json` — Pre-built Grafana dashboard (11 panels)
- `docker/grafana/Dockerfile` — Grafana image with baked-in provisioning + dashboard

### Files Modified (Metrics Instrumentation)
- `src/api/app.py` — Added `PrometheusMiddleware`, `/metrics` endpoint, health gauges in lifespan, rate event counters
- `src/api/recommend_service.py` — Added `RECOMMEND_LATENCY_SECONDS`, `RECOMMEND_CANDIDATES`, `RECOMMEND_RESULTS`, `RECOMMEND_ERRORS` instrumentation
- `src/api/feature_service.py` — Added `FEATURE_LOOKUP_DURATION_SECONDS`, `FEATURE_LOOKUP_ERRORS` to all feature retrieval methods
- `src/api/__init__.py` — Added `PrometheusMiddleware`, `metrics_endpoint` to public exports

### Metrics Exported

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `recostack_http_requests_total` | Counter | method, endpoint, status | Total HTTP requests |
| `recostack_http_request_duration_seconds` | Histogram | method, endpoint | Request latency (10 buckets, 5ms–10s) |
| `recostack_recommend_latency_seconds` | Histogram | — | End-to-end recommend latency |
| `recostack_recommend_candidates` | Histogram | — | SVD candidate count per request |
| `recostack_recommend_results` | Histogram | — | Results returned (top-K) |
| `recostack_recommend_errors_total` | Counter | reason | Recommendation errors |
| `recostack_rate_events_total` | Counter | status | Rating events (published/logged/failed) |
| `recostack_models_loaded` | Gauge | — | 0–2 (SVD + LightGBM) |
| `recostack_models_ready` | Gauge | — | 1 if both models loaded |
| `recostack_feast_available` | Gauge | — | 1 if Feast connected |
| `recostack_redpanda_connected` | Gauge | — | 1 if Redpanda connected |
| `recostack_feature_lookup_duration_seconds` | Histogram | entity_type | Feature retrieval latency |
| `recostack_feature_lookup_errors_total` | Counter | entity_type | Feature lookup errors |

### Grafana Dashboard (System Overview)
The dashboard includes **11 panels** across 4 rows:

| Row | Panel(s) |
|-----|----------|
| **Row 1** | HTTP Request Rate (by endpoint), HTTP Latency (p50/p95/p99), HTTP Error Rate |
| **Row 2** | Recommendation Latency (p50/p95/p99), Candidate Count, Rate Events/sec |
| **Row 3** | System Health stat (Models Ready), Feast Available stat, Redpanda Connected stat |
| **Row 4** | Feature Lookup Latency (user vs. movie, p95), Recommendation Errors |

### Architecture

```
┌──────────────┐    scrape :8000/metrics     ┌──────────────┐
│  FastAPI      │ ◄─────────────────────────│  Prometheus   │
│  (:8000)      │                             │  (:9090)      │
│  ┌──────────┐ │                             └──────┬───────┘
│  │ Metrics  │ │                                    │
│  │ Module   │ │                            query    │
│  └──────────┘ │                                    ▼
└──────────────┘                             ┌──────────────┐
                                             │   Grafana    │
                                             │  (:3000)     │
                                             │  admin/admin │
                                             └──────────────┘
```

### How to Run
```bash
# 1. Start the FastAPI API
python scripts/run_api.py

# 2. Start Prometheus (in a second terminal)
docker build -t recostack-prometheus -f docker/prometheus/Dockerfile .
docker run -d --name prometheus -p 9090:9090 recostack-prometheus

# 3. Start Grafana
docker build -t recostack-grafana -f docker/grafana/Dockerfile .
docker run -d --name grafana -p 3000:3000 recostack-grafana

# 4. Open dashboards
start http://localhost:3000  (admin/admin → RecoStack folder → System Overview)
start http://localhost:9090  (Prometheus expression browser)
start http://localhost:8000/metrics  (raw metrics)
```

### Usage
```bash
# Generate traffic for the dashboards
curl http://localhost:8000/health
curl "http://localhost:8000/recommend?user_id=1&top_k=5"
curl -X POST http://localhost:8000/rate -H "Content-Type: application/json" -d "{\"user_id\":1,\"movie_id\":42,\"rating\":4.5}"

# Query Prometheus directly
curl "http://localhost:9090/api/v1/query?query=recostack_models_ready"
```

### Key Takeaways
- **Three observation planes**: (1) Raw metrics endpoint (`/metrics`) for curl-level debugging, (2) Prometheus for time-series storage and ad-hoc querying, (3) Grafana for persistent visualized dashboards.
- **Histogram buckets were chosen deliberately**: 5ms–10s for HTTP latency (captures both healthy <50ms requests and slow cold-starts), 1–200 for candidates (SVD returns exactly 100), 1–100 for results (top-K caps at 100).
- **Health gauges are set once at startup** (models loaded, Feast, Redpanda). They update only on restart — live health changes would require a background health-check loop.
- **Prometheus on Windows**: Uses `host.docker.internal:8000` instead of `localhost:8000` because Prometheus runs inside a container and needs to reach the host. This is a Windows Docker Desktop pattern.
- **Grafana auto-provisioning**: Datasource and dashboard YAML configs are baked into the image so the dashboard is ready on first load — no manual "Add datasource" or "Import JSON" steps.
- **Docker Compose (Phase 11)** will wire the networking between FastAPI, Prometheus, and Grafana automatically, removing the need for manual container runs.

### Manual Steps Required
1. Run `docker build` and `docker run` for Prometheus and Grafana (or wait for Phase 11 Docker Compose)
2. Generate traffic to populate the dashboards (curl commands above)
3. Open Grafana at http://localhost:3000 (admin/admin)

### Next Phase
Phase 11 — Docker Compose Orchestration (wire all 6+ services together)