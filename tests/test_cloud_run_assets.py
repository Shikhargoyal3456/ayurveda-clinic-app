from __future__ import annotations

from pathlib import Path


def test_dockerfile_gcp_targets_cloud_run_defaults():
    dockerfile = Path("Dockerfile.gcp").read_text(encoding="utf-8")
    assert "ENV PORT=8080" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}" in dockerfile


def test_cloudbuild_uses_gcp_dockerfile_and_cloud_run_shape():
    cloudbuild = Path("cloudbuild.yaml").read_text(encoding="utf-8")
    assert "Dockerfile.gcp" in cloudbuild
    assert "--memory" in cloudbuild
    assert "2Gi" in cloudbuild
    assert "--cpu" in cloudbuild
    assert "8080" in cloudbuild
