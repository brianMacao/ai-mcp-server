"""Security middleware for Web UI: optional token-based access control.

When AI_MCP_UI_TOKEN is set, every non-static request must include
?token=<token> in the URL.
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_TOKEN_ENV = "AI_MCP_UI_TOKEN"


class TokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = os.environ.get(_TOKEN_ENV)
        if not token:
            return await call_next(request)
        # Static assets do not expose local model, endpoint, or job metadata.
        if request.url.path.startswith("/static/"):
            return await call_next(request)
        provided = request.query_params.get("token") or ""
        if provided != token:
            return Response(
                "Unauthorized — append ?token=YOUR_TOKEN to the URL",
                status_code=401,
            )
        return await call_next(request)
