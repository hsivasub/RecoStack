# RecoStack

A fully local, open-source, production-style recommendation system built with modern ML infrastructure tooling.

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Events      │────▶│  Redpanda    │────▶│  Feature      │
│  (Streaming) │     │  (Kafka API) │     │  Pipeline     │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  FastAPI     │◀────│  Ranker       │◀────│  Candidate   │
│  (Serving)   │     │  (LightGBM)   │     │  Generator   │
└──────┬──────┘     └──────────────┘     │  (MF/Embed)  │
       │                                  └──────────────┘
       ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Prometheus  │     │  Grafana      │     │  MLflow      │
│  (Metrics)   │     │  (Dashboards) │     │  (Tracking)  │
└─────────────┘     └──────────────┘     └──────────────┘
```

## Stack

| Component          | Technology                          |
|--------------------|-------------------------------------|
| Language           | Python 3.12                         |
| Streaming          | Redpanda (Kafka-compatible)         |
| Feature Store      | Feast                               |
| Experiment Tracking| MLflow                              |
| Serving            | FastAPI + Redis                     |
| Monitoring         | Prometheus + Grafana                |
| Orchestration      | Docker Compose                      |
| CI/CD              | GitHub Actions                      |

## Quick Start

1. **Prerequisites**: Python 3.12, Docker Desktop, Git
2. **Clone**: `git clone <url> && cd recostack`
3. **Environment**: `python -m venv .venv && .venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
4. **Install base + dev**: `pip install -e ".[dev]"` — this installs only essential packages. Add extras per phase:
   - ML stack: `pip install -e ".[ml]"`
   - Feast: `pip install -e ".[feast]"`
   - MLflow: `pip install -e ".[mlflow]"`
   - Everything: `pip install -e ".[all]"`
5. **Start services**: `docker compose up -d`
6. **Run**: `python scripts/run_pipeline.py`

## Project Structure

```
RECOSTACK/
├── config/              # Service configurations
├── data/                # Datasets & model artifacts
├── docker/              # Dockerfiles for each service
├── docs/                # Architecture & API docs
├── scripts/             # Pipeline entry points
├── src/
│   ├── api/             # FastAPI serving layer
│   ├── feast/           # Feast feature definitions
│   └── recommenders/    # ML models (MF, LightGBM)
└── tests/               # Unit & integration tests
```

## Phases

See [PROGRESS.md](PROGRESS.md) for the build roadmap.