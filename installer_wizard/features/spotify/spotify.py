import asyncio
import base64
import logging
import secrets
import time
import urllib.parse

import httpx

from config import env_get, write_env
from state import store

log = logging.getLogger("jarvis.spotify")

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "user-read-currently-playing user-read-playback-state"
POLL_SECONDS = 5


class Spotify:
    def __init__(self) -> None:
        self.access_token = ""
        self.expires_at = 0.0
        self.state = ""
        self.now: dict = {}
        self.status = "non collegato"
        self.user = ""

    @staticmethod
    def _creds() -> tuple[str, str]:
        return env_get("JARVIS_SPOTIFY_CLIENT_ID", ""), env_get("JARVIS_SPOTIFY_CLIENT_SECRET", "")

    def configured(self) -> bool:
        return all(self._creds()) and bool(env_get("JARVIS_SPOTIFY_REFRESH_TOKEN", ""))

    @staticmethod
    def enabled() -> bool:
        return env_get("JARVIS_SPOTIFY", "1") != "0"

    def auth_url(self) -> str:
        cid, _ = self._creds()
        if not cid:
            raise ValueError("Inserisci prima Client ID e Client Secret")
        self.state = secrets.token_urlsafe(12)
        return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
            "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": SCOPES,
            "state": self.state})

    async def _token(self, data: dict) -> dict:
        cid, secret = self._creds()
        basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("https://accounts.spotify.com/api/token", data=data,
                                  headers={"Authorization": f"Basic {basic}"})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200:
            raise ValueError(body.get("error_description") or body.get("error") or f"Spotify: errore {r.status_code}")
        return body

    async def finish(self, pasted: str) -> str:
        pasted = pasted.strip()
        query = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query) if "code=" in pasted else {"code": [pasted]}
        if query.get("error"):
            raise ValueError(f"Autorizzazione negata: {query['error'][0]}")
        if query.get("state") and self.state and query["state"][0] != self.state:
            raise ValueError("Collegamento scaduto: genera di nuovo il link di autorizzazione")
        code = (query.get("code") or [""])[0]
        if not code:
            raise ValueError("Codice di autorizzazione mancante")
        body = await self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI})
        write_env({"JARVIS_SPOTIFY_REFRESH_TOKEN": body["refresh_token"]})
        self.access_token, self.expires_at = body["access_token"], time.time() + body.get("expires_in", 3600) - 60
        me = await self._api("/me")
        self.user = (me or {}).get("display_name") or (me or {}).get("id") or ""
        store.event("INFO", f"Spotify collegato ({self.user})", "spotify")
        return self.user

    def disconnect(self) -> None:
        write_env({"JARVIS_SPOTIFY_REFRESH_TOKEN": ""})
        self.access_token, self.now, self.user = "", {}, ""

    async def _access(self) -> str:
        if not self.access_token or time.time() > self.expires_at:
            body = await self._token({"grant_type": "refresh_token",
                                      "refresh_token": env_get("JARVIS_SPOTIFY_REFRESH_TOKEN", "")})
            self.access_token, self.expires_at = body["access_token"], time.time() + body.get("expires_in", 3600) - 60
            if body.get("refresh_token"):
                write_env({"JARVIS_SPOTIFY_REFRESH_TOKEN": body["refresh_token"]})
        return self.access_token

    async def _api(self, path: str) -> dict | None:
        token = await self._access()
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://api.spotify.com/v1{path}", headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 204:
            return None
        if r.status_code == 401:
            self.access_token = ""
        r.raise_for_status()
        return r.json()

    async def poll(self) -> None:
        data = await self._api("/me/player/currently-playing")
        item = (data or {}).get("item") or {}
        if not data or not item or not data.get("is_playing"):
            self.now = {}
            return
        if self.now.get("key") == item.get("id"):
            started = time.time() - (data.get("progress_ms") or 0) / 1000
            if abs(started - self.now.get("started_at", 0)) > 2:
                self.now = {**self.now, "started_at": started}
            return
        images = (item.get("album") or {}).get("images") or []
        self.now = {
            "key": item.get("id", ""), "source": "spotify", "title": item.get("name", ""),
            "artist": ", ".join(a["name"] for a in item.get("artists", [])),
            "album": (item.get("album") or {}).get("name", ""),
            "year": ((item.get("album") or {}).get("release_date") or "")[:4],
            "cover": images[0]["url"] if images else "",
            "duration": (item.get("duration_ms") or 0) / 1000,
            "started_at": time.time() - (data.get("progress_ms") or 0) / 1000,
        }

    def current(self) -> dict:
        if not self.now:
            return {}
        if env_get("JARVIS_SPOTIFY_WHEN", "present") == "present" and \
                not any(p.get("known") for p in store.presence.get("people", [])):
            return {}
        return self.now

    def summary(self) -> dict:
        cid, secret = self._creds()
        return {"configured": self.configured(), "has_credentials": bool(cid and secret), "status": self.status,
                "user": self.user, "now": self.now, "redirect_uri": REDIRECT_URI, "enabled": self.enabled(),
                "when": env_get("JARVIS_SPOTIFY_WHEN", "present")}

    async def run(self) -> None:
        while True:
            if not (self.enabled() and self.configured()):
                self.status = "disattivato" if not self.enabled() else "non collegato"
                self.now = {}
                await asyncio.sleep(10)
                continue
            try:
                await self.poll()
                self.status = "collegato"
                await asyncio.sleep(POLL_SECONDS)
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                self.status = f"errore: {exc}"[:160]
                log.warning("Spotify: %s", exc)
                await asyncio.sleep(30)


spotify = Spotify()
