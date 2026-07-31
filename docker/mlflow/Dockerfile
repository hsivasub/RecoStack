# RecoStack — MLflow Tracking Server
#
# Build:   docker build -t recostack-mlflow -f docker/mlflow/Dockerfile .
# Run:     docker run -d --name mlflow ^
#             -p 5000:5000 ^
#             -v mlflow-data:/mlflow ^
#             --env-file config/mlflow/settings.env ^
#             recostack-mlflow
#
# UI:      http://localhost:5000

FROM python:3.12-slim

RUN pip install --no-cache-dir mlflow>=2.10.0

EXPOSE 5000

# Defaults — override via --env-file or -e at runtime
ENV MLFLOW_BACKEND_STORE_URI=sqlite:///mlflow/mlflow.db
ENV MLFLOW_ARTIFACT_ROOT=/mlflow/artifacts
ENV MLFLOW_HOST=0.0.0.0
ENV MLFLOW_PORT=5000

VOLUME ["/mlflow"]

ENTRYPOINT ["mlflow", "server", \
    "--backend-store-uri", "sqlite:///mlflow/mlflow.db", \
    "--default-artifact-root", "/mlflow/artifacts", \
    "--host", "0.0.0.0", \
    "--port", "5000"]