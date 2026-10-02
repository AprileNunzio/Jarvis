import json
import re

import httpx
from config import ollama_url

from features.brain.brains import brains
from features.brain.residency import keep_alive
from features.cloud.catalog import is_cloud
from features.cloud.client import CloudError, complete

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


class BrainUnavailable(RuntimeError):
    pass


async def chain(kind: str = "deep") -> list[str]:
    cfg = brains.config()
    installed = {n if ":" in n else f"{n}:latest" for n in await brains.installed()}
    order = cfg[kind] + cfg["deep" if kind == "chat" else "chat"]
    usable = [m for m in dict.fromkeys(order) if brains.usable(m, installed)]
    return usable or [cfg["main"]]


def decode(text: str, as_json: bool):
    if not as_json:
        return text.strip()
    body = _FENCE.sub("", text.strip())
    start, end = body.find("{"), body.rfind("}")
    return json.loads(body[start:end + 1] if start >= 0 and end > start else body)


async def _ollama(model: str, prompt: str, system: str, as_json: bool, max_tokens: int, temperature: float,
                  timeout: float) -> str:
    body = {"model": model, "prompt": prompt, "stream": False, "keep_alive": keep_alive(model),
            "options": {"temperature": temperature, "num_predict": max_tokens}}
    if system:
        body["system"] = system
    if as_json:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10)) as client:
        r = await client.post(f"{ollama_url()}/api/generate", json=body)
        r.raise_for_status()
    return r.json().get("response", "")


def _govern(system: str) -> str:
    try:
        from features.laws.laws import laws
        preamble = laws.preamble()
    except Exception:
        preamble = ""
    return (preamble + "\n\n" + system) if preamble else system


async def generate(prompt: str, *, as_json: bool = False, max_tokens: int = 500, temperature: float = 0.1,
                   kind: str = "deep", system: str = "", prefer: list[str] | None = None, timeout: float = 240,
                   govern: bool = True):
    if govern:
        system = _govern(system)
    errors = []
    models = list(dict.fromkeys([m for m in prefer or [] if m] + await chain(kind)))
    for model in models:
        try:
            if is_cloud(model):
                reply = await complete(model, [{"role": "user", "content": prompt}], system, max_tokens=max_tokens,
                                       temperature=temperature, json_mode=as_json)
                text = reply.text
            else:
                text = await _ollama(model, prompt, system, as_json, max_tokens, temperature, timeout)
            return decode(text, as_json)
        except (httpx.HTTPError, CloudError, ValueError) as exc:
            errors.append(f"{model}: {str(exc)[:120]}")
    raise BrainUnavailable("; ".join(errors) or "nessun modello disponibile")
