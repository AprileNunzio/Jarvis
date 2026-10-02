import base64
import hashlib
import secrets
import time
import urllib.parse

import httpx
from config import env_get

from features.google.constants import REDIRECT_URI, SERVICES

FLOW_TTL = 900


class OAuthApp:
    def __init__(self) -> None:
        self.flows: dict[str, dict] = {}

    @staticmethod
    def credentials() -> tuple[str, str]:
        return env_get("JARVIS_GOOGLE_CLIENT_ID", "").strip(), env_get("JARVIS_GOOGLE_CLIENT_SECRET", "").strip()

    def ready(self) -> bool:
        return all(self.credentials())

    def auth_url(self, slug: str, services: list[str]) -> str:
        cid, secret = self.credentials()
        if not (cid and secret):
            raise ValueError("Inserisci prima Client ID e Client Secret dell'app Google")
        services = [s for s in services if s in SERVICES]
        if not services:
            raise ValueError("Scegli almeno un servizio")
        scopes = ["openid", "email", "profile"] + [x for s in services for x in SERVICES[s]["scopes"]]
        state, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(48)
        now = time.time()
        self.flows = {k: v for k, v in self.flows.items() if now - v["at"] < FLOW_TTL}
        self.flows[state] = {"slug": slug, "verifier": verifier, "at": now}
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
            "client_id": cid, "response_type": "code", "redirect_uri": REDIRECT_URI, "scope": " ".join(scopes),
            "state": state, "access_type": "offline", "prompt": "consent select_account",
            "include_granted_scopes": "true", "code_challenge": challenge, "code_challenge_method": "S256"})

    async def token(self, data: dict) -> dict:
        cid, secret = self.credentials()
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("https://oauth2.googleapis.com/token",
                                  data={**data, "client_id": cid, "client_secret": secret})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200:
            err = body.get("error_description") or body.get("error") or f"errore {r.status_code}"
            if body.get("error") == "invalid_grant":
                err = "autorizzazione scaduta o revocata: ricollega l'account"
            raise ValueError(f"Google: {err}")
        return body

    async def exchange(self, pasted: str) -> tuple[str, dict]:
        pasted = pasted.strip()
        query = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
        if query.get("error"):
            raise ValueError(f"Autorizzazione negata: {query['error'][0]}")
        flow = self.flows.pop((query.get("state") or [""])[0], None)
        if not flow or time.time() - flow["at"] > FLOW_TTL:
            raise ValueError("Collegamento scaduto o non riconosciuto: genera di nuovo il link e incolla l'indirizzo completo")
        code = (query.get("code") or [""])[0]
        if not code:
            raise ValueError("Codice di autorizzazione mancante")
        body = await self.token({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
                                 "code_verifier": flow["verifier"]})
        if not body.get("refresh_token"):
            raise ValueError("Google non ha rilasciato il token di rinnovo: rimuovi l'accesso di Jarvis da "
                             "myaccount.google.com/permissions e ricollega")
        return flow["slug"], body

    @staticmethod
    async def revoke(token: str) -> None:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post("https://oauth2.googleapis.com/revoke", data={"token": token})


oauth = OAuthApp()
