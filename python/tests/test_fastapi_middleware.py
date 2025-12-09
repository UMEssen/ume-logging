import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import logging

from umelogging.context import (
    request_id_var,
    component_var,
    app_var,
    env_var,
    service_var,
    user_hash_var,
    extra_var,
)

# Import FastAPI dependencies - skip tests if not installed
pytest.importorskip("fastapi")
pytest.importorskip("starlette")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import Response

from umelogging.fastapi.middleware import UMERequestLoggerMiddleware


@pytest.fixture(autouse=True)
def reset_context():
    """Reset context variables before each test."""
    app_var.set(os.getenv("UME_APP"))
    env_var.set(os.getenv("UME_ENV", "prod"))
    service_var.set(os.getenv("UME_SERVICE"))
    component_var.set("")
    request_id_var.set("")
    user_hash_var.set("")
    extra_var.set(None)
    yield


@pytest.fixture
def app():
    """Create a FastAPI app with the middleware."""
    fastapi_app = FastAPI()
    fastapi_app.add_middleware(UMERequestLoggerMiddleware)

    @fastapi_app.get("/")
    async def root():
        return {"message": "Hello"}

    @fastapi_app.get("/request-id")
    async def get_request_id():
        return {"request_id": request_id_var.get()}

    @fastapi_app.get("/component")
    async def get_component():
        return {"component": component_var.get()}

    @fastapi_app.get("/error")
    async def error():
        raise ValueError("Test error")

    @fastapi_app.get("/slow")
    async def slow():
        import asyncio
        await asyncio.sleep(0.1)
        return {"status": "done"}

    return fastapi_app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


class TestUMERequestLoggerMiddleware:
    def test_request_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_generates_request_id(self, client):
        response = client.get("/")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) == 36  # UUID format

    def test_uses_provided_request_id(self, client):
        custom_id = "custom-request-id-123"
        response = client.get("/", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id

    def test_sets_request_id_in_context(self, client):
        response = client.get("/request-id")
        data = response.json()
        assert data["request_id"]
        assert len(data["request_id"]) == 36

    def test_sets_component_to_http(self, client):
        response = client.get("/component")
        data = response.json()
        assert data["component"] == "http"

    def test_returns_request_id_in_response_header(self, client):
        response = client.get("/")
        request_id = response.headers.get("X-Request-ID")
        assert request_id is not None

    def test_custom_header_name(self):
        app = FastAPI()
        app.add_middleware(UMERequestLoggerMiddleware, request_id_header="X-Correlation-ID")

        @app.get("/")
        async def root():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/", headers={"X-Correlation-ID": "custom-123"})
        assert response.headers.get("X-Correlation-ID") == "custom-123"

    def test_logs_request_start(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ume.request"):
            client.get("/")

        # Check that request.start was logged
        start_logs = [r for r in caplog.records if "request.start" in r.getMessage()]
        assert len(start_logs) >= 1

    def test_logs_request_end(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ume.request"):
            client.get("/")

        end_logs = [r for r in caplog.records if "request.end" in r.getMessage()]
        assert len(end_logs) >= 1

    def test_logs_method_and_path(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ume.request"):
            client.get("/")

        start_logs = [r for r in caplog.records if "request.start" in r.getMessage()]
        assert len(start_logs) >= 1
        record = start_logs[0]
        assert record.method == "GET"
        assert record.path == "/"

    def test_logs_status_code(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ume.request"):
            client.get("/")

        end_logs = [r for r in caplog.records if "request.end" in r.getMessage()]
        assert len(end_logs) >= 1
        record = end_logs[0]
        assert record.status == 200

    def test_logs_duration(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="ume.request"):
            client.get("/slow")

        end_logs = [r for r in caplog.records if "request.end" in r.getMessage()]
        assert len(end_logs) >= 1
        record = end_logs[0]
        assert hasattr(record, "duration_ms")
        assert record.duration_ms >= 100  # At least 100ms for slow endpoint

    def test_handles_exceptions(self, client, caplog):
        """Middleware logs start even when endpoint raises."""
        with caplog.at_level(logging.INFO, logger="ume.request"):
            response = client.get("/error")

        # Should have logged start (end not logged if exception bubbles up)
        assert response.status_code == 500
        start_logs = [r for r in caplog.records if "request.start" in r.getMessage()]
        assert len(start_logs) >= 1


class TestMiddlewareIsolation:
    def test_request_id_isolated_between_requests(self, client):
        """Each request should get its own request ID."""
        response1 = client.get("/request-id")
        response2 = client.get("/request-id")

        id1 = response1.json()["request_id"]
        id2 = response2.json()["request_id"]

        assert id1 != id2


class TestMiddlewareInit:
    def test_default_header_name(self):
        app = FastAPI()
        middleware = UMERequestLoggerMiddleware(app)
        assert middleware.request_id_header == "X-Request-ID"

    def test_custom_header_name(self):
        app = FastAPI()
        middleware = UMERequestLoggerMiddleware(app, request_id_header="X-Custom")
        assert middleware.request_id_header == "X-Custom"

    def test_has_logger(self):
        app = FastAPI()
        middleware = UMERequestLoggerMiddleware(app)
        assert middleware.log.name == "ume.request"
