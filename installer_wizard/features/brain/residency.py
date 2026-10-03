import httpx
from config import DEMO, ollama_remote, ollama_url, read_env

from features.brain.brains import brains, norm
from features.brain.keepalive import keep_alive_policy
from features.cloud.catalog import is_cloud, parse_ref
from features.cloud.vault import vault
from state import store

PINNED = "24h"
TRANSIENT = "5m"


def primary() -> str | None:
    cfg = brains.config()
    for model in cfg["chat"] + cfg["deep"]:
        if not is_cloud(model):
            return model
    return None


def embed_model() -> str:
    return read_env().get("JARVIS_EMBED_MODEL") or "nomic-embed-text"


def keep_alive(model: str) -> str:
    chosen = keep_alive_policy.get(model)
    if chosen:
        return chosen
    main = primary()
    return PINNED if main and norm(model) == norm(main) else TRANSIENT


def _kept(name: str) -> bool:
    return any(norm(ref) == norm(name) for ref in keep_alive_policy.overrides())


async def touch(ref: str) -> None:
    if DEMO or not is_cloud(ref):
        return
    chosen = keep_alive_policy.get(ref)
    try:
        provider, model = parse_ref(ref)
    except ValueError:
        return
    entry = vault.servers().get(provider)
    if not chosen or not entry or entry.get("flavor") != "ollama":
        return
    headers = {"Authorization": f"Bearer {entry['key']}"} if entry.get("key") else {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=5)) as client:
            await client.post(f"{entry['root']}/api/generate", json={"model": model, "keep_alive": chosen}, headers=headers)
    except httpx.HTTPError:
        return


async def apply(ref: str) -> None:
    if DEMO:
        return
    if is_cloud(ref):
        await touch(ref)
        return
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10)) as client:
            await client.post(f"{ollama_url()}/api/generate", json={"model": ref, "keep_alive": keep_alive(ref)})
    except httpx.HTTPError as exc:
        store.event("WARN", f"Impossibile mantenere {ref} in memoria: {exc}", "models")


async def loaded() -> list[str]:
    async with httpx.AsyncClient(timeout=5) as client:
        return [m.get("name", "") for m in (await client.get(f"{ollama_url()}/api/ps")).json().get("models", [])]


async def rebalance() -> None:
    if DEMO:
        return
    main, embed = primary(), norm(embed_model())
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as client:
            for name in [] if ollama_remote() else await loaded():
                if name == embed or (main and name == norm(main)) or _kept(name):
                    continue
                await client.post(f"{ollama_url()}/api/generate", json={"model": name, "keep_alive": 0})
                store.event("INFO", f"Modello {name} scaricato dalla memoria (non più in uso)", "models")
            if main:
                await client.post(f"{ollama_url()}/api/generate", json={"model": main, "keep_alive": keep_alive(main)})
    except (httpx.HTTPError, ValueError) as exc:
        store.event("WARN", f"Riallineamento dei modelli in memoria non riuscito: {exc}", "models")
