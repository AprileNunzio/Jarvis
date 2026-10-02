import time
from datetime import date, datetime, timedelta

from state import store

from features.google.session import Session
from features.people import identity

FRESH_SECONDS = 12 * 3600
FOLLOW_UP_SECONDS = 15 * 60
TTL = 180


class Notifier:
    def __init__(self) -> None:
        self.reminded: dict[str, float] = {}
        self.known: dict[str, set] = {}
        self.briefed: dict[str, str] = {}
        self.last: dict[str, tuple[str, float]] = {}

    @staticmethod
    def _desk():
        from features.desktop.desk import desk
        return desk

    def recent(self, slug: str, window: float = FOLLOW_UP_SECONDS) -> str | None:
        kind, at = self.last.get(slug, ("", 0.0))
        return kind if kind and time.time() - at < window else None

    def consume(self, slug: str) -> None:
        self.last.pop(slug, None)

    def _show(self, profile: dict, kind: str, data: dict, key: str, ttl: float = TTL) -> None:
        self.last[profile["slug"]] = (kind, time.time())
        self._desk().show("g_notify", {"kind": kind, "who": identity.first_name(profile), "announce": True, **data},
                          key=key, ttl=ttl)

    def _new(self, profile: dict, kind: str, ids: list[str]) -> list[str] | None:
        key = f"{profile['slug']}:{kind}"
        before = self.known.get(key)
        self.known[key] = set(ids)
        return None if before is None else [i for i in ids if i not in before]

    async def soon(self, profile: dict, session: Session, minutes: int) -> None:
        now = datetime.now().astimezone()
        name = identity.first_name(profile)
        for e in await session.events(now, now + timedelta(minutes=minutes + 1), 10):
            key = f"{profile['slug']}:{e['id']}"
            if e["all_day"] or key in self.reminded:
                continue
            self.reminded[key] = time.time()
            left = max(1, round((e["start"] - now).total_seconds() / 60))
            from features.automations.bus import emit
            emit("calendar_soon", {"person": name, "title": e["title"], "where": e["where"], "minutes": left,
                                   "at": e["start"].strftime("%H:%M")})
            self._show(profile, "event", {"title": e["title"], "text": e["where"], "at": e["start"].timestamp(),
                                          "speak": f"{name}, tra {left} minuti ha {e['title']}."},
                       key=f"gcal:{key}", ttl=minutes * 60 + 120)
            store.event("INFO", f"Promemoria per {name}: {e['title']} alle {e['start']:%H:%M}", "google")
        self.reminded = {k: v for k, v in self.reminded.items() if time.time() - v < 86400}

    async def calendar(self, profile: dict, session: Session) -> None:
        now = datetime.now().astimezone()
        events = await session.events(now, now + timedelta(days=7), 50)
        new = self._new(profile, "calendar", [e["id"] for e in events])
        added = [e for e in events if new and e["id"] in new]
        if not added:
            return
        e, name, private = added[0], identity.first_name(profile), identity.alone(profile)
        when = f"{e['start']:%d/%m}" + ("" if e["all_day"] else f" alle {e['start']:%H:%M}")
        self._show(profile, "calendar", {"icon": "📅", "title": e["title"] if private else "Nuovo appuntamento",
                                         "text": when + (f" · +{len(added) - 1} altri" if len(added) > 1 else ""),
                                         "speak": f"{name}, c'è un nuovo appuntamento in agenda"
                                                  + (f": {e['title']}, {when}." if private else ".")},
                   key=f"gcalnew:{profile['slug']}")

    async def mail(self, profile: dict, session: Session) -> None:
        total, mails = await session.mails(limit=1)
        session.unread = total
        if not mails:
            self._new(profile, "mail", [])
            return
        m = mails[0]
        first_look = f"{profile['slug']}:mail" not in self.known
        new = self._new(profile, "mail", [m["id"]])
        if first_look and time.time() - m["at"] > FRESH_SECONDS or not first_look and not new:
            return
        name, private = identity.first_name(profile), identity.alone(profile)
        from features.automations.bus import emit
        emit("email_new", {"person": name, "from": m["from"], "subject": m["subject"], "unread": total})
        self._show(profile, "mail", {"icon": "✉️", "title": m["subject"] if private else "Nuova email",
                                     "from": m["from"] if private else "",
                                     "text": m["snippet"][:120] if private else f"{total} non lette",
                                     "speak": (f"{name}, nuova email da {m['from']}. Desidera che gliela legga?" if private
                                               else f"{name}, ha una nuova email.")},
                   key=f"gmail:{profile['slug']}")

    async def tasks(self, profile: dict, session: Session) -> None:
        today = date.today().isoformat()
        due = [t for t in await session.tasks(50) if t["due"] and t["due"] <= today]
        new = self._new(profile, "tasks", [t["id"] for t in due])
        fresh = [t for t in due if new and t["id"] in new]
        if not fresh:
            return
        name, private = identity.first_name(profile), identity.alone(profile)
        late = sum(1 for t in due if t["due"] < today)
        self._show(profile, "tasks", {"icon": "✅", "title": fresh[0]["title"] if private else "Attività in scadenza",
                                      "text": f"{len(due)} da fare oggi" + (f", {late} in ritardo" if late else ""),
                                      "speak": f"{name}, ha {len(due)} attività in scadenza. Desidera l'elenco?"},
                   key=f"gtasks:{profile['slug']}")

    async def notes(self, profile: dict, session: Session) -> None:
        found = await session.notes(20)
        new = self._new(profile, "notes", [n["id"] for n in found])
        fresh = [n for n in found if new and n["id"] in new]
        if not fresh:
            return
        n, name, private = fresh[0], identity.first_name(profile), identity.alone(profile)
        self._show(profile, "notes", {"icon": "🗒", "title": (n["title"] or n["text"][:60]) if private else "Nuova nota",
                                      "text": n["text"][:120] if private else "Google Keep",
                                      "speak": f"{name}, c'è una nuova nota in Keep. Desidera che gliela legga?"},
                   key=f"gkeep:{profile['slug']}")

    async def brief(self, profile: dict, session: Session) -> None:
        slug, today = profile["slug"], date.today().isoformat()
        if self.briefed.get(slug) == today:
            return
        self.briefed[slug] = today
        now = datetime.now().astimezone()
        end = datetime.combine(now.date(), datetime.max.time()).astimezone()
        items, first, events = [], None, []
        if session.ready("calendar"):
            events = await session.events(now, end, 30)
            first = next((e for e in events if e.get("kind") == "appointment"), None)
        groups = self._groups(events, session.ready("calendar"))
        for g in groups:
            items.append({"icon": g["icon"], "value": str(len(g["entries"])), "label": g["label"].lower()})
        if session.ready("gmail"):
            total, _ = await session.mails(limit=0)
            session.unread = total
            items.append({"icon": "✉️", "value": str(total), "label": "da leggere"})
        if session.ready("tasks"):
            due = [t for t in await session.tasks(50) if t["due"] and t["due"] <= today]
            items.append({"icon": "✅", "value": str(len(due)), "label": "in scadenza"})
        if not items:
            return
        private = identity.alone(profile)
        text = f"Primo impegno alle {first['start']:%H:%M}: {first['title']}" if first and private else ""
        shown = [g for g in groups if g["entries"]] if private else []
        self._desk().show("g_notify", {"kind": "brief", "who": identity.first_name(profile), "items": items,
                                       "groups": shown, "text": text}, key=f"gbrief:{slug}", ttl=240)

    @staticmethod
    def _groups(events: list[dict], calendar: bool) -> list[dict]:
        groups = {"birthday": {"key": "birthday", "icon": "🎂", "label": "Compleanni", "entries": []},
                  "event": {"key": "event", "icon": "📌", "label": "Eventi", "entries": []},
                  "appointment": {"key": "appointment", "icon": "🗓", "label": "Impegni", "entries": []}}
        for e in events:
            kind = e.get("kind") or ("event" if e["all_day"] else "appointment")
            when = "" if e["all_day"] else f"{e['start']:%H:%M}"
            groups[kind]["entries"].append({"time": when, "title": e["title"], "where": e.get("where", "")})
        try:
            from features.people import people
            for r in people.reminders(days=0):
                kind = "birthday" if r["type"] in ("compleanno", "onomastico") else "event"
                if not any(r["person"].split()[0].lower() in x["title"].lower() for x in groups[kind]["entries"]):
                    groups[kind]["entries"].append({"time": "", "title": r["title"], "where": ""})
        except Exception:
            pass
        return [g for g in groups.values() if g["entries"] or calendar]


notifier = Notifier()
