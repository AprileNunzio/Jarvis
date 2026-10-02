import asyncio
import logging
import os
import time
from collections import deque

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.vad import VadOptions, get_speech_timestamps
from learner import learner

log = logging.getLogger("jarvis.ear")

RATE = 16000
MODEL_DIR = os.environ.get("JARVIS_EAR_MODELS", "/opt/jarvis-ear/models")
CPU = os.cpu_count() or 4
THREADS = max(2, min(8, CPU - 2))
HEAD_SECONDS = 1.8
MULTILANG = os.environ.get("JARVIS_EAR_MULTILANG", "1").lower() not in ("0", "off", "no")
HOME_LANG = "it"
LANG_MIN_PROB = 0.75
LANG_MIN_SECONDS = 0.9
PROMPTS = {"it": "Jarvis, assistente digitale.", "en": "Jarvis, digital assistant.", "es": "Jarvis, asistente digital.",
           "fr": "Jarvis, assistant numérique.", "de": "Jarvis, digitaler Assistent.", "pt": "Jarvis, assistente digital."}
HALLUCINATIONS = {"", "grazie.", "grazie", "sottotitoli a cura di qtss", "sottotitoli creati dalla comunità amara.org",
                  "thank you.", "thanks for watching!", "you"}


def _has_avx2() -> bool:
    try:
        return "avx2" in open("/proc/cpuinfo", encoding="utf-8").read()
    except OSError:
        return True


AVX2 = _has_avx2()
MODEL_SIZE = os.environ.get("JARVIS_STT_MODEL") or ("small" if CPU >= 6 and AVX2 else "base")
WAKE_MODEL = os.environ.get("JARVIS_WAKE_MODEL") or ("base" if CPU >= 6 and AVX2 else "tiny")
SLOW_RTF = 0.8
FALLBACK = "base" if MODEL_SIZE not in ("base", "tiny") else "tiny"

started = time.time()
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8", cpu_threads=THREADS, download_root=MODEL_DIR)
wake_model = model if WAKE_MODEL == MODEL_SIZE else WhisperModel(
    WAKE_MODEL, device="cpu", compute_type="int8", cpu_threads=max(2, THREADS // 2), download_root=MODEL_DIR)
lock = asyncio.Lock()
VAD = VadOptions(threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=300)
log.info("Modelli pronti in %.1fs: comandi=%s, attivazione=%s (%d thread)",
         time.time() - started, MODEL_SIZE, WAKE_MODEL, THREADS)

HOTWORDS = {"value": learner.hotwords(), "at": time.time()}
SPEED: deque = deque(maxlen=6)
ACTIVE = {"model": model, "name": MODEL_SIZE}


def refresh_hotwords() -> None:
    if time.time() - HOTWORDS["at"] > 300:
        HOTWORDS.update(value=learner.hotwords(), at=time.time())


def has_speech(audio: np.ndarray) -> bool:
    return bool(get_speech_timestamps(audio, VAD))


def spoken_language(audio: np.ndarray) -> str:
    if not MULTILANG or len(audio) < RATE * LANG_MIN_SECONDS:
        return HOME_LANG
    try:
        lang, prob, _ = ACTIVE["model"].detect_language(audio)
    except (RuntimeError, ValueError) as exc:
        log.debug("Riconoscimento della lingua non disponibile: %s", exc)
        return HOME_LANG
    return lang if lang == HOME_LANG or prob >= LANG_MIN_PROB else HOME_LANG


def _adapt(seconds: float, audio_seconds: float) -> None:
    if os.environ.get("JARVIS_STT_MODEL") or ACTIVE["name"] == FALLBACK or audio_seconds < 1.0:
        return
    SPEED.append(seconds / audio_seconds)
    if len(SPEED) == SPEED.maxlen and sum(SPEED) / len(SPEED) > SLOW_RTF:
        log.warning("Trascrizione lenta su questo hardware (%.1fx il tempo reale): passo al modello %s",
                    sum(SPEED) / len(SPEED), FALLBACK)
        ACTIVE.update(model=wake_model if WAKE_MODEL == FALLBACK else WhisperModel(
            FALLBACK, device="cpu", compute_type="int8", cpu_threads=THREADS, download_root=MODEL_DIR), name=FALLBACK)


def transcribe(audio: np.ndarray, fast: bool = False, detect: bool = False) -> tuple[str, str]:
    started = time.time()
    m = wake_model if fast else ACTIVE["model"]
    lang = spoken_language(audio) if detect else HOME_LANG
    segments, _ = m.transcribe(audio, language=lang, beam_size=1, vad_filter=False,
                               initial_prompt=PROMPTS.get(lang, "Jarvis."), condition_on_previous_text=False,
                               hotwords=HOTWORDS["value"] if lang == HOME_LANG else "Jarvis")
    text = " ".join(s.text.strip() for s in segments).strip()
    if not fast:
        _adapt(time.time() - started, len(audio) / RATE)
    return text, lang


def head(audio: np.ndarray) -> np.ndarray:
    return audio[:int(RATE * HEAD_SECONDS)]


def hallucination(text: str) -> bool:
    return text.lower().strip(" .") in HALLUCINATIONS
