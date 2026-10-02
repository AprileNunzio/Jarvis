import base64
import re

import httpx
from config import ollama_url

from features.brain.brains import brains
from features.brain.llm import BrainUnavailable, decode, chain
from features.cloud import public_catalog
from features.cloud.catalog import BY_ID, is_cloud, parse_ref
from features.cloud.client import CloudError, complete

VISION_FAMILIES = re.compile(r"gpt-4o|gpt-4\.1|gpt-5|o3|o4|claude-(?:3|sonnet|opus|haiku)|claude-.*-4|gemini|pixtral|"
                             r"mistral-(?:medium|small)-(?:2505|3)|llama-?3\.2.*vision|llama-4|qwen.*vl|grok-(?:2-vision|4)|"
                             r"glm-4\.?\d*v|kimi.*vl", re.I)
LOCAL_VISION = re.compile(r"llava|bakllava|moondream|llama3\.2-vision|qwen2\.5vl|qwen2-vl|minicpm-v|gemma3|granite3\.2-vision|"
                          r"mistral-small3", re.I)


def _cloud_vision(ref: str) -> bool:
    pid, model = parse_ref(ref)
    rows = public_catalog.for_provider(pid, public_catalog.cached())
    row = next((r for r in rows if r["model"] == model), None)
    return bool(row["vision"]) if row else bool(VISION_FAMILIES.search(model))


async def models() -> list[str]:
    ordered = await chain("deep")
    installed = await brains.installed()
    local = [m for m in installed if LOCAL_VISION.search(m)]
    return [m for m in ordered if is_cloud(m) and _cloud_vision(m)] + local


def _message(ref: str, prompt: str, jpeg: bytes) -> dict:
    data = base64.b64encode(jpeg).decode()
    pid, _ = parse_ref(ref)
    if BY_ID[pid].kind == "anthropic":
        return {"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
            {"type": "text", "text": prompt}]}
    return {"role": "user", "content": [{"type": "text", "text": prompt},
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}]}


async def _ollama(model: str, prompt: str, jpeg: bytes, as_json: bool, max_tokens: int) -> str:
    body = {"model": model, "prompt": prompt, "images": [base64.b64encode(jpeg).decode()], "stream": False,
            "options": {"temperature": 0.2, "num_predict": max_tokens}}
    if as_json:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{ollama_url()}/api/generate", json=body)
        r.raise_for_status()
    return r.json().get("response", "")


async def look(jpeg: bytes, prompt: str, *, system: str = "", as_json: bool = False, max_tokens: int = 900,
               history: list | None = None) -> tuple[object, str]:
    errors = []
    for ref in await models():
        try:
            if is_cloud(ref):
                messages = [*(history or []), _message(ref, prompt, jpeg)]
                reply = await complete(ref, messages, system, max_tokens=max_tokens, temperature=0.2, json_mode=as_json)
                text = reply.text
            else:
                text = await _ollama(ref, (system + "\n\n" if system else "") + prompt, jpeg, as_json, max_tokens)
            return decode(text, as_json), ref
        except (httpx.HTTPError, CloudError, ValueError) as exc:
            errors.append(f"{ref}: {str(exc)[:120]}")
    raise BrainUnavailable("; ".join(errors) or "nessun modello capace di vedere immagini")
