import time
from itertools import groupby

import httpx
from state import store
from tasks import background

from features.brain.brains import brains
from features.brain.residency import touch
from features.brain.trace import trace
from features.cloud import conversation
from features.cloud.catalog import is_cloud
from features.cloud.client import CloudError


class NoBrainAvailable(RuntimeError):
    pass


def _label(kind: str) -> str:
    return "veloce" if kind == "chat" else "ragionamento"


async def _cloud(ref: str, query: str, device: str, context: dict, route: dict) -> dict:
    started = time.time()
    call = trace.begin("conversation", route["reason"], route["models"])
    trace.attempt(call, ref)
    try:
        answer = await conversation.reply(ref, query, device, context, route["max_tokens"])
    except CloudError as exc:
        brains.record(ref, (time.time() - started) * 1000, False, route["kind"])
        trace.abort(call, str(exc))
        raise
    brains.record(ref, answer.ms, True, route["kind"])
    trace.finish(call, ref, answer.ms, answer.text)
    background(touch(ref))
    return {"agent_id": f"jarvis_cloud · {ref.removeprefix('cloud:')} ({_label(route['kind'])})",
            "speech_output": answer.text, "result_data": {"model": ref}}


async def ask(query: str, device: str, context: dict, route: dict, core_local) -> dict:
    errors = []
    for cloud, group in groupby(route["models"], key=is_cloud):
        names = list(group)
        if not cloud:
            try:
                return await core_local(names)
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"locale: {type(exc).__name__}")
                store.event("WARN", f"Modelli locali non disponibili: {exc}", "core")
            continue
        for ref in names:
            try:
                return await _cloud(ref, query, device, context, route)
            except CloudError as exc:
                errors.append(str(exc)[:160])
                store.event("WARN", f"Cervello cloud non disponibile: {exc}", "cloud")
    raise NoBrainAvailable("; ".join(errors) or "nessun cervello configurato")
