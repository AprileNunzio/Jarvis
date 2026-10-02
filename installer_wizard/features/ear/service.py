import asyncio
import json
import logging
import os
import re
import time

import numpy as np
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [jarvis.ear] %(levelname)s: %(message)s")
for noisy in ("websockets", "faster_whisper"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

import enhance
import stt
from learner import learner
from music import MusicTap
from voiceprint import ENROLLED_AT, Voiceprints
from wakeword import WakeWord

log = logging.getLogger("jarvis.ear")

RATE = 16000
PORT = int(os.environ.get("JARVIS_EAR_PORT", "8093"))
FRAME = 480
PRE_ROLL = int(0.4 * RATE)
END_SILENCE = 0.8
MAX_UTTERANCE = 14.0
MIN_UTTERANCE = 0.35
WAIT_FOR_SPEECH = 8.0
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
BARGE_IN = float(os.environ.get("JARVIS_BARGE_IN", "0.7"))

voiceprints = Voiceprints()
LINK_FILE = os.environ.get("JARVIS_EAR_LINK", "/var/lib/jarvis/ear_link.json")
LINK = {"clients": 0, "last_audio": 0.0, "level": 0.0, "since": time.time(), "pages": []}
SESSIONS: set = set()


def save_link() -> None:
    try:
        tmp = LINK_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({**LINK, "at": time.time()}, f)
        os.replace(tmp, LINK_FILE)
    except OSError as exc:
        log.debug("Stato del collegamento non salvato: %s", exc)


async def link_writer() -> None:
    while True:
        save_link()
        await asyncio.sleep(5)


class Session:

    def __init__(self, ws) -> None:
        self.ws = ws
        self.buffer = np.zeros(0, dtype=np.float32)
        self.ring = np.zeros(0, dtype=np.float32)
        self.noise = 0.004
        self.in_speech = False
        self.speech: list = []
        self.speech_start = 0.0
        self.last_voice = 0.0
        self.mode = "idle"
        self.listen_until = 0.0
        self.conversation = False
        self.awaiting_command = False
        self.instant = False
        self.jarvis_speaking = False
        self.last_level = 0.0
        self.waiting = 0
        self.raw: list | None = None
        self.alone: str | None = None
        self.enroll: dict | None = None
        self.music = MusicTap()
        self.profile = enhance.NoiseProfile()
        self.wake = WakeWord()
        self.page: dict = {}
        self.opened = time.time()

    async def send(self, **event) -> None:
        try:
            await self.ws.send(json.dumps(event))
        except websockets.ConnectionClosed:
            pass

    async def set_mode(self, mode: str, seconds: float = WAIT_FOR_SPEECH, conversation: bool = False) -> None:
        self.mode = mode
        self.conversation = conversation and mode == "listening"
        self.listen_until = time.time() + seconds if mode == "listening" else 0.0
        await self.send(type="state", state=mode, conversation=self.conversation)

    async def feed(self, pcm: bytes) -> None:
        if not self.page and time.time() - self.opened > 5 and any(s.page.get("visible") == "visible" for s in SESSIONS):
            log.info("Connessione senza identità chiusa: c'è una pagina visibile del display")
            await self.ws.close(4001, "pagina non identificata")
            return
        if self.raw is not None:
            self.raw.append(pcm)
            return
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        LINK["last_audio"] = time.time()
        if len(samples):
            LINK["level"] = round(float(np.sqrt(np.mean(samples * samples))), 4)
        self.buffer = np.concatenate([self.buffer, samples])
        while len(self.buffer) >= FRAME:
            frame, self.buffer = self.buffer[:FRAME], self.buffer[FRAME:]
            await self._frame(frame)

    async def _frame(self, frame: np.ndarray) -> None:
        now = time.time()
        rms = float(np.sqrt(np.mean(frame * frame)) + 1e-9)
        self.music.feed(frame, rms, self.noise, self.mode == "idle" and not self.jarvis_speaking, now)
        if now - self.last_level > 0.1:
            self.last_level = now
            await self.send(type="level", rms=round(min(1.0, rms * 12), 3), speech=self.in_speech,
                            wake=round(self.wake.score, 2))

        if self.jarvis_speaking:
            self.in_speech, self.speech = False, []
            if self.enroll is None and self.wake.feed(frame) and self.wake.score >= BARGE_IN:
                self.jarvis_speaking = False
                await self.send(type="barge")
                await self._instant_wake()
            return
        if self.mode == "idle" and self.enroll is None and self.wake.feed(frame):
            await self._instant_wake()
        if self.mode == "listening" and now > self.listen_until and (not self.in_speech or now > self.listen_until + 6):
            await self._listen_timeout()

        threshold = max(self.noise * 3.2, 0.010)
        voiced = rms > threshold
        if not self.in_speech:
            if not voiced:
                self.noise = self.noise * 0.97 + rms * 0.03
                self.profile.learn(frame)
            self.ring = np.concatenate([self.ring, frame])[-PRE_ROLL:]
            if voiced:
                self.in_speech, self.speech_start, self.last_voice = True, now, now
                self.speech = [self.ring.copy()]
            return

        self.speech.append(frame)
        if voiced:
            self.last_voice = now
        duration = now - self.speech_start
        if now - self.last_voice > END_SILENCE or duration > MAX_UTTERANCE:
            audio = np.concatenate(self.speech)
            self.in_speech, self.speech, self.ring = False, [], np.zeros(0, dtype=np.float32)
            instant, self.instant = self.instant, False
            if duration >= MIN_UTTERANCE:
                asyncio.create_task(self._utterance(audio, self.mode == "listening" or instant,
                                                    self.conversation, instant))

    async def _listen_timeout(self) -> None:
        if self.in_speech:
            self.in_speech, self.speech, self.ring = False, [], np.zeros(0, dtype=np.float32)
        if self.awaiting_command:
            self.awaiting_command = False
            learner.on_false_wake()
        if self.conversation:
            await self.send(type="conversation_end")
        await self.set_mode("idle")

    async def _instant_wake(self) -> None:
        self.instant = True
        self.awaiting_command = True
        learner.on_wake(None, 0)
        await self.send(type="wake", source="instant")
        await self.set_mode("listening")

    async def _utterance(self, audio: np.ndarray, attentive: bool, followup: bool, instant: bool) -> None:
        if not await asyncio.to_thread(stt.has_speech, audio):
            if instant:
                await self._wake_only()
            elif attentive and self.mode == "listening" and time.time() > self.listen_until:
                await self.set_mode("idle")
            return
        clean = await asyncio.to_thread(enhance.clean, audio, self.profile)
        if self.enroll is not None:
            await self._enroll_sample(clean)
            return
        if not attentive and self.waiting >= 2:
            return
        self.waiting += 0 if attentive else 1
        woke = instant
        try:
            async with stt.lock:
                t = time.time()
                if not attentive:
                    stt.refresh_hotwords()
                    probe, _ = await asyncio.to_thread(stt.transcribe, stt.head(clean), True, False)
                    if not learner.find_wake(probe):
                        learner.on_miss(probe)
                        await self.send(type="heard", text=probe)
                        return
                    woke = True
                    await self.send(type="wake", source="speech")
                await self.send(type="state", state="transcribing", conversation=followup)
                text, lang = await asyncio.to_thread(stt.transcribe, clean, False, True)
                ms = int((time.time() - t) * 1000)
        finally:
            self.waiting -= 0 if attentive else 1
        await self._deliver(text, lang, ms, clean, woke, followup)

    async def _deliver(self, text: str, lang: str, ms: int, clean: np.ndarray, woke: bool, followup: bool) -> None:
        found = learner.find_wake(text)
        command = text[found[1]:].strip(" ,.!?") if found and found[0] < 3 else text.strip()
        log.info("Sentito (%d ms, attivazione=%s, conversazione=%s): %s", ms, woke, followup, text)
        if woke and found:
            learner.on_wake(found[2], ms)
        if stt.hallucination(command) or len(command) <= 2:
            if woke or self.awaiting_command:
                await self._wake_only()
            else:
                await self.set_mode("idle")
            return
        self.awaiting_command = False
        learner.on_command()
        speaker, score = await asyncio.to_thread(self._speaker, clean)
        await self.send(type="transcript", text=command, ms=ms, lang=lang, followup=followup and not woke,
                        speaker=speaker, speaker_score=round(score, 3), voice_known=self._known(self.alone))
        await self.set_mode("idle")

    def _speaker(self, clean: np.ndarray) -> tuple[str | None, float]:
        emb = voiceprints.embed(clean)
        slug, score = voiceprints.identify(emb)
        if emb is not None and self.alone and slug in (None, self.alone):
            voiceprints.add(self.alone, emb, "ascolto")
        return slug, score

    @staticmethod
    def _known(slug: str | None) -> bool | None:
        if not slug or not voiceprints.ready:
            return None
        return voiceprints.count(slug) >= ENROLLED_AT

    async def _wake_only(self) -> None:
        self.awaiting_command = True
        await self.send(type="wake_only")
        await self.set_mode("listening")

    async def _enroll_sample(self, clean: np.ndarray) -> None:
        emb = await asyncio.to_thread(voiceprints.embed, clean)
        if emb is None:
            await self.send(type="enroll_progress", count=self.enroll["count"], ok=False)
            return
        self.enroll["count"] = await asyncio.to_thread(voiceprints.add, self.enroll["slug"], emb, "lettura")
        await self.send(type="enroll_progress", count=self.enroll["count"], ok=True)

    async def _transcribe_raw(self) -> None:
        pcm, self.raw = b"".join(self.raw or []), None
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        async with stt.lock:
            text, lang = (await asyncio.to_thread(stt.transcribe, enhance.clean(audio, self.profile), False, True)
                          if len(audio) > RATE * 0.3 else ("", stt.HOME_LANG))
        await self.send(type="transcription", text=text, lang=lang)

    async def control(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "listen":
            learner.on_manual_listen()
            await self.set_mode("listening")
        elif kind == "followup":
            seconds = max(3.0, min(40.0, float(msg.get("seconds", 8))))
            await self.set_mode("listening", seconds, conversation=bool(msg.get("conversation")))
        elif kind == "speaking":
            self.jarvis_speaking = bool(msg.get("on"))
            if self.jarvis_speaking:
                self.wake.reset()
        elif kind == "presence":
            alone = str(msg.get("alone") or "")
            self.alone = alone if SLUG_RE.match(alone) else None
        elif kind == "enroll_start":
            slug = str(msg.get("slug") or "")
            if voiceprints.ready and SLUG_RE.match(slug):
                self.enroll = {"slug": slug, "count": voiceprints.count(slug)}
                await self.send(type="enroll_progress", count=self.enroll["count"], ok=True)
            else:
                await self.send(type="enroll_unavailable")
        elif kind == "enroll_stop":
            done, self.enroll = self.enroll, None
            await self.send(type="enroll_done", count=(done or {}).get("count", 0))
        elif kind == "transcribe_start":
            self.raw = []
        elif kind == "transcribe_end":
            await self._transcribe_raw()
        elif kind == "stats":
            await self.send(type="stats", **learner.summary(), instant=self.wake.ready, voiceprint=voiceprints.ready)
        elif kind == "client":
            self.page = {"page": str(msg.get("page") or "")[:12], "visible": str(msg.get("visible") or "")[:10],
                         "href": str(msg.get("href") or self.page.get("href", ""))[:60], "since": self.page.get("since", time.time())}
            LINK["pages"] = [s.page for s in SESSIONS if s.page]
            await park_hidden()
        elif kind == "cancel":
            self.in_speech, self.speech = False, []
            await self.set_mode("idle")


async def park_hidden() -> None:
    visible = [s for s in SESSIONS if s.page.get("visible") == "visible"]
    if not visible:
        return
    for s in list(SESSIONS):
        if s.page.get("visible") == "hidden":
            log.info("Pagina nascosta %s scollegata: l'ascolto resta alla pagina visibile", s.page.get("page"))
            try:
                await s.ws.close(4001, "pagina nascosta")
            except Exception:
                pass


def note_error(where: str, exc: Exception) -> None:
    text = f"{where}: {type(exc).__name__}: {exc}"[:240]
    if LINK.get("error") != text:
        log.exception("Errore nell'ascolto (%s)", where)
    LINK["error"], LINK["error_at"] = text, time.time()


async def handler(ws) -> None:
    try:
        session = Session(ws)
    except Exception as exc:
        note_error("avvio della sessione", exc)
        save_link()
        raise
    await session.send(type="ready", model=stt.MODEL_SIZE, instant=session.wake.ready, voiceprint=voiceprints.ready)
    log.info("Display collegato")
    SESSIONS.add(session)
    LINK["clients"] += 1
    save_link()
    try:
        async for message in ws:
            try:
                if isinstance(message, bytes):
                    await session.feed(message)
                else:
                    await session.control(json.loads(message))
            except (ValueError, TypeError) as exc:
                if isinstance(message, bytes):
                    note_error("elaborazione dell'audio", exc)
                else:
                    log.debug("Messaggio di controllo non valido")
            except websockets.ConnectionClosed:
                raise
            except Exception as exc:
                note_error("elaborazione dell'audio" if isinstance(message, bytes) else "comando", exc)
                session.in_speech, session.speech = False, []
    except websockets.ConnectionClosed:
        log.debug("Connessione chiusa dal display")
    finally:
        SESSIONS.discard(session)
        LINK["pages"] = [s.page for s in SESSIONS if s.page]
        LINK["clients"] = max(0, LINK["clients"] - 1)
        save_link()
        log.info("Display scollegato")


async def main() -> None:
    async with websockets.serve(handler, "127.0.0.1", PORT, max_size=2 ** 20, ping_interval=20, ping_timeout=90):
        await link_writer()


if __name__ == "__main__":
    asyncio.run(main())
