import asyncio
import time
from datetime import datetime, timedelta

import httpx
from config import env_get
from state import store

from features.google.accounts import accounts
from features.google.app import oauth
from features.google.constants import DEFAULT_SERVICES, REDIRECT_URI, SERVICES, log
from features.google.notify import notifier
from features.google.session import Session
from features.google.timeparse import event_json
from features.people import identity, people


class Google:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}

    @staticmethod
    def enabled() -> bool:
        return env_get("JARVIS_GOOGLE", "1") != "0"

    def session(self, slug: str) -> Session | None:
        if not accounts.get(slug):
            self.sessions.pop(slug, None)
            return None
        return self.sessions.setdefault(slug, Session(slug))

    def for_profile(self, profile: dict | None) -> Session | None:
        return self.session(profile["slug"]) if profile and self.enabled() else None

    def present_sessions(self, service: str) -> list[tuple[dict, Session]]:
        pairs = [(p, self.for_profile(p)) for p in identity.present()]
        return [(p, s) for p, s in pairs if s and s.ready(service)]

    def auth_url(self, slug: str, services: list[str]) -> str:
        if not people.load(slug):
            raise ValueError("Persona sconosciuta")
        return oauth.auth_url(slug, services)

    async def link(self, pasted: str) -> tuple[str, str]:
        slug, body = await oauth.exchange(pasted)
        accounts.put(slug, {"refresh": body["refresh_token"], "scopes": body.get("scope", "").split(),
                            "linked_at": time.time()})
        session = Session(slug)
        session.access_token = body["access_token"]
        session.expires_at = time.time() + body.get("expires_in", 3600) - 60
        self.sessions[slug] = session
        me = await session._get("https://openidconnect.googleapis.com/v1/userinfo")
        accounts.put(slug, {"email": me.get("email", ""), "name": me.get("name", "")})
        who = (people.load(slug) or {}).get("name", slug)
        store.event("INFO", f"Google collegato per {who} ({me.get('email', '')}): "
                            f"{', '.join(SERVICES[s]['name'] for s in session.granted())}", "google")
        return slug, me.get("email", "")

    async def unlink(self, slug: str) -> None:
        entry = accounts.remove(slug)
        self.sessions.pop(slug, None)
        if entry and entry.get("refresh"):
            try:
                await oauth.revoke(entry["refresh"])
            except httpx.HTTPError as exc:
                log.warning("Revoca del token Google non confermata: %s", exc)

    def summary(self) -> dict:
        cid, secret = oauth.credentials()
        rows = []
        for p in people.all_profiles(light=True):
            entry = accounts.get(p["slug"]) or {}
            session = self.sessions.get(p["slug"])
            rows.append({"slug": p["slug"], "name": p.get("name"), "role": p.get("role", ""),
                         "linked": bool(entry.get("refresh")), "email": entry.get("email", ""),
                         "granted": accounts.granted(entry) if entry else [],
                         "status": session.status if session else ("collegato" if entry else "non collegato"),
                         "unread": session.unread if session else None})
        return {"enabled": self.enabled(), "has_credentials": bool(cid and secret), "client_id": cid,
                "redirect_uri": REDIRECT_URI, "remind_min": env_get("JARVIS_GOOGLE_REMIND_MIN", "10"),
                "default_services": DEFAULT_SERVICES.split(","),
                "services": [{"id": s, "name": d["name"], "icon": d["icon"], "api": d["api"],
                              "workspace": bool(d.get("workspace"))} for s, d in SERVICES.items()],
                "people": rows}

    async def preview(self, slug: str) -> dict:
        session = self.session(slug)
        if not session:
            return {}
        out: dict = {}
        now = datetime.now().astimezone()
        jobs = {"events": ("calendar", lambda: session.events(now, now + timedelta(days=7), 8)),
                "mail": ("gmail", lambda: session.mails(limit=5)), "tasks": ("tasks", lambda: session.tasks(10))}
        for key, (service, job) in jobs.items():
            if not session.ready(service):
                continue
            try:
                result = await job()
            except (httpx.HTTPError, ValueError) as exc:
                out[f"{key}_error"] = str(exc)
                continue
            if key == "events":
                out[key] = [event_json(e) for e in result]
            elif key == "mail":
                out[key] = {"unread": result[0], "items": result[1]}
            else:
                out[key] = result
        return out

    async def _refresh(self, profile: dict, minutes: int) -> None:
        session = self.for_profile(profile)
        if not session:
            return
        try:
            await notifier.brief(profile, session)
            if session.ready("calendar"):
                if minutes > 0:
                    await notifier.soon(profile, session, minutes)
                await notifier.calendar(profile, session)
            if session.ready("gmail"):
                await notifier.mail(profile, session)
            if session.ready("tasks"):
                await notifier.tasks(profile, session)
            if session.ready("keep"):
                await notifier.notes(profile, session)
            session.status = "collegato"
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            session.status = f"errore: {exc}"[:160]
            log.warning("Google (%s): %s", profile["slug"], exc)

    async def run(self) -> None:
        seen: set[str] = set()
        last_full = 0.0
        while True:
            if self.enabled() and oauth.ready():
                accounts.slugs()
                minutes = int(env_get("JARVIS_GOOGLE_REMIND_MIN", "10") or 10)
                here = identity.present()
                full = time.time() - last_full >= 60
                for profile in here:
                    if full or profile["slug"] not in seen:
                        await self._refresh(profile, minutes)
                seen = {p["slug"] for p in here}
                if full:
                    last_full = time.time()
            await asyncio.sleep(4)


google = Google()
