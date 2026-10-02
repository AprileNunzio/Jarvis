import asyncio
import json
import re
import time

import httpx

from config import DEMO, JARVIS_DIR, STATE_DIR, env_get
from health import sh
from state import now_iso, store

PENDING_FILE = STATE_DIR / "update_pending.json"
BAD_REVS_FILE = STATE_DIR / "bad_revs"
LAST_GOOD_FILE = STATE_DIR / "last_good_rev"
GATED_JOBS = {"validate-python", "tests", "validate-scripts"}
UNREACHABLE_GRACE = 3600
_ci: dict[str, tuple[str, float]] = {}
_unreachable_since = 0.0


async def git(*args: str, timeout: float = 120) -> tuple[int, str]:
    return await sh("git", "-c", "safe.directory=*", "-C", str(JARVIS_DIR), *args, timeout=timeout)


def _bad_revs() -> set:
    try:
        return set(BAD_REVS_FILE.read_text().split())
    except OSError:
        return set()


def branch() -> str:
    return env_get("JARVIS_UPDATE_BRANCH", "main") or "main"


async def current_rev() -> str:
    code, out = await git("rev-parse", "HEAD")
    return out if code == 0 else ""


def require_ci() -> bool:
    return env_get("JARVIS_UPDATE_REQUIRE_CI", "1") != "0"


async def _slug() -> str:
    _, url = await git("remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]([^/]+/[^/.\s]+?)(?:\.git)?$", url.strip())
    return m.group(1) if m else ""


async def ci_status(sha: str) -> str:
    global _unreachable_since
    cached = _ci.get(sha)
    if cached and (cached[0] in ("success", "failure") or time.time() - cached[1] < 60):
        return cached[0]
    slug = await _slug()
    if not slug:
        return "unknown"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"https://api.github.com/repos/{slug}/commits/{sha}/check-runs",
                                 headers={"Accept": "application/vnd.github+json"}, params={"per_page": 50})
        r.raise_for_status()
        runs = [c for c in r.json().get("check_runs", []) if c.get("name") in GATED_JOBS]
        _unreachable_since = 0.0
    except (httpx.HTTPError, ValueError):
        _unreachable_since = _unreachable_since or time.time()
        return "unknown"
    if any(c.get("conclusion") in ("failure", "cancelled", "timed_out", "action_required") for c in runs):
        status = "failure"
    elif not runs or any(c.get("status") != "completed" for c in runs):
        status = "pending"
    else:
        status = "success"
    _ci[sha] = (status, time.time())
    return status


async def pick_target(remote: str) -> tuple[str, str]:
    if not require_ci():
        return remote, ""
    _, revs = await git("rev-list", "--max-count=30", f"HEAD..{remote}")
    waiting = ""
    for sha in revs.split():
        if sha in _bad_revs():
            continue
        status = await ci_status(sha)
        if status == "success":
            return sha, waiting
        if status == "pending" and not waiting:
            waiting = f"test in corso su GitHub per {sha[:7]}"
        if status == "failure" and not waiting:
            waiting = f"{sha[:7]} non ha superato i test su GitHub: la salto"
        if status == "unknown":
            if _unreachable_since and time.time() - _unreachable_since > UNREACHABLE_GRACE:
                return sha, "GitHub non raggiungibile da oltre un'ora: aggiorno senza conferma dei test"
            return "", "GitHub non raggiungibile: attendo la conferma dei test"
    return "", waiting


async def mark_good() -> None:
    rev = await current_rev()
    if rev:
        store.last_good_rev = rev
        LAST_GOOD_FILE.write_text(rev)
        store.save()


async def check() -> dict:
    info = store.update
    info["last_check"] = now_iso()
    if DEMO:
        info.update(local_rev="demo", remote_rev="demo", available=False, last_result="Modalità demo")
        return info
    code, out = await git("fetch", "--quiet", "origin", branch(), timeout=180)
    if code != 0:
        info["last_result"] = f"Fetch non riuscito: {out[:160]}"
        store.touch()
        return info
    local = await current_rev()
    _, remote = await git("rev-parse", f"origin/{branch()}")
    _, log = await git("log", "--oneline", "-n", "15", f"HEAD..origin/{branch()}")
    target, note = (await pick_target(remote)) if remote and remote != local else ("", "")
    info.update(local_rev=local, remote_rev=remote, target_rev=target, ci_note=note,
                available=bool(target) and target != local and target not in _bad_revs(),
                changelog=log.splitlines() if log else [])
    if note:
        info["last_result"] = note
    store.touch()
    return info


async def apply(reason: str = "automatico") -> bool:
    info = await check()
    if not info.get("available"):
        return False
    target = info["target_rev"]
    store.event("INFO", f"Aggiornamento {reason}: {info['local_rev'][:7]} → {target[:7]} (test superati)", "updater")
    store.set_phase("UPDATING", "Download del nuovo firmware cognitivo…")
    PENDING_FILE.write_text(json.dumps({"from": info["local_rev"], "to": target, "at": time.time()}))
    code, out = await git("reset", "--hard", target)
    if code != 0:
        PENDING_FILE.unlink(missing_ok=True)
        store.event("ERROR", f"Aggiornamento non applicato: {out[:200]}", "updater")
        store.set_phase("READY", "Aggiornamento annullato")
        return False
    store.message = "Riavvio del supervisore sulla nuova versione…"
    store.touch()
    await asyncio.sleep(2)
    await sh("systemctl", "restart", "--no-block", "jarvis-supervisor.service", timeout=10)
    return True


def pending() -> dict | None:
    try:
        return json.loads(PENDING_FILE.read_text())
    except (OSError, ValueError):
        return None


async def finish_pending(success: bool) -> bool:
    data = pending()
    if not data:
        return False
    PENDING_FILE.unlink(missing_ok=True)
    if success:
        from datetime import datetime
        local_time = datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S')
        store.update["last_result"] = f"Aggiornato a {data['to'][:7]} il {local_time}"
        store.event("INFO", "Aggiornamento verificato e confermato", "updater")
        await mark_good()
        return False
    store.update["last_result"] = f"Rollback: {data['to'][:7]} non ha superato la verifica"
    store.event("ERROR", f"Aggiornamento {data['to'][:7]} fallito: rollback a {data['from'][:7]}", "updater")
    with BAD_REVS_FILE.open("a") as fh:
        fh.write(data["to"] + "\n")
    await git("reset", "--hard", data["from"])
    await sh("systemctl", "restart", "--no-block", "jarvis-supervisor.service", timeout=10)
    return True


async def scheduler() -> None:
    await asyncio.sleep(120)
    while True:
        stuck = store.phase == "ERROR" or getattr(store, "pipeline_failed", False)
        if store.phase != "READY" and not stuck:
            await asyncio.sleep(60)
            continue
        try:
            if env_get("JARVIS_AUTO_UPDATE", "1") != "0":
                await apply("automatico" if store.phase == "READY" else "correttivo (sistema bloccato)")
            else:
                await check()
        except Exception as exc:
            store.event("ERROR", f"Errore updater: {exc}", "updater")
        try:
            minutes = float(env_get("JARVIS_UPDATE_INTERVAL_MIN", "5") or 5)
        except ValueError:
            minutes = 5
        await asyncio.sleep(max(1.0, minutes) * 60)
