import io
import json
import logging
import os
import pytest

from umelogging.config import log_configure, _level_from_env, _build_handlers
from umelogging.context import app_var, env_var, service_var, component_var, extra_var, request_id_var, user_hash_var
from umelogging.formatter import JsonFormatter
from umelogging.filters import PiiScrubberFilter


@pytest.fixture(autouse=True)
def reset_logging_and_context():
    """Reset logging configuration and context before each test."""
    # Reset context
    app_var.set(os.getenv("UME_APP"))
    env_var.set(os.getenv("UME_ENV", "prod"))
    service_var.set(os.getenv("UME_SERVICE"))
    component_var.set("")
    request_id_var.set("")
    user_hash_var.set("")
    extra_var.set(None)

    # Reset root logger
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.WARNING)

    yield

    # Cleanup after test
    root = logging.getLogger()
    root.handlers = []


class TestLevelFromEnv:
    def test_returns_default_when_no_env(self, monkeypatch):
        monkeypatch.delenv("UME_LOG_LEVEL", raising=False)
        level = _level_from_env("WARNING")
        assert level == logging.WARNING

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("UME_LOG_LEVEL", "DEBUG")
        level = _level_from_env("INFO")
        assert level == logging.DEBUG

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("UME_LOG_LEVEL", "debug")
        level = _level_from_env("INFO")
        assert level == logging.DEBUG

    def test_invalid_level_returns_info(self, monkeypatch):
        monkeypatch.setenv("UME_LOG_LEVEL", "INVALID")
        level = _level_from_env("INVALID")
        assert level == logging.INFO


class TestBuildHandlers:
    def test_returns_list_of_handlers(self):
        stream = io.StringIO()
        handlers = _build_handlers(stream, {"org": "TEST"})
        assert len(handlers) == 1
        assert isinstance(handlers[0], logging.StreamHandler)

    def test_handler_has_json_formatter(self):
        stream = io.StringIO()
        handlers = _build_handlers(stream, {})
        assert isinstance(handlers[0].formatter, JsonFormatter)

    def test_handler_has_pii_filter(self):
        stream = io.StringIO()
        handlers = _build_handlers(stream, {})
        filters = handlers[0].filters
        assert any(isinstance(f, PiiScrubberFilter) for f in filters)

    def test_uses_provided_stream(self):
        stream = io.StringIO()
        handlers = _build_handlers(stream, {})
        assert handlers[0].stream is stream


class TestLogConfigure:
    def test_configures_root_logger(self):
        stream = io.StringIO()
        log_configure(level="DEBUG", stream=stream)

        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) > 0

    def test_sets_context(self):
        stream = io.StringIO()
        log_configure(
            app="testapp",
            env="test",
            service="testsvc",
            component="testcomp",
            stream=stream,
        )
        assert app_var.get() == "testapp"
        assert env_var.get() == "test"
        assert service_var.get() == "testsvc"
        assert component_var.get() == "testcomp"

    def test_reads_context_from_env(self, monkeypatch):
        monkeypatch.setenv("UME_APP", "envapp")
        monkeypatch.setenv("UME_ENV", "envenv")
        monkeypatch.setenv("UME_SERVICE", "envsvc")

        stream = io.StringIO()
        log_configure(stream=stream)

        assert app_var.get() == "envapp"
        assert env_var.get() == "envenv"
        assert service_var.get() == "envsvc"

    def test_explicit_values_override_env(self, monkeypatch):
        monkeypatch.setenv("UME_APP", "envapp")
        stream = io.StringIO()
        log_configure(app="explicitapp", stream=stream)
        assert app_var.get() == "explicitapp"

    def test_outputs_json(self):
        stream = io.StringIO()
        log_configure(level="INFO", stream=stream)

        logger = logging.getLogger("test.json")
        logger.info("Test message")

        output = stream.getvalue()
        # Should have at least the init message
        lines = [l for l in output.strip().split("\n") if l]
        assert len(lines) >= 1

        # Each line should be valid JSON
        for line in lines:
            parsed = json.loads(line)
            assert "message" in parsed
            assert "level" in parsed

    def test_default_static_fields(self):
        stream = io.StringIO()
        log_configure(stream=stream)

        logger = logging.getLogger("test.static")
        logger.info("Test")

        output = stream.getvalue()
        lines = output.strip().split("\n")
        for line in lines:
            if line:
                parsed = json.loads(line)
                assert parsed.get("org") == "UME"

    def test_custom_static_fields(self):
        stream = io.StringIO()
        log_configure(stream=stream, static_fields={"custom": "value", "org": "CUSTOM"})

        logger = logging.getLogger("test.custom")
        logger.info("Test")

        output = stream.getvalue()
        lines = output.strip().split("\n")
        # Find our test message
        for line in lines:
            if line and "Test" in line:
                parsed = json.loads(line)
                assert parsed.get("custom") == "value"
                assert parsed.get("org") == "CUSTOM"

    def test_level_from_env(self, monkeypatch):
        monkeypatch.setenv("UME_LOG_LEVEL", "WARNING")
        stream = io.StringIO()
        log_configure(stream=stream)

        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_integer_level(self):
        stream = io.StringIO()
        log_configure(level=logging.ERROR, stream=stream)

        root = logging.getLogger()
        assert root.level == logging.ERROR

    def test_propagate_existing_loggers(self):
        # Create a logger before configure
        pre_logger = logging.getLogger("pre.existing")
        pre_logger.setLevel(logging.CRITICAL)

        stream = io.StringIO()
        log_configure(level="DEBUG", stream=stream, propagate_existing=True)

        # Logger should now use root level
        assert pre_logger.level == logging.DEBUG
        assert pre_logger.propagate is True

    def test_no_propagate_existing(self):
        pre_logger = logging.getLogger("pre.nopropagate")
        pre_logger.setLevel(logging.CRITICAL)

        stream = io.StringIO()
        log_configure(level="DEBUG", stream=stream, propagate_existing=False)

        # Logger should keep its level
        assert pre_logger.level == logging.CRITICAL

    def test_uvicorn_loggers_configured(self):
        stream = io.StringIO()
        log_configure(stream=stream)

        uvicorn_logger = logging.getLogger("uvicorn")
        assert uvicorn_logger.propagate is True
        assert uvicorn_logger.handlers == []

        uvicorn_error = logging.getLogger("uvicorn.error")
        assert uvicorn_error.propagate is True

    def test_logs_init_message(self):
        stream = io.StringIO()
        log_configure(level="INFO", stream=stream)

        output = stream.getvalue()
        assert "Logging initialized" in output


class TestLogConfigureIntegration:
    def test_full_logging_pipeline(self):
        stream = io.StringIO()
        log_configure(
            level="DEBUG",
            app="integration-test",
            env="test",
            service="test-svc",
            stream=stream,
        )

        logger = logging.getLogger("integration")
        logger.info("Test message", extra={"custom_field": "custom_value"})

        output = stream.getvalue()
        lines = output.strip().split("\n")

        # Find our specific log
        for line in lines:
            if "Test message" in line:
                parsed = json.loads(line)
                assert parsed["app"] == "integration-test"
                assert parsed["env"] == "test"
                assert parsed["service"] == "test-svc"
                assert parsed["level"] == "INFO"
                break

    def test_pii_scrubbed_in_output(self):
        stream = io.StringIO()
        log_configure(level="INFO", stream=stream)

        logger = logging.getLogger("pii.test")
        logger.info("Contact: user@example.com")

        output = stream.getvalue()
        assert "[email]" in output
        assert "user@example.com" not in output
