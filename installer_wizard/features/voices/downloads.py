import asyncio

import httpx

from features.voices import languages
from features.voices.catalog import (PIPER_BASE, VOICE_DIR, auto_download, best_download, describe, fallback_voice,
                                     is_online, is_piper, online_enabled, piper_catalog, piper_installed,
                                     piper_voice_path, voices_for)
from state import store

downloading: set[str] = set()


async def ensure_language(lang: str) -> dict:
    lang = languages.base(lang)
    ready = [v for v in await voices_for(lang) if not is_online(v) or online_enabled()]
    offline = [v for v in ready if not is_online(v)]
    if offline:
        return {"lang": lang, "status": "pronta", "voice": offline[0]}
    target = best_download(lang)
    if target and auto_download():
        await start_download(target)
        return {"lang": lang, "status": "download", "voice": target, "online": ready[0] if ready else None,
                "size_mb": describe(target)["size_mb"]}
    if ready:
        return {"lang": lang, "status": "pronta", "voice": ready[0]}
    return {"lang": lang, "status": "assente", "voice": None}


async def start_download(voice: str) -> bool:
    if not is_piper(voice) or piper_installed(voice) or voice in downloading:
        return False
    downloading.add(voice)
    asyncio.get_running_loop().create_task(download_piper(voice))
    return True


async def download_piper(voice: str) -> None:
    target = VOICE_DIR / "voices"
    path = (piper_catalog().get(voice) or {}).get("path") or piper_voice_path(voice)
    downloading.add(voice)
    store.voice_pull = {"name": voice, "status": "download", "percent": 0}
    store.touch()
    try:
        target.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=120), follow_redirects=True) as client:
            for ext in ("onnx.json", "onnx"):
                part = target / f"{voice}.{ext}.part"
                async with client.stream("GET", f"{PIPER_BASE}/{path}.{ext}") as r:
                    r.raise_for_status()
                    total, done = int(r.headers.get("content-length") or 0), 0
                    with part.open("wb") as fh:
                        async for chunk in r.aiter_bytes(1 << 16):
                            fh.write(chunk)
                            done += len(chunk)
                            pct = done * 100 // total if total and ext == "onnx" else 0
                            if pct and pct != store.voice_pull.get("percent"):
                                store.voice_pull = {"name": voice, "status": "download", "percent": pct}
                                store.touch()
                part.replace(target / f"{voice}.{ext}")
        store.voice_pull = {"name": voice, "status": "completato", "percent": 100}
        d = describe(voice)
        store.event("INFO", f"Voce scaricata: {d['name']} ({languages.label(d['lang'])})", "voice")
    except (httpx.HTTPError, OSError) as exc:
        store.voice_pull = {"name": voice, "status": f"errore: {exc}", "percent": 0}
        store.event("ERROR", f"Download della voce {voice} non riuscito: {exc}", "voice")
    finally:
        downloading.discard(voice)
    store.touch()


def delete_piper(voice: str) -> None:
    if voice == fallback_voice():
        raise ValueError("È la voce di riserva di sicurezza: non può essere eliminata")
    for ext in ("onnx", "onnx.json"):
        (VOICE_DIR / "voices" / f"{voice}.{ext}").unlink(missing_ok=True)

