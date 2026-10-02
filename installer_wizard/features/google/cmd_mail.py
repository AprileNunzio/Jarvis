import re
from features.google import panels
from features.google.commands import Ctx

_SENDER = re.compile(r"\b(?:da|di)\s+([A-Za-zÀ-ÿ'][\wÀ-ÿ'. -]{1,40})$", re.I)
_TOPIC = re.compile(r"\b(?:su|riguardo(?: a)?|che parla(?:no)? di|con oggetto)\s+(.{2,60})$", re.I)
_NOT_SENDER = re.compile(r"^(?:oggi|ieri|stamattina|nuove|non lette|posta|gmail)\b", re.I)


def _query(text: str) -> tuple[str, str]:
    clean = text.strip(" ?!.")
    sender = _SENDER.search(clean)
    if sender and not _NOT_SENDER.match(sender.group(1)):
        who = sender.group(1).strip()
        return f"from:({who}) in:inbox", f"da {who}"
    topic = _TOPIC.search(clean)
    if topic:
        what = topic.group(1).strip(" \"'«»")
        return f"{what} in:inbox", f"su «{what}»"
    return "is:unread in:inbox", ""


def _private_reply(ctx: Ctx, total: int) -> tuple[str, dict]:
    return (f"{ctx.name}, ha {total} email non lett{'a' if total == 1 else 'e'}. Ci sono altre persone qui: "
            "le dirò mittenti e contenuti quando sarà da solo.", {"mode": "face"})


async def inbox(text: str, ctx: Ctx) -> tuple[str, dict]:
    query, label = _query(text)
    total, mails = await ctx.session.mails(query, 6)
    if not label:
        ctx.session.unread = total
    if not ctx.private:
        return _private_reply(ctx, total if not label else len(mails))
    if not mails:
        return (f"Non trovo email {label}." if label else f"{ctx.name}, nessuna email da leggere. Casella in ordine."), \
            {"mode": "face"}
    if label:
        last = mails[0]
        speech = f"L'ultima email {label} è di {last['from']}, oggetto «{last['subject']}». {last['snippet'][:160]}"
        title = f"Email {label}"
    else:
        speech = f"{ctx.name}, ha {total} email non lett{'a' if total == 1 else 'e'}. " + " ".join(
            f"Da {x['from']}: {x['subject']}." for x in mails[:3])
        title = f"Posta di {ctx.name} — {total} non lette"
    return speech, {"mode": "focus", "title": title, "subtitle": ctx.email,
                    "panels": [panels.mail(total if not label else len(mails), mails, "Messaggi")]}


async def read(text: str, ctx: Ctx) -> tuple[str, dict]:
    query, label = _query(text)
    if not ctx.private:
        total, _ = await ctx.session.mails("is:unread in:inbox", 0)
        return _private_reply(ctx, total)
    _, mails = await ctx.session.mails(query, 1)
    if not mails and not label:
        _, mails = await ctx.session.mails("in:inbox", 1)
    if not mails:
        return f"Non trovo email {label or 'recenti'}.", {"mode": "face"}
    m = mails[0]
    body = await ctx.session.mail_text(m["id"])
    speech = f"Email di {m['from']}, oggetto «{m['subject']}». {body[:600]}"
    return speech, {"mode": "focus", "title": m["subject"], "subtitle": f"{m['from']} · {ctx.email}",
                    "panels": [panels.mail_body(m, body)]}
