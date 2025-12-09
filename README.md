# ume-logging

Uniform JSON logging for **University Medicine Essen** applications.

A consistent logging standard across multiple languages, designed for microservices running in Docker/Kubernetes with ELK stack integration.

## Implementations

| Language | Package | Status |
|----------|---------|--------|
| [Python](./python) | [`ume-logging`](https://pypi.org/project/ume-logging/) | ✅ Available |
| Scala | — | 🚧 Planned |
| Rust | — | 🚧 Planned |

## Why?

When running microservices written in different languages, you need consistent log output for:

- **Centralized logging** — Parse logs uniformly in ELK/Loki/CloudWatch
- **Request tracing** — Correlate logs across services with `request_id`
- **Debugging** — Know which app/service/environment produced each log
- **Compliance** — Automatic PII scrubbing and user ID hashing

## Standard Log Format

All implementations produce JSON logs with this structure:

```json
{
  "time": "2025-01-15T10:30:00.000Z",
  "level": "INFO",
  "logger": "my.module",
  "message": "Processing complete",
  "org": "UME",
  "app": "patient-api",
  "env": "prod",
  "service": "fhir-import",
  "component": "parser",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user": {
    "hash": "a1b2c3d4e5f6..."
  },
  "trace_id": "0af7651916cd43dd8448eb211c80319c",
  "span_id": "b7ad6b7169203331"
}
```

## Common Features

All implementations provide:

| Feature | Description |
|---------|-------------|
| **JSON output** | Single-line JSON to stdout |
| **Context fields** | `app`, `env`, `service`, `component` in every log |
| **Request ID** | `X-Request-ID` header propagation |
| **User hashing** | SHA256 hash of user identifiers |
| **PII scrubbing** | Redact emails and phone numbers |
| **OpenTelemetry** | Inject `trace_id` and `span_id` when available |

## Environment Variables

Standard across all implementations:

| Variable | Description | Default |
|----------|-------------|---------|
| `UME_LOG_LEVEL` | Logging level | `INFO` |
| `UME_APP` | Application name | — |
| `UME_ENV` | Environment | `prod` |
| `UME_SERVICE` | Service name | — |
| `UME_COMPONENT` | Component name | — |
| `UME_USER_HASH_SALT` | Salt for user ID hashing | `ume` |

## Getting Started

### Python

```bash
pip install ume-logging
```

```python
import logging
from umelogging import log_configure

log_configure("INFO", app="my-app", env="prod")
logging.getLogger(__name__).info("Hello from Python")
```

See [python/README.md](./python/README.md) for full documentation.

## License

MIT License — Copyright © University Medicine Essen
