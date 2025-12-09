# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ume-logging** is a Python package providing uniform JSON logging for University Medicine Essen (UME) applications. It ensures consistent, structured logging across microservices with ECS/Kubernetes/ELK stack compatibility.

Published on PyPI as `ume-logging`.

## Build Commands

All commands run from the `python/` directory:

```bash
# Build package (wheel + sdist)
cd python
python -m pip install build
rm -rf dist/ build/ *.egg-info
python -m build
```

## Architecture

The package lives in `python/umelogging/` with these core modules:

- **config.py** - `log_configure()` sets up the root logger with JSON formatting and PII filtering
- **context.py** - Thread/async-safe context variables via `contextvars` (request_id, user_hash, app, env, service, component)
- **formatter.py** - `JsonFormatter` outputs ECS-style JSON with OpenTelemetry trace/span ID injection when available
- **filters.py** - `PiiScrubberFilter` scrubs emails and phone numbers from log messages
- **fastapi/middleware.py** - `UMERequestLoggerMiddleware` logs HTTP requests with latency and request ID propagation
- **otel/handler.py** - `setup_otel_tracing()` configures OTLP export; `OTelSpanEventHandler` mirrors logs as span events

**Logging Pipeline:**
1. Standard Python logging API
2. PII scrubbing filter (emails → `[email]`, phones → `[phone]`)
3. JSON formatter adds context variables + OTel trace IDs
4. stdout output (Docker/K8s friendly)

## Key Environment Variables

| Variable | Purpose |
|----------|---------|
| `UME_LOG_LEVEL` | Logging level (default: INFO) |
| `UME_APP`, `UME_ENV`, `UME_SERVICE`, `UME_COMPONENT` | Context fields for log output |
| `UME_USER_HASH_SALT` | Salt for SHA256 user ID hashing (default: "ume") |
| `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry configuration |

## Dependencies

- **Core:** python-dateutil, pytz
- **Optional extras:** `fastapi` (for middleware), `otel` (for OpenTelemetry)

## Publishing

Automated via GitHub Actions on release (`.github/workflows/python-publish.yml`). Uses PyPI trusted publishing with OIDC.
