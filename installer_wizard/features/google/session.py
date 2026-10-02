import time

import httpx

from features.google.accounts import accounts
from features.google.app import oauth
from features.google.data import GoogleData


class Session(GoogleData):
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.access_token = ""
        self.expires_at = 0.0
        self.unread: int | None = None
        self.status = "collegato"

    @property
    def info(self) -> dict:
        return accounts.get(self.slug) or {}

    def granted(self) -> list[str]:
        return accounts.granted(self.info)

    def ready(self, service: str) -> bool:
        return bool(self.info.get("refresh")) and service in self.granted()

    async def _access(self) -> str:
        if not self.access_token or time.time() > self.expires_at:
            body = await oauth.token({"grant_type": "refresh_token", "refresh_token": self.info.get("refresh", "")})
            self.access_token, self.expires_at = body["access_token"], time.time() + body.get("expires_in", 3600) - 60
            if body.get("scope"):
                accounts.put(self.slug, {"scopes": body["scope"].split()})
        return self.access_token

    async def _call(self, method: str, url: str, **kw) -> dict:
        token = await self._access()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kw)
        if r.status_code == 401:
            self.access_token = ""
        if r.status_code == 403:
            is_json = r.headers.get("content-type", "").startswith("application/json")
            msg = ((r.json() if r.content and is_json else {}).get("error") or {}).get("message", "")
            raise ValueError(f"Google ha rifiutato la richiesta: {msg or 'API non abilitata o permesso mancante'}")
        r.raise_for_status()
        return r.json() if r.content else {}

    async def _get(self, url: str, **params) -> dict:
        return await self._call("GET", url, params=params or None)
