import json
import logging
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytz

from umelogging.formatter import (
    _try_parse_datetime,
    _datetime_hook,
    _DateTimeEncoder,
    safe_json_dumps,
    parse_timezone,
    JsonFormatter,
)
from umelogging.context import set_context, extra_var, app_var, env_var, service_var, component_var, request_id_var, user_hash_var
import os


@pytest.fixture(autouse=True)
def reset_context():
    """Reset context before each test."""
    app_var.set(os.getenv("UME_APP"))
    env_var.set(os.getenv("UME_ENV", "prod"))
    service_var.set(os.getenv("UME_SERVICE"))
    component_var.set("")
    request_id_var.set("")
    user_hash_var.set("")
    extra_var.set(None)
    yield


class TestTryParseDatetime:
    def test_parses_iso_format(self):
        result = _try_parse_datetime("2024-01-15T10:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parses_iso_format_with_microseconds(self):
        result = _try_parse_datetime("2024-01-15T10:30:00.123456")
        assert isinstance(result, datetime)
        assert result.microsecond == 123456

    def test_parses_compact_format(self):
        result = _try_parse_datetime("20240115103000")
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_parses_compact_format_with_microseconds(self):
        result = _try_parse_datetime("20240115103000.123456")
        assert isinstance(result, datetime)

    def test_returns_string_on_invalid_input(self):
        result = _try_parse_datetime("not a date")
        assert result == "not a date"
        assert isinstance(result, str)

    def test_parses_dateutil_formats(self):
        result = _try_parse_datetime("January 15, 2024")
        assert isinstance(result, datetime)
        assert result.month == 1


class TestDatetimeHook:
    def test_converts_datetime_strings_in_dict(self):
        obj = {"timestamp": "2024-01-15T10:30:00", "name": "test"}
        result = _datetime_hook(obj)
        assert isinstance(result["timestamp"], datetime)
        assert result["name"] == "test"

    def test_leaves_non_datetime_strings(self):
        obj = {"message": "hello world"}
        result = _datetime_hook(obj)
        assert result["message"] == "hello world"

    def test_handles_empty_dict(self):
        result = _datetime_hook({})
        assert result == {}


class TestDateTimeEncoder:
    def test_encodes_datetime_as_iso(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        encoder = _DateTimeEncoder()
        result = encoder.default(dt)
        assert result == "2024-01-15T10:30:00"

    def test_raises_for_non_datetime(self):
        encoder = _DateTimeEncoder()
        with pytest.raises(TypeError):
            encoder.default(object())


class TestSafeJsonDumps:
    def test_serializes_dict(self):
        result = safe_json_dumps({"key": "value"})
        assert result == '{"key":"value"}'

    def test_serializes_datetime(self):
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = safe_json_dumps({"time": dt})
        assert '"2024-01-15T10:30:00"' in result

    def test_no_whitespace(self):
        result = safe_json_dumps({"a": 1, "b": 2})
        assert " " not in result

    def test_preserves_unicode(self):
        result = safe_json_dumps({"name": "über"})
        assert "über" in result


class TestParseTimezone:
    def test_parses_valid_timezone(self):
        tz = parse_timezone("America/New_York")
        assert tz.zone == "America/New_York"

    def test_parses_utc(self):
        tz = parse_timezone("UTC")
        assert tz == pytz.UTC

    def test_returns_utc_for_invalid(self):
        tz = parse_timezone("Invalid/Timezone")
        assert tz == pytz.UTC


class TestJsonFormatter:
    @pytest.fixture
    def formatter(self):
        return JsonFormatter(static_fields={"org": "UME"})

    @pytest.fixture
    def log_record(self):
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        return record

    def test_outputs_valid_json(self, formatter, log_record):
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_includes_time(self, formatter, log_record):
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert "time" in parsed

    def test_includes_level(self, formatter, log_record):
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert parsed["level"] == "INFO"

    def test_includes_logger_name(self, formatter, log_record):
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert parsed["logger"] == "test.logger"

    def test_includes_message(self, formatter, log_record):
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert parsed["message"] == "Test message"

    def test_includes_static_fields(self, formatter, log_record):
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert parsed["org"] == "UME"

    def test_includes_context_fields(self, formatter, log_record):
        set_context(app="testapp", env="test", service="testsvc")
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert parsed["app"] == "testapp"
        assert parsed["env"] == "test"
        assert parsed["service"] == "testsvc"

    def test_excludes_none_context_values(self, formatter, log_record):
        set_context(app="testapp")
        result = formatter.format(log_record)
        parsed = json.loads(result)
        # service should not be in output if None
        assert parsed.get("service") is None or "service" not in parsed or parsed["service"] is None

    def test_formats_exception(self, formatter):
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
        result = formatter.format(record)
        parsed = json.loads(result)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_formats_stack_info(self, formatter):
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error",
            args=(),
            exc_info=None,
        )
        record.stack_info = "Stack trace here"
        result = formatter.format(record)
        parsed = json.loads(result)
        assert "stack" in parsed

    def test_otel_trace_ids_when_available(self, formatter, log_record):
        """Test that trace/span IDs are included when OTel is available."""
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x1234567890ABCDEF1234567890ABCDEF
        mock_span_context.span_id = 0x1234567890ABCDEF

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        formatter._tracer = MagicMock()
        formatter._tracer.get_current_span.return_value = mock_span

        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert "trace_id" in parsed
        assert "span_id" in parsed

    def test_no_otel_fields_when_unavailable(self, log_record):
        formatter = JsonFormatter()
        formatter._tracer = None
        result = formatter.format(log_record)
        parsed = json.loads(result)
        assert "trace_id" not in parsed
        assert "span_id" not in parsed

    def test_default_static_fields_empty(self, log_record):
        formatter = JsonFormatter()
        result = formatter.format(log_record)
        parsed = json.loads(result)
        # Should still be valid JSON without org field
        assert "message" in parsed
