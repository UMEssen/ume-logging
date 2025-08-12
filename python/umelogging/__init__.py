# Purpose: Public API surface for UME logging
from .config import log_configure, set_context
from .fastapi.middleware import UMERequestLoggerMiddleware  # optional; fails gracefully if FastAPI absent
from .formatter import JsonFormatter
from .context import request_id_var, update_context, get_context, with_request_id

__all__ = [
    "log_configure",
    "set_context",
    "update_context",
    "get_context",
    "with_request_id",
    "UMERequestLoggerMiddleware",
    "JsonFormatter",
    "request_id_var",
]