# Purpose: OpenTelemetry setup (traces) and logging->span event bridge handler

from __future__ import annotations
import logging, os
from typing import Optional, Dict, Any
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased, ParentBased
from opentelemetry import trace as _trace  # local alias

def setup_otel_tracing(
    *,
    service_name: str,
    resource_attrs: Optional[Dict[str, Any]] = None,
    otlp_endpoint: Optional[str] = None,
    otlp_headers: Optional[Dict[str, str]] = None,
    sampling_ratio: float = 1.0,
    auto_set_global: bool = True,
) -> "TracerProvider":
    """
    Configure OTel tracing with OTLP/HTTP exporter.
    Honors env if args not passed:
      OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_HEADERS, OTEL_SERVICE_NAME, OTEL_TRACES_SAMPLER_ARG
    """

    # Build Resource
    svc = service_name or os.getenv("OTEL_SERVICE_NAME") or "ume-service"
    res = Resource.create({"service.name": svc, **(resource_attrs or {})})

    # Sampler
    ratio = sampling_ratio
    try:
        ratio = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", str(sampling_ratio)))
    except Exception:
        pass
    sampler = ParentBased(TraceIdRatioBased(ratio))

    provider = TracerProvider(resource=res, sampler=sampler)

    # Exporter
    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or "http://localhost:4318"
    headers = otlp_headers or _parse_headers(os.getenv("OTEL_EXPORTER_OTLP_HEADERS"))
    exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers)

    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)

    if auto_set_global:
        trace.set_tracer_provider(provider)

    return provider


def _parse_headers(hdrs: Optional[str]) -> Optional[Dict[str, str]]:
    # "k1=v1,k2=v2"
    if not hdrs:
        return None
    out: Dict[str, str] = {}
    for kv in hdrs.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class OTelSpanEventHandler(logging.Handler):
    """
    Logging handler that attaches log records as events on the current span.
    Preserves normal stdout JSON logging; use in addition to your StreamHandler.
    """

    def __init__(self, *, event_name_field: str = "message"):
        super().__init__()
        self.event_name_field = event_name_field
        self._enabled = True
        self._trace = _trace

    def emit(self, record: logging.LogRecord) -> None:
        if not self._enabled or not self._trace:
            return
        try:
            span = self._trace.get_current_span()
            if not span or not span.get_span_context().is_valid:
                return
            attrs = {
                "log.level": record.levelname,
                "log.logger": record.name,
                "log.module": record.module,
                "log.file": getattr(record, "pathname", None),
                "log.line": getattr(record, "lineno", None),
            }
            # Include extra dict if present
            if hasattr(record, "__dict__"):
                for k, v in record.__dict__.items():
                    if k not in ("args", "msg", "name", "levelname", "levelno", "pathname",
                                 "filename", "module", "exc_info", "exc_text", "stack_info",
                                 "lineno", "funcName", "created", "msecs", "relativeCreated",
                                 "thread", "threadName", "processName", "process"):
                        attrs[f"log.{k}"] = v

            if record.exc_info:
                attrs["exception"] = logging.Formatter().formatException(record.exc_info)

            event_name = getattr(record, self.event_name_field, None) or record.getMessage()
            span.add_event(event_name, attributes=attrs)
        except Exception:
            # never raise from logging
            pass