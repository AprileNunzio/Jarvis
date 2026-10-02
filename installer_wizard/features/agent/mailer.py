import asyncio
import base64
import mimetypes
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

from config import env_get

MAX_ATTACH = 24 * 1024 * 1024
ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MailUnavailable(Exception):
    pass


def build(to: list[str], subject: str, body: str, files: list[Path], sender: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if sender:
        msg["From"] = sender
    msg.set_content(body)
    total = 0
    for f in files:
        data = f.read_bytes()
        total += len(data)
        if total > MAX_ATTACH:
            raise ValueError("allegati oltre 24 MB: meglio condividerli in una cartella SMB")
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        main, sub = ctype.split("/", 1)
        msg.add_attachment(data, maintype=main, subtype=sub, filename=f.name)
    return msg


def _gmail_session():
    try:
        from features.google.accounts import accounts
        from features.google.gservices import google
    except Exception:
        return None
    for slug in accounts.slugs():
        session = google.session(slug)
        if session and session.ready("gmail_send"):
            return session
    return None


def smtp_ready() -> bool:
    return bool(env_get("JARVIS_SMTP_HOST") and env_get("JARVIS_SMTP_USER"))


def _smtp_send(msg: EmailMessage) -> None:
    host, port = env_get("JARVIS_SMTP_HOST"), int(env_get("JARVIS_SMTP_PORT", "587") or 587)
    user, password = env_get("JARVIS_SMTP_USER"), env_get("JARVIS_SMTP_PASSWORD")
    if "From" not in msg:
        msg["From"] = env_get("JARVIS_SMTP_FROM") or user
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)


async def send(to: list[str], subject: str, body: str, files: list[Path]) -> str:
    bad = [a for a in to if not ADDRESS.match(a)]
    if not to or bad:
        raise ValueError(f"indirizzo email non valido: {', '.join(bad) or 'nessun destinatario'}")
    msg = build(to, subject, body, files)
    session = _gmail_session()
    if session:
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        await session._call("POST", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send", json={"raw": raw})
        return f"inviata con Gmail ({session.info.get('email', session.slug)})"
    if smtp_ready():
        await asyncio.to_thread(_smtp_send, msg)
        return f"inviata via SMTP ({env_get('JARVIS_SMTP_HOST')})"
    raise MailUnavailable("nessun account per inviare: collega Google con il permesso «Invio email» oppure imposta l'SMTP nel pannello")
