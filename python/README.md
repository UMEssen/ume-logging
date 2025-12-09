# ume-logging

<p align="left">
  <a href="https://pypi.org/project/ume-logging/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/ume-logging?color=blue">
  </a>
  <a href="https://pypi.org/project/ume-logging/">
    <img alt="Python Versions" src="https://img.shields.io/pypi/pyversions/ume-logging">
  </a>
  <a href="https://github.com/UMEssen/ume-logging/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/UMEssen/ume-logging">
  </a>
</p>

Uniform JSON logging for **University Medicine Essen** applications. Designed for microservices running in Docker/Kubernetes with ELK stack integration.

## Features

- **Structured JSON output** — Machine-readable logs for ELK/Loki/CloudWatch
- **Context injection** — Automatically include app, env, service, request ID in every log
- **Request tracing** — Track requests across services with `X-Request-ID` propagation
- **PII scrubbing** — Automatically redact emails and phone numbers from logs
- **OpenTelemetry integration** — Trace/span IDs in logs + log→span event bridge
- **FastAPI middleware** — Request/response logging with latency tracking
- **User privacy** — Hash user identifiers with configurable salt

## Installation

```bash
pip install ume-logging

# With FastAPI support
pip install "ume-logging[fastapi]"

# With OpenTelemetry support
pip install "ume-logging[otel]"

# Everything
pip install "ume-logging[fastapi,otel]"
```

## Quick Start

```python
import logging
from umelogging import log_configure

log_configure("INFO", app="patient-api", env="prod", service="fhir-import")

log = logging.getLogger(__name__)
log.info("Processing patient records", extra={"count": 42})
```

**Output:**
```json
{"time":"2025-01-15T10:30:00","level":"INFO","logger":"__main__","message":"Processing patient records","org":"UME","app":"patient-api","env":"prod","service":"fhir-import","count":42}
```

## Context Management

Track requests and users across your application:

```python
from umelogging import set_context, with_request_id

# Set request ID (or auto-generate with with_request_id())
with_request_id("req-abc-123")

# Track user (automatically hashed for privacy)
set_context(user_id="patient@example.com", component="auth")

# Add custom context
set_context(extra={"tenant": "hospital-a", "study_id": "ST001"})
```

All subsequent logs will include this context:
```json
{"message":"User authenticated","request_id":"req-abc-123","user":{"hash":"a1b2c3..."},"component":"auth","tenant":"hospital-a"}
```

## PII Scrubbing

Emails and phone numbers are automatically redacted:

```python
log.info("Contact: john.doe@hospital.com, Phone: +49 201 723-0")
# Output: "Contact: [email], Phone: [phone]"
```

## FastAPI Integration

```python
from fastapi import FastAPI
from umelogging import log_configure, UMERequestLoggerMiddleware

log_configure("INFO", app="my-api", env="prod")

app = FastAPI()
app.add_middleware(UMERequestLoggerMiddleware)

@app.get("/patients/{id}")
async def get_patient(id: str):
    return {"id": id}
```

Every request logs:
```json
{"message":"request.start","method":"GET","path":"/patients/123","request_id":"550e8400-..."}
{"message":"request.end","status":200,"duration_ms":45,"request_id":"550e8400-..."}
```

The middleware:
- Extracts `X-Request-ID` from headers (or generates UUID)
- Returns `X-Request-ID` in response headers
- Measures request latency
- Sets `component` context to `"http"`

## OpenTelemetry Integration

### Add Trace IDs to Logs

When OpenTelemetry is configured, trace and span IDs are automatically added to every log:

```json
{"message":"Processing","trace_id":"0af7651916cd43dd8448eb211c80319c","span_id":"b7ad6b7169203331"}
```

### Setup Tracing

```python
from umelogging.otel.handler import setup_otel_tracing

setup_otel_tracing(
    service_name="patient-api",
    otlp_endpoint="http://otel-collector:4318",
    sampling_ratio=0.1,  # Sample 10% of traces
)
```

### Mirror Logs to Span Events

Attach logs as events on the current trace span:

```python
import logging
from umelogging.otel.handler import OTelSpanEventHandler

logging.getLogger().addHandler(OTelSpanEventHandler())
```

## Environment Variables

### Core Configuration

| Variable             | Description                   | Default |
|----------------------|-------------------------------|---------|
| `UME_LOG_LEVEL`      | Logging level                 | `INFO`  |
| `UME_APP`            | Application name              |         |
| `UME_ENV`            | Environment (prod/dev/test)   | `prod`  |
| `UME_SERVICE`        | Service name                  |         |
| `UME_COMPONENT`      | Component/module name         |         |
| `UME_USER_HASH_SALT` | Salt for user ID hashing      | `ume`   |

### OpenTelemetry Configuration

| Variable                       | Description                | Default                 |
|--------------------------------|----------------------------|-------------------------|
| `OTEL_SERVICE_NAME`            | Service name for traces    | `ume-service`           |
| `OTEL_EXPORTER_OTLP_ENDPOINT`  | Collector endpoint         | `http://localhost:4318` |
| `OTEL_EXPORTER_OTLP_HEADERS`   | Headers (`key=val,k2=v2`)  |                         |
| `OTEL_TRACES_SAMPLER_ARG`      | Sampling ratio (0.0-1.0)   | `1.0`                   |

## API Reference

### `log_configure(level, *, app, env, service, component, stream, static_fields, propagate_existing)`

Configure the root logger with JSON formatting and PII filtering.

### `set_context(*, app, env, service, component, request_id, user_id, extra)`

Set context variables that are included in all subsequent logs.

### `with_request_id(request_id=None) -> str`

Set or generate a request ID. Returns the ID.

### `get_context() -> dict`

Get current context as a dictionary.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## License

MIT License — Copyright © University Medicine Essen
