# UME Logging (`logging-ume`)

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
  <!-- Optionally add CI badge:
  <a href="https://github.com/UMEssen/ume-logging/actions">
    <img alt="CI" src="https://github.com/UMEssen/ume-logging/actions/workflows/ci.yml/badge.svg">
  </a>
  -->
</p>

Uniform JSON logging for **University Medicine Essen** applications.  

---

## Features

- JSON log output (Docker/K8s/ELK friendly)
- App/env/service/request context injection
- PII scrubbing (emails, numeric IDs, phone numbers)
- OpenTelemetry trace/span IDs in logs
- Optional log→OTel span event bridge
- FastAPI middleware for request/response logging
- Compatible with Python 3.9+

---

## 📦 Installation

```bash
pip install ume-logging
# Optional extras:
pip install "ume-logging[fastapi]"   # FastAPI request logging middleware
pip install "ume-logging[otel]"      # OpenTelemetry tracing + span events
```

---

## 🚀 Quickstart

```python
import logging
from umelogging import log_configure

log_configure("INFO", app="dicom2fhir", env="prod", service="mapping")
log = logging.getLogger(__name__)

log.info("Starting dicom-to-fhir mapping job.")
```

### Example Output (JSON):

```json
{
  "time": "2025-08-12T12:01:23.456Z",
  "level": "INFO",
  "logger": "myapp",
  "message": "Starting dicom-to-fhir mapping job.",
  "org": "UME",
  "app": "dicom2fhir",
  "env": "prod",
  "service": "mapping"
}
```

---

## ⚙️ Environment Variables

| Variable                | Description                          | Default  |
|-------------------------|--------------------------------------|----------|
| `UME_LOG_LEVEL`         | Logging level                       | `INFO`   |
| `UME_APP`               | App name                            |          |
| `UME_ENV`               | Environment (prod, dev, test)       | `prod`   |
| `UME_SERVICE`           | Service name                        |          |
| `UME_COMPONENT`         | Component/module name               |          |
| `UME_USER_HASH_SALT`    | Salt for user ID hashing            | `ume`    |
| `UME_OTEL_SPAN_EVENTS`  | Mirror logs as OTel span events     | `false`  |

---

## 🌐 FastAPI Integration (optional)

Add request/response logging to your FastAPI app:

```python
from fastapi import FastAPI
from umelogging.fastapi.middleware import UMELoggingMiddleware

app = FastAPI()
app.add_middleware(UMELoggingMiddleware)
```

This will log incoming requests and responses in JSON, including request ID, latency, status, and correlation information.

---

## 📈 OpenTelemetry Integration (optional)

Enable OpenTelemetry tracing and span events in your logs:

```python
from umelogging import log_configure

log_configure(
    "INFO",
    app="myapp",
    env="prod",
    otel_enable=True,  # Enable OpenTelemetry
    otel_exporter="otlp",  # or "console"
)
```

Configure via environment variables:

| Variable                     | Description                       | Example             |
|------------------------------|-----------------------------------|---------------------|
| `UMELOG_OTEL_ENABLE`         | Enable OTel tracing/log bridge    | `true`              |
| `UMELOG_OTEL_EXPORTER`       | OTel exporter ("otlp", "console") | `otlp`             |
| `OTEL_EXPORTER_OTLP_ENDPOINT`| OTel collector endpoint           | `http://otel:4317`  |

See [OpenTelemetry Docs](https://opentelemetry.io/docs/) for advanced setup.

---

## 📄 License

MIT License.  
Copyright © University Medicine Essen ZIT / IKIM.
