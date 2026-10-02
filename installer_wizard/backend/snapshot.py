import asyncio
import json
import time

from fastapi import Request
from fastapi.responses import StreamingResponse

from access import NO_CACHE
from config import NODE, STATE_DIR, VERSION, read_env
from features.brain.brains import brains
from features.home_assistant import home
from features.music import music
from orchestrator import orch
from pages import ASSET_VERSION, face_options
from state import store
from steps import step_catalog


FACE_KEYS = {"JARVIS_AVATAR", "JARVIS_FACE_COLOR"}


def _node_faces() -> dict:
    faces = {}
    for nid in node_ids_with(FACE_KEYS):
        token = NODE.set(nid)
        try:
            faces[nid] = face_options()
        finally:
            NODE.reset(token)
    return faces


def node_ids_with(keys: set) -> list[str]:
    path = STATE_DIR / "nodes.json"
    try:
        nodes = json.loads(path.read_text(encoding="utf-8")).get("nodes", {})
    except (OSError, ValueError):
        return []
    return [nid for nid, n in nodes.items() if keys & set(n.get("settings") or {})]


def full_snapshot(admin: bool) -> dict:
    snap = store.snapshot(admin=admin, log_lines=40 if admin else 14)
    snap["catalog"] = step_catalog()
    snap["supervisor_version"] = VERSION
    snap["asset_version"] = ASSET_VERSION
    env = read_env()
    snap["llm_model"] = env.get("JARVIS_LLM_MODEL", "")
    cfg = brains.config()
    chat, deep = brains.active_now("chat"), brains.active_now("deep")
    last = brains.last.get("model", "")
    snap["brains"] = {"chat": chat["label"] if chat else cfg["chat"][0], "deep": deep["label"] if deep else cfg["deep"][0],
                      "routing": cfg["routing"], "last": brains.describe(last)["label"] if last else ""}
    snap["user_name"] = env.get("JARVIS_USER_NAME", "")
    snap["face"] = face_options()
    snap["node_faces"] = _node_faces()
    snap["mic_reset"] = getattr(store, "mic_reset", 0)
    snap["now_playing"] = music.watcher.current()
    snap["home"] = home.brain.brief()
    snap["selftest"] = getattr(store, "selftest", None)
    try:
        from features.sounds.policy import policy as sound_policy
        snap["sounds"] = sound_policy.state()
    except Exception:
        snap["sounds"] = None
    if admin:
        snap["model_pull"] = getattr(store, "model_pull", None)
        snap["voice_pull"] = getattr(store, "voice_pull", None)
        snap["busy"] = orch.busy
    if hasattr(store, "holo_action"):
        snap["holo_action"] = store.holo_action
        delattr(store, "holo_action")
    return snap


def sse(admin: bool):
    async def generator(request: Request):
        last_version, last_sent = -1, 0.0
        while not await request.is_disconnected():
            if store.version != last_version or time.time() - last_sent > 10:
                last_version, last_sent = store.version, time.time()
                yield f"data: {json.dumps(full_snapshot(admin), ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.5)

    async def endpoint(request: Request):
        return StreamingResponse(generator(request), media_type="text/event-stream",
                                 headers={**NO_CACHE, "X-Accel-Buffering": "no"})
    return endpoint
