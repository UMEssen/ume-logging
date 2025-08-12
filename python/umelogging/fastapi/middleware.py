# Purpose: FastAPI middleware for request_id + access logging in JSON

from typing import Callable
import time, uuid, logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from ..context import with_request_id, update_context

class UMERequestLoggerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, request_id_header: str = "X-Request-ID"):
        super().__init__(app)
        self.request_id_header = request_id_header
        self.log = logging.getLogger("ume.request")

    async def dispatch(self, request: Request, call_next: Callable):
        rid = request.headers.get(self.request_id_header) or str(uuid.uuid4())
        with_request_id(rid)
        update_context(component="http")

        start = time.perf_counter()
        self.log.info("request.start", extra={"method": request.method, "path": request.url.path, "request_id": rid})
        resp = await call_next(request)
        dur_ms = int((time.perf_counter() - start) * 1000)
        resp.headers[self.request_id_header] = rid
        self.log.info(
            "request.end",
            extra={"status": resp.status_code, "duration_ms": dur_ms, "request_id": rid},
        )
        return resp