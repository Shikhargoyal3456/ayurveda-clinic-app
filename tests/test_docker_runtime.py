import os
import shutil
import subprocess
import time

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1" or shutil.which("docker") is None,
    reason="Set RUN_DOCKER_TESTS=1 and ensure Docker is installed to run the deployment smoke test.",
)


def _compose_command() -> list[str]:
    plugin_command = ["docker", "compose"]
    legacy_command = ["docker-compose"]

    try:
        subprocess.run(plugin_command + ["version"], check=True, capture_output=True, text=True)
        return plugin_command
    except Exception:
        return legacy_command


def _wait_for_url(url: str, timeout_seconds: int = 90) -> httpx.Response:
    deadline = time.time() + timeout_seconds
    last_error = None
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code < 500:
                return response
        except Exception as exc:  # pragma: no cover
            last_error = exc
        time.sleep(2)
    raise AssertionError(f"Timed out waiting for {url}. Last error: {last_error}")


def test_docker_compose_runtime_smoke():
    compose = _compose_command()

    subprocess.run(compose + ["up", "-d"], cwd=".", check=True)
    try:
        root_response = _wait_for_url("http://127.0.0.1/")
        assert root_response.status_code == 200

        login_response = _wait_for_url("http://127.0.0.1/login")
        assert login_response.status_code == 200

        health_response = _wait_for_url("http://127.0.0.1/healthz")
        assert health_response.status_code == 200
    finally:
        subprocess.run(compose + ["down"], cwd=".", check=False)
