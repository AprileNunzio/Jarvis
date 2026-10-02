import re

import httpx

LRCLIB = "https://lrclib.net/api/get"
USER_AGENT = "JarvisOS/3 (+https://github.com/AprileNunzio/Jarvis)"
LINE = re.compile(r"((?:\[\d{1,2}:\d{2}(?:[.:]\d{1,3})?\])+)(.*)")
TAG = re.compile(r"\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")
_cache: dict = {}


def _parse(synced: str) -> list:
    out = []
    for raw in synced.splitlines():
        m = LINE.match(raw.strip())
        if not m:
            continue
        text = m.group(2).strip()
        for tag in TAG.finditer(m.group(1)):
            mm, ss, frac = tag.groups()
            t = int(mm) * 60 + int(ss) + (int(frac.ljust(3, "0")) / 1000 if frac else 0)
            out.append({"t": round(t, 2), "text": text})
    out.sort(key=lambda x: x["t"])
    return out[:400]


async def fetch(title: str, artist: str, album: str = "", duration: float | None = None) -> dict:
    if not title or not artist:
        return {}
    key = f"{title}|{artist}".lower()
    if key in _cache:
        return _cache[key]
    params = {"track_name": title, "artist_name": artist}
    if album:
        params["album_name"] = album
    if duration:
        params["duration"] = int(duration)
    result: dict = {}
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": USER_AGENT}) as client:
            r = await client.get(LRCLIB, params=params)
            if r.status_code == 200:
                data = r.json()
                synced = _parse(data.get("syncedLyrics") or "")
                plain = (data.get("plainLyrics") or "").strip()
                if synced:
                    result = {"synced": synced}
                elif plain:
                    result = {"plain": plain[:4000]}
    except (httpx.HTTPError, ValueError):
        result = {}
    _cache[key] = result
    if len(_cache) > 60:
        _cache.pop(next(iter(_cache)))
    return result
