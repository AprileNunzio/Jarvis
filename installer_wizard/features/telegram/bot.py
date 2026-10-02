import asyncio
import html
import json
import logging
import re
import secrets
import time

import httpx

from config import STATE_DIR, env_get
from state import store

log = logging.getLogger("jarvis.telegram")
DATA_FILE = STATE_DIR / "telegram.json"
API = "https://api.telegram.org"
PAIR_TTL = 600
COMMANDS = [
    ("stato", "Stato del sistema"), ("chi", "Chi c'è davanti alla webcam"), ("foto", "Foto dalla webcam"),
    ("meteo", "Previsioni della settimana"), ("rete", "Dispositivi in rete"), ("ricorrenze", "Compleanni, onomastici e scadenze"),
    ("voce", "Risposte vocali on/off"), ("notifiche", "Notifiche on/off"), ("aggiorna", "Installa gli aggiornamenti"),
    ("ripara", "Verifica e ripara tutto"), ("riavvia", "Riavvia il sistema"), ("aiuto", "Elenco dei comandi"),
]
OWNER_ONLY = {"aggiorna", "ripara", "riavvia"}
TAG_RE = re.compile(r"</?(?:b|i|u|s|code|pre|a)(?:\s[^>]*)?>", re.I)


def esc(value) -> str:
    return html.escape(str(value), quote=False)


def plain(text: str) -> str:
    return html.unescape(TAG_RE.sub("", text))


class TelegramBot:
    def __init__(self) -> None:
        self.data = self._load()
        self.pair_code = None
        self.pair_expires = 0.0
        self.me: dict = {}
        self.status = "non configurato"
        self.offset = 0
        self.handlers: dict = {}
        self._last_event_count = 0
        self._last_phase = None
        self._last_daily = ""

    def _load(self) -> dict:
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"chats": {}}

    def _save(self) -> None:
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(DATA_FILE)

    @property
    def token(self) -> str:
        if env_get("JARVIS_TELEGRAM", "1") == "0":
            return ""
        return env_get("JARVIS_TELEGRAM_TOKEN", "").strip()

    def new_pair_code(self) -> dict:
        self.pair_code = f"{secrets.randbelow(1_000_000):06d}"
        self.pair_expires = time.time() + PAIR_TTL
        return {"code": self.pair_code, "expires_in": PAIR_TTL}

    def summary(self) -> dict:
        return {"configured": bool(self.token), "status": self.status, "bot": self.me.get("username"),
                "chats": [{"id": k, **v} for k, v in self.data["chats"].items()],
                "pair_code": self.pair_code if time.time() < self.pair_expires else None,
                "pair_expires_in": max(0, int(self.pair_expires - time.time()))}

    def update_chat(self, chat_id: str, changes: dict) -> None:
        chat = self.data["chats"].get(str(chat_id))
        if not chat:
            raise KeyError(chat_id)
        for key in ("notify", "voice", "role", "person"):
            if key in changes:
                chat[key] = changes[key]
        self._save()

    def remove_chat(self, chat_id: str) -> None:
        self.data["chats"].pop(str(chat_id), None)
        self._save()

    async def call(self, method: str, timeout: float = 30, **params):
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{API}/bot{self.token}/{method}", json=params)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "errore Telegram"))
        return data["result"]

    async def upload(self, method: str, chat_id, field: str, filename: str, content: bytes, mime: str, **params):
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{API}/bot{self.token}/{method}", data={"chat_id": chat_id, **params},
                                  files={field: (filename, content, mime)})
        return r.json()

    async def send(self, chat_id, text: str, **extra) -> None:
        try:
            await self.call("sendMessage", chat_id=chat_id, text=text[:4000], parse_mode="HTML", **extra)
        except RuntimeError as exc:
            if "parse" not in str(exc).lower():
                log.warning("Invio a %s non riuscito: %s", chat_id, exc)
                return
            await self._send_plain(chat_id, text, extra)
        except httpx.HTTPError as exc:
            log.warning("Invio a %s non riuscito: %s", chat_id, exc)

    async def _send_plain(self, chat_id, text: str, extra: dict) -> None:
        try:
            await self.call("sendMessage", chat_id=chat_id, text=plain(text)[:4000], **extra)
        except (httpx.HTTPError, RuntimeError) as exc:
            log.warning("Invio a %s non riuscito: %s", chat_id, exc)

    async def send_photo(self, chat_id, jpeg: bytes, caption: str = "") -> None:
        result = await self.upload("sendPhoto", chat_id, "photo", "jarvis.jpg", jpeg, "image/jpeg",
                                   caption=caption[:1000], parse_mode="HTML")
        if not result.get("ok"):
            await self.upload("sendPhoto", chat_id, "photo", "jarvis.jpg", jpeg, "image/jpeg",
                              caption=plain(caption)[:1000])

    async def send_voice(self, chat_id, text: str, lang: str | None = None) -> None:
        synth = self.handlers.get("tts")
        if not synth:
            return
        try:
            wav = await synth(text, lang=lang)
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            ogg, _ = await asyncio.wait_for(proc.communicate(wav), 60)
            if ogg:
                await self.upload("sendVoice", chat_id, "voice", "jarvis.ogg", ogg, "audio/ogg")
        except (OSError, RuntimeError, asyncio.TimeoutError, httpx.HTTPError) as exc:
            log.warning("Risposta vocale non inviata: %s", exc)

    async def notify(self, text: str, photo: bytes | None = None) -> None:
        for chat_id, chat in self.data["chats"].items():
            if not chat.get("notify", True):
                continue
            if photo:
                await self.send_photo(chat_id, photo, text)
            else:
                await self.send(chat_id, text)

    async def run(self) -> None:
        while True:
            if not self.token:
                self.status, self.me = ("disattivato" if env_get("JARVIS_TELEGRAM", "1") == "0"
                                        else "non configurato"), {}
                await asyncio.sleep(10)
                continue
            try:
                self.me = await self.call("getMe")
                await self.call("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS])
                self.status = "attivo"
                log.info("Bot Telegram attivo: @%s", self.me.get("username"))
                current = self.token
                watcher = asyncio.create_task(self._watch_events())
                try:
                    while self.token == current:
                        updates = await self._poll()
                        for upd in updates:
                            self.offset = upd["update_id"] + 1
                            asyncio.create_task(self._handle(upd))
                finally:
                    watcher.cancel()
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                self.status = f"errore: {exc}"
                log.warning("Telegram: %s", exc)
                await asyncio.sleep(15)

    async def _poll(self) -> list:
        async with httpx.AsyncClient(timeout=70) as client:
            r = await client.post(f"{API}/bot{self.token}/getUpdates",
                                  json={"offset": self.offset, "timeout": 50,
                                        "allowed_updates": ["message", "callback_query"]})
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(data.get("description", "getUpdates non riuscito"))
        return data["result"]

    async def _handle(self, upd: dict) -> None:
        if "callback_query" in upd:
            return await self._callback(upd["callback_query"])
        msg = upd.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = (msg.get("text") or "").strip()
        user = msg.get("from", {})
        name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or user.get("username", "")
        chat = self.data["chats"].get(chat_id)

        if not chat:
            if self.pair_code and time.time() < self.pair_expires and text == self.pair_code:
                role = "owner" if not self.data["chats"] else "member"
                self.data["chats"][chat_id] = {"name": name, "username": user.get("username"), "role": role,
                                               "notify": True, "voice": True, "added": time.time()}
                self._save()
                self.pair_code = None
                store.event("INFO", f"Telegram: abbinato {name} ({role})", "telegram")
                await self.send(chat_id, f"✅ Abbinamento completato, {esc(name)}. Sono <b>Jarvis</b>.\n"
                                         "Scrivimi o mandami un messaggio vocale. /aiuto per i comandi.")
            else:
                await self.send(chat_id, "🔒 Questo è il bot privato di un sistema Jarvis.\n"
                                         "Per abbinarti apri il pannello di Jarvis → Telegram → «Genera codice» "
                                         "e inviami il codice a 6 cifre.")
            return

        if msg.get("voice") or msg.get("audio"):
            return await self._voice_message(chat_id, chat, msg)
        if msg.get("location"):
            return await self._location(chat_id, chat, msg["location"])
        if not text:
            return
        if text.startswith("/"):
            command = text[1:].split()[0].split("@")[0].lower()
            return await self._command(chat_id, chat, command, text.split()[1:])
        await self._chat(chat_id, chat, text)

    async def _location(self, chat_id: str, chat: dict, loc: dict) -> None:
        if chat.get("role") != "owner":
            await self.send(chat_id, "Solo il proprietario può impostare la posizione di Jarvis.")
            return
        from features.location.locator import locator
        try:
            entry = await locator.report("phone", float(loc["latitude"]), float(loc["longitude"]),
                                         float(loc.get("horizontal_accuracy") or 30))
        except (KeyError, ValueError) as exc:
            await self.send(chat_id, f"Posizione non valida: {esc(exc)}")
            return
        store.event("INFO", f"Posizione aggiornata da Telegram: {entry['name']}", "location")
        await self.send(chat_id, f"📍 Ricevuto: ora so di trovarmi a <b>{esc(entry['name'])}</b>. "
                                 "La userò per meteo e servizi locali.")

    async def _chat(self, chat_id: str, chat: dict, text: str) -> None:
        handler = self.handlers.get("chat")
        if not handler:
            return
        await self.call("sendChatAction", chat_id=chat_id, action="typing")
        try:
            result = await handler(text, f"telegram:{chat_id}")
        except Exception as exc:
            await self.send(chat_id, f"⚠️ {esc(getattr(exc, 'detail', exc))}")
            return
        await self.send(chat_id, esc(result["reply"]))
        ui = result.get("ui") or {}
        for panel in ui.get("panels", []):
            if panel.get("type") == "forecast":
                days = panel["data"]["days"]
                lines = [f"{d['label']}: {d['desc']}, {d['tmin']}°/{d['tmax']}°, pioggia {d['rain'] or 0}%" for d in days]
                await self.send(chat_id, "🌤 <b>" + esc(ui.get("title", "Meteo")) + "</b>\n" + esc("\n".join(lines)))
            elif panel.get("type") == "image" and self.handlers.get("snapshot"):
                jpeg = await self.handlers["snapshot"]()
                if jpeg:
                    await self.send_photo(chat_id, jpeg, esc(ui.get("title", "")))
        if chat.get("voice", True):
            await self.send_voice(chat_id, result["reply"], result.get("lang"))

    async def _voice_message(self, chat_id: str, chat: dict, msg: dict) -> None:
        stt = self.handlers.get("stt")
        if not stt:
            return await self.send(chat_id, "L'ascolto vocale non è attivo su questo Jarvis.")
        media = msg.get("voice") or msg.get("audio")
        await self.call("sendChatAction", chat_id=chat_id, action="typing")
        try:
            info = await self.call("getFile", file_id=media["file_id"])
            async with httpx.AsyncClient(timeout=60) as client:
                raw = (await client.get(f"{API}/file/bot{self.token}/{info['file_path']}")).content
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ar", "16000", "-ac", "1", "-f", "s16le", "pipe:1",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            pcm, _ = await asyncio.wait_for(proc.communicate(raw), 60)
            text = await stt(pcm)
        except Exception as exc:
            return await self.send(chat_id, f"⚠️ Non sono riuscito a capire il messaggio vocale ({esc(exc)}).")
        if not text:
            return await self.send(chat_id, "Non ho sentito nulla nel messaggio vocale.")
        await self.send(chat_id, f"🎙 <i>{esc(text)}</i>")
        await self._chat(chat_id, chat, text)

    async def _command(self, chat_id: str, chat: dict, command: str, args: list) -> None:
        if command in OWNER_ONLY and chat.get("role") != "owner":
            return await self.send(chat_id, "⛔ Comando riservato al proprietario.")
        h = self.handlers
        if command in ("start", "aiuto", "help"):
            await self.send(chat_id, "🤖 <b>Jarvis</b> — comandi disponibili:\n" +
                            "\n".join(f"/{c} — {d}" for c, d in COMMANDS) +
                            "\n\nOppure scrivimi o mandami un vocale come faresti di persona.")
        elif command == "stato":
            s = store
            comps = "\n".join(f"{'🟢' if c['status'] == 'ok' else '🟠' if c['status'] == 'warn' else '🔴'} {c['label']}: {c['detail']}"
                              for c in s.components.values())
            sysinfo = s.system or {}
            extra = (f"\n\nCPU {sysinfo.get('cpu_percent', 0):.0f}% · RAM {sysinfo.get('mem_percent', 0):.0f}% · "
                     f"Disco {sysinfo.get('disk_percent', 0):.0f}%") if sysinfo else ""
            await self.send(chat_id, f"<b>{esc(s.snapshot()['phase_label'])}</b>\n{esc(s.message)}\n\n{esc(comps)}{extra}")
        elif command in ("chi", "foto"):
            summary = (store.presence or {}).get("summary") or "La webcam non è disponibile."
            jpeg = await h["snapshot"]() if h.get("snapshot") else None
            if jpeg:
                await self.send_photo(chat_id, jpeg, esc(summary) if command == "chi" else "📷 Webcam")
            else:
                await self.send(chat_id, esc(summary))
        elif command == "rete":
            data = h["network"]() if h.get("network") else {"devices": []}
            online = [d for d in data["devices"] if d.get("online")]
            lines = [f"{d['icon']} {d['label']} — {d.get('ip', '')}" for d in online[:40]]
            await self.send(chat_id, f"📡 <b>Rete {esc(data.get('subnet', ''))}</b> — {len(online)} connessi\n" + esc("\n".join(lines)))
        elif command == "meteo":
            await self._chat(chat_id, chat, "che tempo fa questa settimana?")
        elif command == "ricorrenze":
            items = h["reminders"](30) if h.get("reminders") else []
            icons = {"compleanno": "🎂", "onomastico": "🌼", "evento": "📅", "scadenza": "⚠️"}
            text = "\n".join(f"{icons.get(r['type'], '•')} {r['title']} — " +
                             ("oggi" if r["days"] == 0 else "domani" if r["days"] == 1 else f"tra {r['days']} giorni")
                             for r in items) or "Nessuna ricorrenza nei prossimi 30 giorni."
            await self.send(chat_id, "<b>Prossime ricorrenze</b>\n" + esc(text))
        elif command in ("voce", "notifiche"):
            key = "voice" if command == "voce" else "notify"
            value = (args[0].lower() in ("on", "si", "sì", "1")) if args else not chat.get(key, True)
            chat[key] = value
            self._save()
            await self.send(chat_id, f"{'🔊' if key == 'voice' else '🔔'} {command.capitalize()}: {'attive' if value else 'disattivate'}")
        elif command == "aggiorna":
            await self.send(chat_id, await h["update"]())
        elif command == "ripara":
            await self.send(chat_id, await h["repair"]())
        elif command == "riavvia":
            await self.call("sendMessage", chat_id=chat_id, text="Vuoi davvero riavviare il sistema?",
                            reply_markup={"inline_keyboard": [[{"text": "🔁 Sì, riavvia", "callback_data": "reboot"},
                                                               {"text": "Annulla", "callback_data": "cancel"}]]})
        else:
            await self.send(chat_id, "Comando sconosciuto. /aiuto per l'elenco.")

    async def _callback(self, cq: dict) -> None:
        chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
        chat = self.data["chats"].get(chat_id)
        await self.call("answerCallbackQuery", callback_query_id=cq["id"])
        if not chat or chat.get("role") != "owner":
            return
        if cq.get("data") == "reboot":
            await self.send(chat_id, "🔁 Riavvio in corso: le scrivo quando sono di nuovo operativo.")
            store.event("INFO", "Riavvio richiesto da Telegram", "telegram")
            await self.handlers["reboot"]()
        else:
            await self.send(chat_id, "Annullato.")

    async def _watch_events(self) -> None:
        announced_boot = False
        while True:
            await asyncio.sleep(3)
            if not announced_boot and store.phase == "READY":
                announced_boot = True
                await self.notify(f"✅ <b>Jarvis operativo</b> (avvio n. {store.boot_count}).")
            if self._last_phase and store.phase != self._last_phase and store.phase in ("DEGRADED", "ERROR"):
                await self.notify(f"🟠 <b>{esc(store.snapshot()['phase_label'])}</b>\n{esc(store.message)}\n{esc(store.last_error)}")
            self._last_phase = store.phase
            greeting = getattr(store, "greeting", {}) or {}
            if greeting.get("id") and greeting.get("id") != self.data.get("last_greeting"):
                self.data["last_greeting"] = greeting["id"]
                jpeg = await self.handlers["snapshot"]() if self.handlers.get("snapshot") else None
                who = ", ".join(greeting.get("names") or []) or "una persona non riconosciuta"
                await self.notify(f"👁 Davanti a Jarvis: <b>{esc(who)}</b>\n«{esc(greeting.get('text', ''))}»", jpeg)
            today = time.strftime("%Y-%m-%d")
            if time.localtime().tm_hour >= 8 and self._last_daily != today and self.handlers.get("reminders"):
                self._last_daily = today
                items = [r for r in self.handlers["reminders"](0)]
                if items:
                    await self.notify("📅 <b>Oggi</b>\n" + "\n".join(f"• {esc(r['title'])}" for r in items))


bot = TelegramBot()
