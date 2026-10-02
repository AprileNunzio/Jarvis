import asyncio

import httpx

from features.cloud.catalog import BY_ID, FLAVORS, Provider
from features.cloud.client import CloudError, endpoint, headers
from features.cloud.models import _ids
from features.cloud.vault import vault


def addresses(flavor: str, url: str) -> tuple[str, str]:
    root = str(url or "").strip().rstrip("/")
    if not root:
        raise ValueError("Indirizzo mancante")
    if not root.startswith(("http://", "https://")):
        root = f"http://{root}"
    host = root.split("//", 1)[1].split("/", 1)[0]
    if flavor == "ollama":
        root = root.removesuffix("/v1")
        if ":" not in host:
            root += ":11434"
        return root, f"{root}/v1"
    return root, root if root.endswith("/v1") else f"{root}/v1"


async def probe(flavor: str, base_url: str, key: str = "") -> list[str]:
    spec = Provider("probe", "Server", "", needs_url=True, key_optional=True)
    entry = {"base_url": base_url, "key": key}
    async with httpx.AsyncClient(timeout=8) as client:
        res = await client.get(f"{endpoint(spec, entry)}/models", headers=headers(spec, entry))
    if res.status_code >= 400:
        raise CloudError(f"{res.status_code}: {res.text[:160]}")
    return sorted(set(_ids(res.json())))


async def test(flavor: str, url: str, key: str = "") -> dict:
    if flavor not in FLAVORS:
        return {"ok": False, "error": "Tipo di server sconosciuto"}
    try:
        root, base = addresses(flavor, url)
        models = await probe(flavor, base, key)
    except (httpx.HTTPError, CloudError, ValueError) as exc:
        hint = " — sul server avvia Ollama con OLLAMA_HOST=0.0.0.0" if flavor == "ollama" else ""
        return {"ok": False, "error": f"non raggiungibile ({str(exc)[:120] or type(exc).__name__}){hint}"}
    return {"ok": True, "root": root, "base_url": base, "models": models}


async def _row(pid: str, entry: dict) -> dict:
    row = {"id": pid, "name": entry.get("name", pid), "flavor": entry.get("flavor", "ollama"),
           "url": entry.get("root", ""), "has_key": bool(entry.get("key")), "models": [], "error": ""}
    try:
        row["models"] = await probe(row["flavor"], entry.get("base_url", ""), entry.get("key", ""))
    except (httpx.HTTPError, CloudError, ValueError) as exc:
        row["error"] = f"non raggiungibile ({str(exc)[:120] or type(exc).__name__})"
    row["online"] = not row["error"]
    return row


async def overview() -> list[dict]:
    return list(await asyncio.gather(*(_row(pid, e) for pid, e in vault.servers().items())))


def known(pid: str) -> bool:
    return pid in BY_ID and pid in vault.servers()
