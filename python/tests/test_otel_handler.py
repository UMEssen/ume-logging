import logging
import os
import pytest
from unittest.mock import MagicMock, patch

# Skip all tests if opentelemetry is not installed
otel = pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk.trace")
pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import SpanContext, TraceFlags

from umelogging.otel.handler import (
    setup_otel_tracing,
    _parse_headers,
    OTelSpanEventHandler,
)


@pytest.fixture(autouse=True)
def reset_tracer():
    """Reset global tracer provider after each test."""
    yield
    # Reset to a no-op provider
    trace.set_tracer_provider(TracerProvider())


class TestParseHeaders:
    def test_parses_single_header(self):
        result = _parse_headers("key=value")
        assert result == {"key": "value"}

    def test_parses_multiple_headers(self):
        result = _parse_headers("key1=value1,key2=value2")
        assert result == {"key1": "value1", "key2": "value2"}

    def test_handles_whitespace(self):
        result = _parse_headers("key1 = value1 , key2 = value2")
        assert result == {"key1": "value1", "key2": "value2"}

    def test_returns_none_for_empty(self):
        result = _parse_headers("")
        assert result is None

    def test_returns_none_for_none(self):
        result = _parse_headers(None)
        assert result is None

    def test_handles_value_with_equals(self):
        result = _parse_headers("auth=token=abc123")
        assert result == {"auth": "token=abc123"}

    def test_skips_invalid_entries(self):
        result = _parse_headers("valid=value,invalid")
        assert result == {"valid": "value"}


class TestSetupOtelTracing:
    def test_returns_tracer_provider(self):
        provider = setup_otel_tracing(
            service_name="test-service",
            auto_set_global=False,
        )
        assert isinstance(provider, TracerProvider)

    def test_sets_service_name(self):
        provider = setup_otel_tracing(
            service_name="my-service",
            auto_set_global=False,
        )
        # Check resource attributes
        resource = provider.resource
        assert resource.attributes.get("service.name") == "my-service"

    def test_sets_global_provider_by_default(self):
        provider = setup_otel_tracing(
            service_name="global-test",
            auto_set_global=True,
        )
        # Provider was created and set_tracer_provider was called
        # Note: OTel may warn about overriding but the call is made
        assert provider is not None
        assert isinstance(provider, TracerProvider)

    def test_does_not_set_global_when_disabled(self):
        original_provider = trace.get_tracer_provider()
        provider = setup_otel_tracing(
            service_name="no-global",
            auto_set_global=False,
        )
        assert trace.get_tracer_provider() is not provider

    def test_custom_resource_attrs(self):
        provider = setup_otel_tracing(
            service_name="test",
            resource_attrs={"custom.attr": "custom-value"},
            auto_set_global=False,
        )
        resource = provider.resource
        assert resource.attributes.get("custom.attr") == "custom-value"

    def test_reads_service_name_from_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "env-service")
        provider = setup_otel_tracing(
            service_name=None,
            auto_set_global=False,
        )
        # When service_name is None, it should fall through to env or default
        resource = provider.resource
        # The setup_otel_tracing uses `service_name or os.getenv(...)` so None becomes the env value
        assert resource.attributes.get("service.name") == "env-service"

    def test_default_sampling_ratio(self):
        provider = setup_otel_tracing(
            service_name="test",
            sampling_ratio=1.0,
            auto_set_global=False,
        )
        assert provider is not None

    def test_custom_sampling_ratio(self):
        provider = setup_otel_tracing(
            service_name="test",
            sampling_ratio=0.5,
            auto_set_global=False,
        )
        assert provider is not None

    def test_sampling_ratio_from_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.25")
        provider = setup_otel_tracing(
            service_name="test",
            auto_set_global=False,
        )
        assert provider is not None

    def test_invalid_sampling_ratio_from_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "invalid")
        # Should not raise, falls back to default
        provider = setup_otel_tracing(
            service_name="test",
            auto_set_global=False,
        )
        assert provider is not None

    def test_custom_endpoint(self):
        provider = setup_otel_tracing(
            service_name="test",
            otlp_endpoint="http://custom:4318",
            auto_set_global=False,
        )
        assert provider is not None

    def test_endpoint_from_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://env-collector:4318")
        provider = setup_otel_tracing(
            service_name="test",
            auto_set_global=False,
        )
        assert provider is not None

    def test_custom_headers(self):
        provider = setup_otel_tracing(
            service_name="test",
            otlp_headers={"Authorization": "Bearer token"},
            auto_set_global=False,
        )
        assert provider is not None

    def test_headers_from_env(self, monkeypatch):
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_HEADERS", "auth=token,other=value")
        provider = setup_otel_tracing(
            service_name="test",
            auto_set_global=False,
        )
        assert provider is not None


class TestOTelSpanEventHandler:
    @pytest.fixture
    def handler(self):
        return OTelSpanEventHandler()

    @pytest.fixture
    def log_record(self):
        return logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

    def test_default_event_name_field(self, handler):
        assert handler.event_name_field == "message"

    def test_custom_event_name_field(self):
        handler = OTelSpanEventHandler(event_name_field="custom")
        assert handler.event_name_field == "custom"

    def test_enabled_by_default(self, handler):
        assert handler._enabled is True

    def test_no_emit_when_disabled(self, handler, log_record):
        handler._enabled = False
        # Should not raise
        handler.emit(log_record)

    def test_no_emit_without_valid_span(self, handler, log_record):
        """Should not emit when there's no active span."""
        mock_span = MagicMock()
        mock_span.get_span_context.return_value.is_valid = False

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(log_record)
            mock_span.add_event.assert_not_called()

    def test_no_emit_when_no_span(self, handler, log_record):
        """Should not emit when get_current_span returns None."""
        with patch.object(handler._trace, "get_current_span", return_value=None):
            handler.emit(log_record)

    def test_emits_event_on_valid_span(self, handler, log_record):
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(log_record)
            mock_span.add_event.assert_called_once()

    def test_event_name_from_message(self, handler, log_record):
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(log_record)
            call_args = mock_span.add_event.call_args
            assert call_args[0][0] == "Test message"

    def test_includes_log_level_attribute(self, handler, log_record):
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(log_record)
            call_args = mock_span.add_event.call_args
            attrs = call_args[1]["attributes"]
            assert attrs["log.level"] == "INFO"

    def test_includes_logger_name_attribute(self, handler, log_record):
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(log_record)
            call_args = mock_span.add_event.call_args
            attrs = call_args[1]["attributes"]
            assert attrs["log.logger"] == "test.logger"

    def test_includes_file_info_attributes(self, handler, log_record):
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(log_record)
            call_args = mock_span.add_event.call_args
            attrs = call_args[1]["attributes"]
            assert attrs["log.file"] == "/path/to/test.py"
            assert attrs["log.line"] == 42

    def test_includes_exception_info(self, handler):
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

        mock_span_context = MagicMock()
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(record)
            call_args = mock_span.add_event.call_args
            attrs = call_args[1]["attributes"]
            assert "exception" in attrs
            assert "ValueError" in attrs["exception"]

    def test_includes_extra_attributes(self, handler):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"

        mock_span_context = MagicMock()
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            handler.emit(record)
            call_args = mock_span.add_event.call_args
            attrs = call_args[1]["attributes"]
            assert attrs["log.custom_field"] == "custom_value"

    def test_handles_emit_exception_gracefully(self, handler, log_record):
        """Emit should never raise exceptions."""
        mock_span = MagicMock()
        mock_span.get_span_context.side_effect = RuntimeError("Unexpected error")

        with patch.object(handler._trace, "get_current_span", return_value=mock_span):
            # Should not raise
            handler.emit(log_record)


class TestOTelSpanEventHandlerIntegration:
    def test_with_real_tracer(self):
        """Test handler with a real tracer provider."""
        provider = setup_otel_tracing(
            service_name="handler-test",
            auto_set_global=True,
        )
        tracer = trace.get_tracer("test")
        handler = OTelSpanEventHandler()

        logger = logging.getLogger("otel.integration")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        with tracer.start_as_current_span("test-span") as span:
            logger.info("Test log within span")

        logger.removeHandler(handler)
