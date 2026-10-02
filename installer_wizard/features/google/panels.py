from datetime import date, datetime

from features.google.timeparse import say_day

_MIME = {"document": "doc", "spreadsheet": "sheet", "presentation": "slides", "pdf": "pdf", "folder": "folder",
         "image": "image", "video": "video", "audio": "audio", "form": "form"}


def _end(e: dict) -> str:
    raw = e.get("end") or ""
    if not raw or e["all_day"]:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone().strftime("%H:%M")
    except ValueError:
        return ""


def calendar(events: list[dict], label: str, owner: str) -> dict:
    rows = [{"title": e["title"], "where": e["where"], "calendar": e["calendar"], "all_day": e["all_day"],
             "day": say_day(e["start"].date()), "date": e["start"].date().isoformat(),
             "start": e["start"].strftime("%H:%M"), "end": _end(e), "ts": e["start"].timestamp()} for e in events]
    return {"type": "gcal", "title": f"Agenda di {owner}", "data": {"label": label, "events": rows}}


def free(day: date, slots: list, busy: list[dict]) -> dict:
    return {"type": "gfree", "title": f"Tempo libero — {say_day(day)}",
            "data": {"from": 8, "to": 20,
                     "slots": [[a.hour + a.minute / 60, b.hour + b.minute / 60] for a, b in slots],
                     "busy": [{"title": e["title"], "start": e["start"].hour + e["start"].minute / 60,
                               "end": _hour(_end(e)) or e["start"].hour + e["start"].minute / 60 + 1}
                              for e in busy if not e["all_day"]]}}


def _hour(hm: str) -> float | None:
    if not hm:
        return None
    h, m = hm.split(":")
    return int(h) + int(m) / 60


def mail(total: int, mails: list[dict], title: str) -> dict:
    return {"type": "gmail", "title": title,
            "data": {"total": total, "items": [{"from": m["from"], "subject": m["subject"], "snippet": m["snippet"][:180],
                                                "when": datetime.fromtimestamp(m["at"]).strftime("%d/%m %H:%M")}
                                               for m in mails]}}


def mail_body(m: dict, body: str) -> dict:
    return {"type": "gmailread", "title": "Messaggio",
            "data": {"from": m["from"], "subject": m["subject"], "body": body,
                     "when": datetime.fromtimestamp(m["at"]).strftime("%d/%m/%Y %H:%M")}}


def tasks(items: list[dict], done: str = "") -> dict:
    today = date.today()
    rows = [{"title": t["title"], "due": say_day(date.fromisoformat(t["due"])) if t["due"] else "",
             "late": bool(t["due"]) and date.fromisoformat(t["due"]) < today, "notes": t.get("notes", "")[:120]}
            for t in items]
    return {"type": "gtasks", "title": "Cose da fare", "data": {"items": rows, "done": done}}


def notes(items: list[dict]) -> dict:
    return {"type": "gnotes", "title": "Google Keep", "data": {"items": [{"title": n["title"], "text": n["text"][:400]}
                                                                         for n in items]}}


def contact(p: dict) -> dict:
    return {"type": "gcontact", "title": "Rubrica",
            "data": {"name": p["name"], "phones": p["phones"][:3], "emails": p["emails"][:3]}}


def drive(files: list[dict], query: str) -> dict:
    rows = []
    for f in files:
        mime = f.get("mimeType", "")
        kind = next((v for k, v in _MIME.items() if k in mime), "file")
        rows.append({"name": f.get("name", ""), "kind": kind, "modified": (f.get("modifiedTime") or "")[:10]})
    return {"type": "gdrive", "title": f"Drive — {query}", "data": {"files": rows}}
