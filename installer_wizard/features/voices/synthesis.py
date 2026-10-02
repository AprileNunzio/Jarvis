import asyncio
import hashlib
import io
import json
import re
import wave

import httpx

from config import env_get
from features.voices import languages
from features.voices.catalog import (CACHE_DIR, CACHE_MAX_FILES, HOME_LANG, KOKORO_MODEL, KOKORO_URL, PIPER, VOICE_DIR,
                                     auto_download, best_download, describe, engine, home_lang, is_online,
                                     online_enabled, piper_installed, voice_order, voices_for)
from features.voices.downloads import start_download
from state import store

_piper_lock = asyncio.Semaphore(1)

_REPLACEMENTS_ANY = [
    (re.compile(r"[*_#`>|]+"), " "),
    (re.compile(r"\bJ\.A\.R\.V\.I\.S\.?", re.I), "Jarvis"),
    (re.compile(r"\s*[—–]\s*"), ", "),
]
_REPLACEMENTS_IT = [
    (re.compile(r"https?://\S+"), "il collegamento"),
    (re.compile(r"(\d)\s*°\s*C?"), r"\1 gradi"),
    (re.compile(r"(\d)\s*%"), r"\1 per cento"),
    (re.compile(r"\bkm/h\b"), "chilometri orari"),
    (re.compile(r"\bkm\b"), "chilometri"),
    (re.compile(r"\bGB\b"), "gigabyte"),
    (re.compile(r"\bMB\b"), "megabyte"),
    (re.compile(r"\b(\d{1,2}):(\d{2})\b"), r"\1 e \2"),
]
_SPACES = re.compile(r"\s+")


def normalize(text: str, lang: str = HOME_LANG) -> str:
    rules = _REPLACEMENTS_ANY + (_REPLACEMENTS_IT if lang == "it" else [(re.compile(r"https?://\S+"), " ")])
    for pattern, repl in rules:
        text = pattern.sub(repl, text)
    return _SPACES.sub(" ", text).strip()


def available() -> bool:
    return KOKORO_MODEL.exists() or PIPER.exists()


def _clamped(key: str, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(env_get(key, str(default)) or default)))
    except ValueError:
        return default


def _speed() -> float:
    return _clamped("JARVIS_VOICE_SPEED", 1.0, 0.6, 1.6)


def _pitch() -> float:
    return _clamped("JARVIS_VOICE_PITCH", 0.0, -6.0, 6.0)


def _volume() -> float:
    return _clamped("JARVIS_VOICE_VOLUME", 1.0, 0.4, 2.0)


async def _retune(wav: bytes, pitch: float, volume: float) -> bytes:
    if abs(pitch) < 0.05 and abs(volume - 1.0) < 0.02:
        return wav
    with wave.open(io.BytesIO(wav), "rb") as r:
        sr = r.getframerate()
    ratio = 2 ** (pitch / 12)
    filters = []
    if abs(pitch) >= 0.05:
        tempo = 1 / ratio
        tempo = max(0.5, min(2.0, tempo))
        filters.append(f"asetrate={int(sr * ratio)},aresample={sr},atempo={tempo:.4f}")
    if abs(volume - 1.0) >= 0.02:
        filters.append(f"volume={volume:.3f}")
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-af", ",".join(filters), "-f", "wav", "pipe:1",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await asyncio.wait_for(proc.communicate(wav), 30)
    except (OSError, asyncio.TimeoutError):
        return wav
    return out if proc.returncode == 0 and out else wav


def _sample_rate(voice: str) -> int:
    try:
        meta = json.loads((VOICE_DIR / "voices" / f"{voice}.onnx.json").read_text(encoding="utf-8"))
        return int(meta["audio"]["sample_rate"])
    except (OSError, ValueError, KeyError):
        return 22050


async def _kokoro(text: str, voice: str, speed: float) -> bytes:
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(f"{KOKORO_URL}/tts", json={"text": text, "voice": voice, "speed": speed})
    if r.status_code != 200:
        raise RuntimeError(f"Kokoro: {r.text[:200]}")
    return r.content


async def _piper(text: str, voice: str, speed: float) -> bytes:
    model = VOICE_DIR / "voices" / f"{voice}.onnx"
    if not PIPER.exists() or not model.exists():
        raise RuntimeError(f"Voce Piper non installata: {voice}")
    async with _piper_lock:
        proc = await asyncio.create_subprocess_exec(
            str(PIPER), "--model", str(model), "--length_scale", f"{1 / speed:.3f}",
            "--sentence_silence", "0.15", "--output_raw",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        raw, err = await asyncio.wait_for(proc.communicate(text.encode("utf-8")), timeout=60)
    if proc.returncode != 0 or not raw:
        raise RuntimeError(f"Piper non riuscito: {err.decode(errors='ignore')[-200:]}")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_sample_rate(voice))
        wav.writeframes(raw)
    return buffer.getvalue()


async def _online(text: str, voice: str, speed: float) -> bytes:
    if not online_enabled():
        raise RuntimeError("voci online disattivate o edge-tts non installato")
    import edge_tts
    rate = f"{round((speed - 1) * 100):+d}%"
    mp3 = bytearray()

    async def collect():
        async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
            if chunk.get("type") == "audio":
                mp3.extend(chunk["data"])
    try:
        await asyncio.wait_for(collect(), 30)
    except Exception as exc:
        raise RuntimeError(f"voce online non disponibile: {exc}") from exc
    if not mp3:
        raise RuntimeError("voce online: nessun audio ricevuto")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "24000", "-f", "wav", "pipe:1",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
    wav, _ = await asyncio.wait_for(proc.communicate(bytes(mp3)), 30)
    if proc.returncode != 0 or not wav:
        raise RuntimeError("conversione dell'audio online non riuscita")
    return wav


def _prune_cache() -> None:
    files = sorted(CACHE_DIR.glob("*.wav"), key=lambda p: p.stat().st_atime)
    for old in files[:-CACHE_MAX_FILES]:
        old.unlink(missing_ok=True)


async def speak_with(text: str, voice: str, speed: float) -> bytes:
    kind = engine(voice)
    return await (_piper(text, voice, speed) if kind == "piper" else
                  _online(text, voice, speed) if kind == "online" else _kokoro(text, voice, speed))


async def synthesize(text: str, voice: str | None = None, speed: float | None = None,
                     lang: str | None = None, pitch: float | None = None, volume: float | None = None) -> bytes:
    home = home_lang()
    lang = languages.base(lang or "") or languages.detect(text, home)
    text = normalize(text, lang)[:1200]
    if not text:
        raise ValueError("Testo vuoto")
    speed = speed or _speed()
    pitch = _pitch() if pitch is None else max(-6.0, min(6.0, pitch))
    volume = _volume() if volume is None else max(0.4, min(2.0, volume))
    if voice and describe(voice)["lang"] != lang and "Multilingual" not in voice:
        voice = None
    chain = [voice] if voice else []
    if lang != home:
        chain += await voices_for(lang)
        if not [v for v in chain if not is_online(v)] and auto_download():
            target = best_download(lang)
            if target and await start_download(target):
                store.event("INFO", f"Nessuna voce in {languages.label(lang).lower()}: scarico {target}", "voice")
    chain = list(dict.fromkeys(chain + voice_order()))

    errors, kokoro_down, online_down = [], False, False
    for i, v in enumerate(chain):
        cached = CACHE_DIR / f"{hashlib.sha1(f'{v}|{speed}|{pitch}|{volume}|{text}'.encode()).hexdigest()}.wav"
        if cached.exists():
            cached.touch()
            return cached.read_bytes()
        kind = engine(v)
        if ((kind == "piper" and not piper_installed(v)) or (kind == "kokoro" and kokoro_down)
                or (kind == "online" and online_down)):
            errors.append(f"{v}: non disponibile")
            continue
        try:
            data = await _retune(await speak_with(text, v, speed), pitch, volume)
        except (httpx.HTTPError, RuntimeError, OSError, asyncio.TimeoutError) as exc:
            kokoro_down = kokoro_down or (kind == "kokoro" and isinstance(exc, httpx.TransportError))
            online_down = online_down or kind == "online"
            errors.append(f"{v}: {exc}")
            continue
        if i and errors:
            store.event("WARN", f"Voce {chain[0]} non disponibile, uso {v} ({errors[-1][:120]})", "voice")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        _prune_cache()
        return data
    raise RuntimeError("; ".join(errors)[:300] or "nessuna voce disponibile")
