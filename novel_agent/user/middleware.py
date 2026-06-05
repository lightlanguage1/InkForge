"""Auth middleware — validates Bearer token on every request, sets user context."""
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import verify_token
from .context import set_current_user

logger = logging.getLogger(__name__)

# Paths that don't require authentication (exact prefixes or full paths)
_NO_AUTH_PATHS = {
    "/api/v1/auth/activate",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/reset-password",
}
_NO_AUTH_PREFIXES = (
    "/api/v1/log",
    "/health",
    "/docs",
    "/openapi.json",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """Extract and validate Bearer token, inject user_id into ContextVar."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path.rstrip("/")

        # Skip auth for public endpoints: exact path or prefix match
        if path in _NO_AUTH_PATHS:
            return await call_next(request)
        for prefix in _NO_AUTH_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Authorization: Bearer <token> (fetch) or ?token=<token> (EventSource)
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            token = request.query_params.get("token", "").strip()
        if not token:
            return Response(
                content='{"detail":"请先使用邀请码激活"}',
                status_code=401,
                media_type="application/json",
            )

        user_id = verify_token(token)
        if not user_id:
            return Response(
                content='{"detail":"登录已过期，请重新激活"}',
                status_code=401,
                media_type="application/json",
            )

        set_current_user(user_id)
        return await call_next(request)
