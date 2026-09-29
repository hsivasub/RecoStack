# RecoStack API — serving layer (FastAPI)

from src.api.app import app
from src.api.event_producer import EventProducer
from src.api.feature_service import FeatureService
from src.api.metrics import (
    PrometheusMiddleware,
    metrics_endpoint,
)
from src.api.models import (
    HealthResponse,
    MovieInfo,
    RatingEvent,
    RatingResponse,
    RecommendRequest,
    RecommendResponse,
)
from src.api.recommend_service import RecommendService

__all__ = [
    "app",
    "RecommendService",
    "FeatureService",
    "EventProducer",
    "RatingEvent",
    "RecommendRequest",
    "RecommendResponse",
    "RatingResponse",
    "HealthResponse",
    "MovieInfo",
    "PrometheusMiddleware",
    "metrics_endpoint",
]