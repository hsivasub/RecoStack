"""
run_api.py — Phase 9: Serving API Entry Point

Starts the FastAPI serving layer for RecoStack.

Usage:
    python scripts/run_api.py
    python scripts/run_api.py --port 8080 --reload

The API exposes:
  - GET  /health      — Health check
  - GET  /recommend   — Top-K recommendations for a user
  - POST /rate        — Submit a rating event

Prerequisites:
    - Trained models exist in data/model-artifacts/ (run scripts/train_models.py)
    - Feature Parquet files exist in data/features/ (run scripts/generate_feature_data.py)
    - (Optional) Redpanda running at localhost:9092 for event streaming
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RecoStack — Serving API (Phase 9)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on file changes (dev mode)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: info)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("=" * 60)
    print("RecoStack — Serving API (Phase 9)")
    print("=" * 60)
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Reload: {args.reload}")
    print(f"  Docs: http://localhost:{args.port}/docs")
    print("=" * 60)

    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()