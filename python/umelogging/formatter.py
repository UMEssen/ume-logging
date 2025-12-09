# Purpose: Structured JSON formatter with safe datetime handling

import logging, json
from typing import Any, Dict, Union
from datetime import datetime
from dateutil.parser import parse
import pytz

def _try_parse_datetime(s: str) -> Union[datetime, str]:
    try:
        return parse(s)
    except (ValueError, TypeError, OverflowError):
        for fmt in ("%Y%m%d%H%M%S.%f", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                pass
    return s

def _datetime_hook(obj: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in obj.items():
        if isinstance(v, str):
            dt = _try_parse_datetime(v)
            obj[k] = dt if isinstance(dt, datetime) else v
    return obj

class _DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

def safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj, cls=_DateTimeEncoder, separators=(",", ":"), ensure_ascii=False)

def parse_timezone(tz_name: str) -> pytz.BaseTzInfo:
    try:
        return pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        return pytz.UTC

class JsonFormatter(logging.Formatter):
    # Purpose: emit ECS-ish JSON with UME context, OTEL trace, and exception details
    def __init__(self, *, static_fields: Dict[str, Any] | None = None):
        super().__init__()
        self.static = static_fields or {}

        # Opentelemetry optional
        try:
            from opentelemetry import trace as _trace  # type: ignore
            self._tracer = _trace
        except ImportError:
            self._tracer = None

    def format(self, record: logging.LogRecord) -> str:
        from .context import get_context  # local import avoids cycle

        ctx = get_context()
        base = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **self.static,
            **{k: v for k, v in ctx.items() if v is not None},
        }

        # OTEL trace/span ids if available
        if self._tracer:
            span = self._tracer.get_current_span()
            if span and span.get_span_context().is_valid:
                sc = span.get_span_context()
                base["trace_id"] = f"{sc.trace_id:032x}"
                base["span_id"] = f"{sc.span_id:016x}"

        if record.exc_info:
            base["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            base["stack"] = self.formatStack(record.stack_info)

        return safe_json_dumps(base)