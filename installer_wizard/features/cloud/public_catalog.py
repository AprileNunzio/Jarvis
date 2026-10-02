import asyncio
import json
import re
import time

import httpx

from config import STATE_DIR

CATALOG_URL = "https://openrouter.ai/api/v1/models"
CACHE_FILE = STATE_DIR / "cloud_public_catalog.json"
TTL = 6 * 3600
NATIVE = {"openai": "openai", "google": "gemini", "anthropic": "anthropic", "x-ai": "xai", "mistralai": "mistral",
          "cohere": "cohere", "deepseek": "deepseek", "qwen": "qwen", "moonshotai": "moonshot", "z-ai": "zhipu",
          "perplexity": "perplexity"}
_TEXT_OUT = re.compile(r"->text$")
_state: dict = {"at": 0.0, "rows": []}
_lock = asyncio.Lock()


def _native_id(owner: str, slug: str) -> str:
    if owner == "anthropic":
        return re.sub(r"(?<=\d)\.(?=\d)", "-", slug)
    return slug


def _price(value) -> float | None:
    try:
        return round(float(value) * 1_000_000, 3)
    except (TypeError, ValueError):
        return None


def _row(m: dict) -> dict | None:
    arch = m.get("architecture") or {}
    if not _TEXT_OUT.search(arch.get("modality", "")):
        return None
    pricing = m.get("pricing") or {}
    return {
        "id": m["id"],
        "name": m.get("name") or m["id"],
        "created": m.get("created") or 0,
        "context": m.get("context_length") or 0,
        "price_in": _price(pricing.get("prompt")),
        "price_out": _price(pricing.get("completion")),
        "vision": "image" in (arch.get("input_modalities") or []),
        "reasoning": "reasoning" in (m.get("supported_parameters") or []),
    }


def _load_cache() -> None:
    if _state["rows"] or not CACHE_FILE.exists():
        return
    data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    _state.update(at=data.get("at", 0.0), rows=data.get("rows", []))


async def refresh(force: bool = False) -> list[dict]:
    async with _lock:
        _load_cache()
        if force and time.time() - _state["at"] < 60 or not force and time.time() - _state["at"] < TTL:
            if _state["rows"]:
                return _state["rows"]
        return await _download()


async def _download() -> list[dict]:
    async with httpx.AsyncClient(timeout=25, headers={"User-Agent": "Jarvis-OS"}) as client:
        res = await client.get(CATALOG_URL)
        res.raise_for_status()
    rows = [r for r in (_row(m) for m in res.json().get("data", [])) if r]
    rows.sort(key=lambda r: -r["created"])
    _state.update(at=time.time(), rows=rows)
    CACHE_FILE.write_text(json.dumps(_state, ensure_ascii=False), encoding="utf-8")
    return rows


def cached() -> list[dict]:
    try:
        _load_cache()
    except (OSError, ValueError):
        return []
    return _state["rows"]


def for_provider(pid: str, rows: list[dict]) -> list[dict]:
    if pid == "openrouter":
        return [{**r, "model": r["id"]} for r in rows]
    out, seen = [], set()
    for r in rows:
        owner, _, slug = r["id"].partition("/")
        if NATIVE.get(owner) != pid or ":" in slug:
            continue
        model = _native_id(owner, slug)
        if model not in seen:
            seen.add(model)
            out.append({**r, "model": model})
    return out
