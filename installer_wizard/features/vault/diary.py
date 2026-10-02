import json
from datetime import date, datetime, timedelta

from config import DEMO
from state import AUDIT_FILE

DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
          "novembre", "dicembre"]


def bounds(day: date) -> tuple[float, float]:
    start = datetime.combine(day, datetime.min.time()).timestamp()
    return start, start + 86400


def _hm(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def gather(day: date, requests: list[dict]) -> dict:
    start, end = bounds(day)
    inside = lambda t: start <= (t or 0) < end
    data: dict = {"requests": [r for r in requests if inside(r["at"])]}
    try:
        from features.automations.library import library
        data["runs"] = [r for r in library.history(400) if inside(r.get("started")) and r.get("status") != "condizioni non soddisfatte"]
    except Exception:
        data["runs"] = []
    try:
        from features.autonomy import journal
        data["autonomy"] = [e for e in journal.recent(200, start) if inside(e["at"])]
    except Exception:
        data["autonomy"] = []
    try:
        from features.people import people
        seen = []
        for p in people.all_profiles():
            visits = [s for s in p.get("sessions") or [] if inside(s[0])]
            if visits:
                seen.append({"name": people.display_name(p), "first": visits[0][0], "minutes": sum((s[1] - s[0]) for s in visits) / 60})
        data["people"] = sorted(seen, key=lambda x: x["first"])
    except Exception:
        data["people"] = []
    try:
        from features.mind.mind import mind
        data["learned"] = [f for f in mind.memory.facts if inside(f.get("created"))]
    except Exception:
        data["learned"] = []
    try:
        from features.habits.service import habits
        data["odd"] = [a for a in habits.data.get("anomalies", []) if inside(a["at"])]
        data["habits"] = [s for s in habits.data["suggestions"].values() if inside(s.get("decided") or s.get("created"))]
    except Exception:
        data["odd"], data["habits"] = [], []
    try:
        from features.selftest.service import selftest
        data["selftest"] = [r for r in selftest.data["history"] if inside(r["at"])]
    except Exception:
        data["selftest"] = []
    data["problems"] = []
    try:
        for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines()[-3000:]:
            e = json.loads(line)
            ts = datetime.fromisoformat(e["ts"]).timestamp()
            if inside(ts) and e.get("level") in ("ERROR", "WARN"):
                data["problems"].append({"at": ts, "text": e["msg"][:160]})
    except (OSError, ValueError, KeyError):
        pass
    return data


def facts_line(data: dict) -> str:
    parts = [f"{len(data['requests'])} richieste", f"{len(data['runs'])} automazioni eseguite"]
    if data["people"]:
        parts.append("presenti " + ", ".join(p["name"] for p in data["people"]))
    if data["odd"]:
        parts.append(f"{len(data['odd'])} situazioni insolite")
    if data["problems"]:
        parts.append(f"{len(data['problems'])} avvisi di sistema")
    return "; ".join(parts)


async def summary(data: dict) -> str:
    if DEMO or not (data["requests"] or data["runs"] or data["people"]):
        return ""
    try:
        from features.brain.llm import generate
        prompt = ("Scrivi in italiano, in due o tre frasi, il riassunto di questa giornata di Jarvis per il diario, dando del Lei "
                  "all'utente. Solo fatti presenti qui:\n" + json.dumps({
                      "richieste": [r["text"] for r in data["requests"]][:30], "persone": [p["name"] for p in data["people"]],
                      "automazioni": [r["name"] + ": " + r["status"] for r in data["runs"]][:20],
                      "imparato": [f["text"] for f in data["learned"]][:10], "insolito": [a["text"] for a in data["odd"]],
                      "autonomia": [e["title"] + ": " + e["text"][:120] for e in data["autonomy"]][:10]}, ensure_ascii=False))
        text = await generate(prompt, kind="chat", max_tokens=180, timeout=180)
        return str(text).strip()
    except Exception:
        return ""


def render(day: date, data: dict, recap: str, final: bool) -> str:
    title = f"{DAYS[day.weekday()].capitalize()} {day.day} {MONTHS[day.month - 1]} {day.year}"
    out = [f"# {title}", ""]
    if not final:
        out += [f"_Giornata in corso: aggiornato alle {datetime.now():%H:%M}._", ""]
    if recap:
        out += ["## Riassunto", recap, ""]
    out += [f"**In breve**: {facts_line(data)}.", ""]
    if data["people"]:
        out += ["## Chi c'era"] + [f"- {p['name']}: dalle {_hm(p['first'])}, circa {p['minutes']:.0f} minuti" for p in data["people"]] + [""]
    if data["requests"]:
        out += ["## Richieste a Jarvis"] + [f"- {_hm(r['at'])} — {r['text']}" for r in data["requests"][-40:]] + [""]
    if data["runs"]:
        out += ["## Automazioni"] + [f"- {_hm(r['started'])} — {r['name']}: {r['status']}" + (f" ({r['error']})" if r.get("error") else "")
                                     for r in data["runs"][-40:]] + [""]
    if data["autonomy"]:
        out += ["## In autonomia"] + [f"- {_hm(e['at'])} — {e['title']}: {e['text'][:200]}" for e in data["autonomy"]] + [""]
    if data["learned"]:
        out += ["## Ho imparato"] + [f"- {f['text']}" for f in data["learned"]] + [""]
    if data["odd"]:
        out += ["## Situazioni insolite"] + [f"- {_hm(a['at'])} — {a['text']}" for a in data["odd"]] + [""]
    if data["habits"]:
        out += ["## Abitudini"] + [f"- {s['text']} ({s['status']})" for s in data["habits"]] + [""]
    if data["selftest"]:
        out += ["## Collaudo"] + [f"- {_hm(r['at'])} ({r['reason']}): {r['passed']} superate, {r['failed']} fallite" for r in data["selftest"]] + [""]
    if data["problems"]:
        out += ["## Avvisi di sistema"] + [f"- {_hm(p['at'])} — {p['text']}" for p in data["problems"][-20:]] + [""]
    return "\n".join(out)


def path_for(root, day: date):
    return root / "Diario" / f"{day.year}" / f"{day.month:02d}" / f"{day.isoformat()}.md"


def yesterday() -> date:
    return date.today() - timedelta(days=1)

