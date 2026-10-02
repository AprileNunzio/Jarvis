import asyncio
import base64
import html
import re
import urllib.parse
from datetime import date, datetime, timedelta

import httpx


class GoogleData:
    async def events(self, start: datetime, end: datetime, limit: int = 25) -> list[dict]:
        cals = (await self._get("https://www.googleapis.com/calendar/v3/users/me/calendarList",
                                minAccessRole="reader")).get("items", [])
        cals = [c for c in cals if c.get("selected") or c.get("primary")] or [{"id": "primary"}]
        out = []
        for cal in cals[:12]:
            try:
                data = await self._get(
                    f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(cal['id'])}/events",
                    timeMin=start.isoformat(), timeMax=end.isoformat(), singleEvents="true",
                    orderBy="startTime", maxResults=str(limit))
            except (httpx.HTTPError, ValueError):
                continue
            for e in data.get("items", []):
                if e.get("status") == "cancelled":
                    continue
                s, en = e.get("start", {}), e.get("end", {})
                all_day = "date" in s
                begin = datetime.fromisoformat(s["date"]).astimezone() if all_day else \
                    datetime.fromisoformat(s["dateTime"].replace("Z", "+00:00")).astimezone()
                title = e.get("summary") or "(senza titolo)"
                kind = ("birthday" if e.get("eventType") == "birthday" or "#contacts@" in cal["id"]
                        or all_day and re.search(r"complean|birthday|\bauguri\b", title, re.I)
                        else "event" if all_day or "#holiday@" in cal["id"] else "appointment")
                out.append({"id": e.get("id"), "cal_id": cal["id"], "title": title, "kind": kind,
                            "start": begin,
                            "all_day": all_day, "where": e.get("location", ""),
                            "calendar": "" if cal.get("primary") else cal.get("summary", ""),
                            "end": en.get("dateTime") or en.get("date")})
        out.sort(key=lambda x: x["start"])
        return out[:limit]

    async def add_event(self, title: str, start: datetime, all_day: bool, minutes: int = 60) -> dict:
        if all_day:
            body = {"summary": title, "start": {"date": start.date().isoformat()},
                    "end": {"date": (start.date() + timedelta(days=1)).isoformat()}}
        else:
            body = {"summary": title, "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": (start + timedelta(minutes=minutes)).isoformat()}}
        return await self._call("POST", "https://www.googleapis.com/calendar/v3/calendars/primary/events", json=body)

    async def mails(self, query: str = "is:unread in:inbox", limit: int = 5) -> tuple[int, list[dict]]:
        base = "https://gmail.googleapis.com/gmail/v1/users/me"
        data = await self._get(f"{base}/messages", q=query, maxResults=str(max(1, limit)))
        total = data.get("resultSizeEstimate", 0)
        out = []
        for m in data.get("messages", [])[:limit]:
            msg = await self._get(f"{base}/messages/{m['id']}", format="metadata",
                                  metadataHeaders=["From", "Subject", "Date"])
            h = {x["name"].lower(): x["value"] for x in msg.get("payload", {}).get("headers", [])}
            sender = re.sub(r"\s*<[^>]+>", "", h.get("from", "")).strip('" ') or h.get("from", "")
            out.append({"id": m["id"], "from": sender, "subject": h.get("subject") or "(senza oggetto)",
                        "snippet": msg.get("snippet", ""),
                        "at": int(msg.get("internalDate", "0")) / 1000})
        return total, out

    async def tasks(self, limit: int = 20) -> list[dict]:
        data = await self._get("https://tasks.googleapis.com/tasks/v1/lists/@default/tasks",
                               showCompleted="false", maxResults=str(limit))
        return [{"id": t.get("id"), "title": t.get("title", ""), "due": (t.get("due") or "")[:10],
                 "notes": t.get("notes", "")}
                for t in data.get("items", []) if t.get("title")]

    async def add_task(self, title: str, due: date | None = None) -> dict:
        body = {"title": title}
        if due:
            body["due"] = f"{due.isoformat()}T00:00:00.000Z"
        return await self._call("POST", "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks", json=body)

    async def contacts(self, query: str) -> list[dict]:
        url = "https://people.googleapis.com/v1/people:searchContacts"
        mask = "names,phoneNumbers,emailAddresses"
        data = await self._get(url, query=query, readMask=mask, pageSize="5")
        if not data.get("results"):
            await self._get(url, query="", readMask=mask)
            await asyncio.sleep(1)
            data = await self._get(url, query=query, readMask=mask, pageSize="5")
        out = []
        for r in data.get("results", []):
            p = r.get("person", {})
            out.append({"name": ((p.get("names") or [{}])[0]).get("displayName", ""),
                        "phones": [x.get("value", "") for x in p.get("phoneNumbers", [])],
                        "emails": [x.get("value", "") for x in p.get("emailAddresses", [])]})
        return out

    async def files(self, query: str, limit: int = 8) -> list[dict]:
        q = query.replace("\\", "").replace("'", "\\'")
        data = await self._get("https://www.googleapis.com/drive/v3/files",
                               q=f"(name contains '{q}' or fullText contains '{q}') and trashed = false",
                               pageSize=str(limit), orderBy="modifiedTime desc",
                               fields="files(name,mimeType,modifiedTime,webViewLink)")
        return data.get("files", [])

    async def notes(self, limit: int = 10) -> list[dict]:
        data = await self._get("https://keep.googleapis.com/v1/notes", pageSize=str(limit), filter="trashed=false")
        out = []
        for n in data.get("notes", []):
            body = n.get("body", {})
            text = (body.get("text") or {}).get("text", "")
            if not text and body.get("list"):
                text = ", ".join(i.get("text", {}).get("text", "") for i in body["list"].get("listItems", []))
            out.append({"id": n.get("name", ""), "title": n.get("title", ""), "text": text})
        return out

    async def add_note(self, text: str) -> dict:
        title, _, rest = text.partition(":")
        body = {"title": title.strip()[:80], "body": {"text": {"text": rest.strip()}}} if rest.strip() else \
            {"title": "", "body": {"text": {"text": text.strip()}}}
        return await self._call("POST", "https://keep.googleapis.com/v1/notes", json=body)

    async def delete_event(self, cal_id: str, event_id: str) -> None:
        await self._call("DELETE", f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(cal_id)}"
                                   f"/events/{urllib.parse.quote(event_id)}")

    async def complete_task(self, task_id: str) -> dict:
        return await self._call("PATCH", f"https://tasks.googleapis.com/tasks/v1/lists/@default/tasks/"
                                         f"{urllib.parse.quote(task_id)}", json={"status": "completed"})

    async def mail_text(self, mail_id: str, limit: int = 1500) -> str:
        msg = await self._get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{urllib.parse.quote(mail_id)}",
                              format="full")
        parts = [msg.get("payload", {})]
        plain, rich = "", ""
        while parts:
            part = parts.pop(0)
            parts.extend(part.get("parts") or [])
            data = (part.get("body") or {}).get("data")
            if not data:
                continue
            text = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
            if part.get("mimeType") == "text/plain" and not plain:
                plain = text
            elif part.get("mimeType") == "text/html" and not rich:
                rich = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(style|script).*?</\1>", " ", text)))
        body = plain or rich or msg.get("snippet", "")
        body = re.split(r"\n(?:>|On .+ wrote:|Il giorno .+ ha scritto:)", body)[0]
        return re.sub(r"\s+", " ", body).strip()[:limit]

    async def free_slots(self, day: date, start_hour: int = 8, end_hour: int = 20) -> list[tuple[datetime, datetime]]:
        begin = datetime.combine(day, datetime.min.time()).replace(hour=start_hour).astimezone()
        finish = begin.replace(hour=end_hour)
        busy = []
        for e in await self.events(begin, finish, 50):
            if e["all_day"]:
                continue
            end = datetime.fromisoformat(e["end"].replace("Z", "+00:00")).astimezone() if e.get("end") else \
                e["start"] + timedelta(hours=1)
            busy.append((max(e["start"], begin), min(end, finish)))
        busy.sort()
        slots, cursor = [], max(begin, datetime.now().astimezone()) if day == date.today() else begin
        for s0, e0 in busy:
            if s0 - cursor >= timedelta(minutes=30):
                slots.append((cursor, s0))
            cursor = max(cursor, e0)
        if finish - cursor >= timedelta(minutes=30):
            slots.append((cursor, finish))
        return slots
