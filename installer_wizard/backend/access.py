from fastapi import HTTPException, Request

import auth

NO_CACHE = {"Cache-Control": "no-store"}


def is_local(request: Request) -> bool:
    return bool(request.client) and request.client.host in ("127.0.0.1", "::1", "localhost")


def session_user(request: Request) -> str | None:
    return auth.verify(request.cookies.get(auth.SESSION_COOKIE))


def require_admin(request: Request) -> str:
    user = session_user(request)
    if not user:
        raise HTTPException(401, "Accesso richiesto")
    if request.method in ("POST", "PUT", "DELETE") and request.headers.get("X-Jarvis-Request") != "1":
        raise HTTPException(403, "Richiesta non valida")
    return user


def require_display(request: Request, message: str = "Accesso richiesto") -> None:
    if not (is_local(request) or session_user(request)):
        raise HTTPException(401, message)


def require_internal(request: Request) -> None:
    if not is_local(request) or request.headers.get("X-Jarvis-Request") != "1":
        raise HTTPException(403, "Consentito solo in locale")


def lang_of(body: dict) -> str | None:
    return str(body.get("lang") or "")[:8] or None
