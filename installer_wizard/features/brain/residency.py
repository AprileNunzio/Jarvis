import httpx
from config import DEMO, ollama_remote, ollama_url, read_env

from features.brain.brains import brains, norm
from features.cloud.catalog import is_cloud
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
    main = primary()
    return PINNED if main and norm(model) == norm(main) else TRANSIENT


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
                if name == embed or (main and name == norm(main)):
                    continue
                await client.post(f"{ollama_url()}/api/generate", json={"model": name, "keep_alive": 0})
                store.event("INFO", f"Modello {name} scaricato dalla memoria (non più in uso)", "models")
            if main:
                await client.post(f"{ollama_url()}/api/generate", json={"model": main, "keep_alive": PINNED})
    except (httpx.HTTPError, ValueError) as exc:
        store.event("WARN", f"Riallineamento dei modelli in memoria non riuscito: {exc}", "models")
