import time

import httpx

from features.cloud import public_catalog
from features.cloud.catalog import BY_ID
from features.cloud.client import CloudError, endpoint, headers
from features.cloud.vault import vault

_CACHE: dict[str, tuple[float, list[str]]] = {}
_TTL = 600
_SKIP = ("embed", "whisper", "tts", "dall-e", "moderation", "image", "audio", "transcribe", "realtime", "rerank",
         "search-", "guard", "vision-preview", "davinci", "babbage", "veo", "imagen", "lyria", "sora")


def _usable(name: str) -> bool:
    low = name.lower()
    return not any(s in low for s in _SKIP)


def _ids(data: dict) -> list[str]:
    rows = data.get("data") or data.get("models") or []
    out = []
    for row in rows:
        mid = row.get("id") or row.get("name") or ""
        out.append(mid.removeprefix("models/"))
    return [m for m in out if m and _usable(m)]


async def live(pid: str) -> list[str]:
    spec = BY_ID[pid]
    entry = vault.get(pid)
    url = f"{endpoint(spec, entry)}/models"
    async with httpx.AsyncClient(timeout=20) as client:
        res = await client.get(url, headers=headers(spec, entry))
    if res.status_code >= 400:
        raise CloudError(f"{spec.name} {res.status_code}: {res.text[:200]}")
    return sorted(set(_ids(res.json())))


async def _public(pid: str, refresh: bool) -> tuple[list[dict], str]:
    try:
        rows = await public_catalog.refresh(force=refresh)
    except (httpx.HTTPError, ValueError, OSError) as exc:
        return [], f"catalogo pubblico non raggiungibile: {type(exc).__name__}"
    return [r for r in public_catalog.for_provider(pid, rows) if _usable(r["model"])], ""


async def available(pid: str, refresh: bool = False) -> dict:
    spec = BY_ID[pid]
    stamp, cached = _CACHE.get(pid, (0.0, []))
    errors = []
    if vault.configured(pid) and (refresh or time.time() - stamp > _TTL):
        try:
            cached = await live(pid)
            _CACHE[pid] = (time.time(), cached)
        except (httpx.HTTPError, CloudError, ValueError) as exc:
            errors.append(str(exc)[:240])
    public, error = await _public(pid, refresh)
    if error:
        errors.append(error)
    details = {r["model"]: {k: r[k] for k in ("name", "context", "price_in", "price_out", "vision", "reasoning")}
               for r in public}
    ranked = [r["model"] for r in public]
    if cached:
        order = [m for m in ranked if m in set(cached)] + [m for m in cached if m not in details]
        source = "fornitore"
    else:
        order = ranked
        source = "catalogo pubblico" if ranked else "predefiniti"
    names = list(dict.fromkeys([*order, *([] if cached or ranked else spec.models)]))
    return {"models": names, "details": details, "source": source, "live": bool(cached), "error": "; ".join(errors)}
