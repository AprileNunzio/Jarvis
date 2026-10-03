import hashlib
import hmac
import time

from access import is_local
from config import read_env
from fastapi import APIRouter, HTTPException, Request

from features.brain.trace import trace
from features.cloud.catalog import is_cloud
from features.cloud.client import CloudError, complete

SIGNATURE_HEADER = "X-Jarvis-Signature"
TIMESTAMP_HEADER = "X-Jarvis-Timestamp"
MAX_SKEW_SECONDS = 30
MAX_BODY_BYTES = 256 * 1024
COMPLETE_PATH = "/api/internal/brain/complete"
TRACE_PATH = "/api/internal/brain/trace"
_MAX_EXTERNAL = 512

admin_routes = APIRouter()
_external: dict[str, int] = {}


def sign(key: str, method: str, path: str, timestamp: int, body: bytes) -> str:
    message = b"\n".join([method.upper().encode(), path.encode(), str(timestamp).encode(), hashlib.sha256(body).digest()])
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify(key: str, method: str, path: str, timestamp: int, body: bytes, signature: str, now: float) -> bool:
    if not key.strip("0") or abs(now - timestamp) > MAX_SKEW_SECONDS:
        return False
    return hmac.compare_digest(sign(key, method, path, timestamp, body), signature)


async def _authorised(request: Request, path: str) -> bytes:
    if not is_local(request):
        raise HTTPException(403, "Consentito solo in locale")
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(413, "Richiesta troppo grande")
    try:
        stamp = int(request.headers.get(TIMESTAMP_HEADER, ""))
    except ValueError:
        raise HTTPException(401, "Firma mancante")
    key = read_env().get("JARVIS_SECRET_KEY", "")
    if not verify(key, request.method, path, stamp, body, request.headers.get(SIGNATURE_HEADER, ""), time.time()):
        raise HTTPException(401, "Firma non valida")
    return body


@admin_routes.post(COMPLETE_PATH)
async def bridge_complete(request: Request):
    import json
    data = json.loads(await _authorised(request, COMPLETE_PATH) or b"{}")
    ref = str(data.get("ref") or "")
    if not is_cloud(ref):
        raise HTTPException(400, "Riferimento non valido")
    try:
        reply = await complete(ref, list(data.get("messages") or []), str(data.get("system") or ""),
                               max_tokens=int(data.get("max_tokens") or 800), temperature=data.get("temperature"),
                               json_mode=bool(data.get("json")))
    except (CloudError, ValueError) as exc:
        raise HTTPException(502, str(exc)[:240])
    from features.brain.residency import touch
    from tasks import background
    background(touch(ref))
    return {"text": reply.text, "model": reply.model, "ms": reply.ms, "tokens": reply.tokens}


@admin_routes.post(TRACE_PATH)
async def bridge_trace(request: Request):
    import json
    data = json.loads(await _authorised(request, TRACE_PATH) or b"{}")
    key, op = str(data.get("call") or "")[:64], str(data.get("op") or "")
    if not key:
        raise HTTPException(400, "Evento non valido")
    if op == "begin":
        if len(_external) >= _MAX_EXTERNAL:
            _external.pop(next(iter(_external)))
        _external[key] = trace.begin(str(data.get("component") or "")[:64], str(data.get("note") or "")[:200],
                                     [str(r)[:160] for r in (data.get("chain") or [])][:12])
        return {"ok": True}
    call = _external.get(key)
    if call is None:
        return {"ok": False}
    ref = str(data.get("ref") or "")[:160]
    if op == "attempt":
        trace.attempt(call, ref)
    elif op == "failed":
        trace.failed(call, ref, str(data.get("reason") or "")[:120])
    elif op == "done":
        trace.finish(call, ref, float(data.get("ms") or 0), str(data.get("snippet") or ""))
        _external.pop(key, None)
    elif op == "abort":
        trace.abort(call, str(data.get("reason") or "")[:160])
        _external.pop(key, None)
    return {"ok": True}
