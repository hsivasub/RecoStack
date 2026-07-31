"""Phase 6 — smoke test: log a dummy run to the MLflow tracking server."""

import os
import sys

# Tell Python to use utf-8 so MLflow's emoji doesn't crash on Windows
sys.stdout.reconfigure(encoding="utf-8")

import mlflow

mlflow.set_tracking_uri("http://localhost:5000")
client = mlflow.MlflowClient()

# Terminate the dangling run from the first attempt
client.set_terminated("bbe1fc8b2386435599414701d06c4400")
print("Run terminated.")

# Log a clean second run
mlflow.set_experiment("phase-6-smoke-test")
with mlflow.start_run(run_name="clean-connectivity-test"):
    mlflow.log_param("model_type", "dummy-v2")
    mlflow.log_param("dataset", "movielens-100k")
    mlflow.log_metric("dummy_rmse", 0.8765)
    mlflow.log_metric("dummy_precision", 0.55)
    mlflow.set_tag("phase", "6")
    mlflow.set_tag("purpose", "clean run with utf-8 fix")
    print(f"Clean run logged: {mlflow.active_run().info.run_id}")

print("All done.")