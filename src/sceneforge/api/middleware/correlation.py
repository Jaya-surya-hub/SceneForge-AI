"""Correlation ID middleware.

Injects X-Correlation-ID on every request and response.
If the client supplies the header, it is reused; otherwise a new UUID is generated.
The correlation ID is stored in a context variable so workers and logs can access it.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from sceneforge.observability.logging import set_correlation_id

_HEADER = "X-Correlation-ID"


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        cid = request.headers.get(_HEADER) or str(uuid.uuid4())
        set_correlation_id(cid)
        response = await call_next(request)
        response.headers[_HEADER] = cid
        return response
