# Purpose: One-call configuration for consistent JSON logs across UME

import logging, os, sys
from typing import Optional, Dict, Any, List
from .formatter import JsonFormatter
from .filters import PiiScrubberFilter
from .context import set_context

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

def _level_from_env(default: str) -> int:
    lvl = os.getenv("UME_LOG_LEVEL", default).upper()
    return getattr(logging, lvl, logging.INFO)

def _build_handlers(stream: Any, static_fields: Dict[str, Any]) -> List[logging.Handler]:
    h = logging.StreamHandler(stream)
    h.setFormatter(JsonFormatter(static_fields=static_fields))
    h.addFilter(PiiScrubberFilter())
    return [h]

def log_configure(
    level: str | int = "INFO",
    *,
    app: Optional[str] = None,
    env: Optional[str] = None,
    service: Optional[str] = None,
    component: Optional[str] = None,
    stream: Any = sys.stdout,
    static_fields: Optional[Dict[str, Any]] = None,
    propagate_existing: bool = True,
) -> None:
    """
    Configure root logger + known framework loggers for JSON output.

    Env overrides:
      UME_LOG_LEVEL, UME_APP, UME_ENV, UME_SERVICE
    """
    set_context(
        app=app or os.getenv("UME_APP"),
        env=env or os.getenv("UME_ENV", "prod"),
        service=service or os.getenv("UME_SERVICE"),
        component=component or os.getenv("UME_COMPONENT"),
    )

    lvl = _level_from_env(level if isinstance(level, str) else logging.getLevelName(level))
    handlers = _build_handlers(stream, static_fields or {"org": "UME"})

    logging.basicConfig(level=lvl, handlers=handlers, force=True)

    # Align earlier-created loggers
    if propagate_existing:
        root = logging.getLogger()
        for name in list(logging.root.manager.loggerDict.keys()):
            lg = logging.getLogger(name)
            lg.setLevel(root.level)
            lg.propagate = True

    # Uvicorn alignment (if used)
    for name in _UVICORN_LOGGERS:
        lg = logging.getLogger(name)
        lg.handlers = []  # use root handlers
        lg.propagate = True

    logging.getLogger().info("Logging initialized", extra={"configured": True, "level": logging.getLevelName(lvl)})