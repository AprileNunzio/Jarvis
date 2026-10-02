import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from config import DEMO, env_get
from state import store

from features.music import lyrics

log = logging.getLogger("jarvis.music")

VENV_PY = Path("/opt/jarvis-music/venv/bin/python")
RECOGNIZER = Path(__file__).resolve().parent / "music_id.py"
USER_AGENT = "JarvisOS/3 (+https://github.com/AprileNunzio/Jarvis)"
DISABLED_RETRY = 300


def enabled() -> bool:
    return env_get("JARVIS_MUSIC_ID", "1") != "0"


def available() -> bool:
    return DEMO or VENV_PY.exists()


class MusicWatcher:
    def __init__(self) -> None:
        self.misses = 0
        self.history: list = []
        self.lock = asyncio.Lock()
        self.bio_cache: dict = {}

    async def _recognize(self, wav: bytes) -> dict:
        if DEMO:
            return {}
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
            fh.write(wav)
            path = fh.name
        try:
            proc = await asyncio.create_subprocess_exec(
                "nice", "-n", "10", str(VENV_PY), str(RECOGNIZER), path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(proc.communicate(), 40)
            if proc.returncode:
                lines = err.decode(errors="replace").strip().splitlines()
                raise RuntimeError(lines[-1] if lines else f"codice {proc.returncode}")
            return json.loads(out or b"{}")
        finally:
            Path(path).unlink(missing_ok=True)

    async def _itunes(self, client: httpx.AsyncClient, title: str, artist: str) -> dict:
        try:
            r = await client.get("https://itunes.apple.com/search",
                                 params={"term": f"{artist} {title}", "entity": "song", "limit": 5, "country": "it"})
            results = r.json().get("results", [])
        except (httpx.HTTPError, ValueError):
            return {}
        t = title.lower().split(" (")[0]
        best = next((x for x in results if t in x.get("trackName", "").lower()), results[0] if results else None)
        if not best:
            return {}
        return {"duration": (best.get("trackTimeMillis") or 0) / 1000 or None,
                "album": best.get("collectionName"), "year": (best.get("releaseDate") or "")[:4] or None,
                "genre": best.get("primaryGenreName"),
                "cover": (best.get("artworkUrl100") or "").replace("100x100", "600x600") or None,
                "track_number": best.get("trackNumber"), "track_count": best.get("trackCount")}

    async def _bio(self, client: httpx.AsyncClient, artist: str) -> dict:
        key = artist.lower()
        if key in self.bio_cache:
            return self.bio_cache[key]
        bio = {}
        for lang in ("it", "en"):
            try:
                r = await client.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(artist)}",
                                     follow_redirects=True)
                d = r.json()
            except (httpx.HTTPError, ValueError):
                continue
            if r.status_code == 200 and d.get("type") != "disambiguation" and d.get("extract"):
                bio = {"text": d["extract"][:600], "description": d.get("description"),
                       "url": (d.get("content_urls") or {}).get("desktop", {}).get("page"),
                       "image": (d.get("thumbnail") or {}).get("source")}
                break
        self.bio_cache[key] = bio
        return bio

    @staticmethod
    def _parse(raw: dict) -> dict | None:
        track = raw.get("track")
        if not track:
            return None
        meta = {}
        for section in track.get("sections", []):
            for m in section.get("metadata", []) or []:
                meta[str(m.get("title", "")).lower()] = m.get("text")
        images = track.get("images") or {}
        offset = None
        if raw.get("matches"):
            offset = raw["matches"][0].get("offset")
        return {
            "title": track.get("title"), "artist": track.get("subtitle"),
            "album": meta.get("album"), "label": meta.get("etichetta") or meta.get("label"),
            "year": meta.get("pubblicato") or meta.get("released") or meta.get("uscita"),
            "genre": (track.get("genres") or {}).get("primary"),
            "cover": images.get("coverarthq") or images.get("coverart"),
            "url": track.get("url"), "isrc": track.get("isrc"), "key": track.get("key"),
            "offset": offset,
        }

    async def handle(self, wav: bytes) -> dict:
        if not enabled():
            return {"ok": False, "next_in": DISABLED_RETRY, "reason": "disabilitato"}
        if not available():
            return {"ok": False, "next_in": DISABLED_RETRY, "reason": "riconoscimento non installato"}
        if self.lock.locked():
            return {"ok": False, "next_in": 30}
        async with self.lock:
            captured_at = time.time() - 5
            try:
                song = self._parse(await self._recognize(wav))
            except Exception as exc:
                log.warning("Riconoscimento musicale non riuscito: %s", exc)
                return {"ok": False, "next_in": 300}
            now_playing = store.now_playing or {}
            if not song:
                self.misses += 1
                if now_playing and time.time() > now_playing.get("expires", 0) - 60:
                    store.now_playing = {}
                    store.touch()
                return {"ok": True, "found": False, "next_in": min(480, 60 * 2 ** min(self.misses - 1, 3))}
            self.misses = 0
            same = now_playing.get("key") == song["key"]
            if same:
                enriched = {k: v for k, v in now_playing.items() if k not in ("offset", "recognized_at")}
                enriched.update({k: v for k, v in song.items() if v})
            else:
                async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
                    itunes, bio = await asyncio.gather(self._itunes(client, song["title"], song["artist"] or ""),
                                                       self._bio(client, (song["artist"] or "").split(" feat")[0]))
                enriched = {**{k: v for k, v in itunes.items() if v}, **{k: v for k, v in song.items() if v}, "bio": bio}
                enriched["cover"] = song.get("cover") or itunes.get("cover")
                enriched["lyrics"] = await lyrics.fetch(song["title"], song.get("artist") or "",
                                                        itunes.get("album") or "", itunes.get("duration"))
                self.history = ([{"title": song["title"], "artist": song["artist"], "at": time.time()}]
                                + self.history)[:20]
                store.event("INFO", f"Brano riconosciuto: {song['title']} — {song['artist']}", "music")
            duration, offset = enriched.get("duration"), song.get("offset")
            started = captured_at - offset if offset is not None else now_playing.get("started_at", captured_at)
            enriched.update(recognized_at=time.time(), started_at=started)
            if duration:
                remaining = started + duration - time.time()
                enriched["expires"] = time.time() + max(30, remaining + 45)
                next_in = int(max(20, min(360, remaining + 8)))
            else:
                enriched["expires"] = time.time() + 240
                next_in = 90
            store.now_playing = enriched
            store.touch()
            return {"ok": True, "found": True, "title": song["title"], "next_in": next_in}

    def current(self) -> dict:
        np_ = store.now_playing or {}
        if np_ and time.time() > np_.get("expires", 0):
            store.now_playing = {}
            store.touch()
            return {}
        return np_

    def summary(self) -> dict:
        return {"enabled": enabled(), "installed": available(), "now_playing": self.current(),
                "history": self.history}


watcher = MusicWatcher()


def speech_for(np_: dict) -> str:
    if not np_:
        return "In questo momento non sento musica che io riesca a riconoscere."
    text = f"Sta suonando «{np_['title']}» di {np_.get('artist') or 'un artista che non conosco'}"
    extra = []
    if np_.get("album"):
        extra.append(f"dall'album {np_['album']}")
    if np_.get("year"):
        extra.append(f"del {np_['year']}")
    return text + (", " + " ".join(extra) if extra else "") + "."
