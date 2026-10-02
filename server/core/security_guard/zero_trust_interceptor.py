from typing import Callable, Awaitable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from server.core.security_guard.token_provider import token_provider
from server.shared.errors.domain_errors import UnauthorizedException

class ZeroTrustMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {
        "/",
        "/health",
        "/docs",
        "/openapi.json",
        "/api/v1/auth/exchange"
    }

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.url.path in self.EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "code": "MISSING_CREDENTIALS",
                    "message": "Authorization header missing or invalid format"
                }
            )

        token = auth_header.replace("Bearer ", "").strip()
        try:
            token_claims = token_provider.verify_token(token)
            request.state.user = token_claims
        except UnauthorizedException as exc:
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "code": exc.code,
                    "message": exc.message
                }
            )

        return await call_next(request)
