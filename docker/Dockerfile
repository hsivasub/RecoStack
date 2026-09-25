# RecoStack — FastAPI Serving Image
#
# Build:   docker build -t recostack-api -f docker/Dockerfile .
# Run:     docker run -d --name recostack-api -p 8000:8000 recostack-api
#
# In production / compose, volumes and env vars are provided by docker-compose.yaml.

FROM python:3.12-slim

WORKDIR /app

# Install system deps needed by lightgbm, scikit-learn, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the full recostack package, config, and data references
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY config/ ./config/

# Install the package with serving, monitoring, and streaming extras
RUN pip install --no-cache-dir .[serving,monitoring,streaming]

# Volumes for runtime data (provided by docker-compose)
VOLUME ["/app/data"]

EXPOSE 8000

# Default: run the API with uvicorn
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]