import asyncio
import importlib.util
import json
import re
import time
from pathlib import Path

import httpx

from config import STATE_DIR, env_get
from features.voices import languages
from state import store

VOICE_DIR = Path("/opt/jarvis-voice")
PIPER = VOICE_DIR / "piper" / "piper"
KOKORO_MODEL = VOICE_DIR / "kokoro" / "kokoro-v1.0.onnx"
KOKORO_URL = "http://127.0.0.1:8092"
CACHE_DIR = STATE_DIR / "tts-cache"
CATALOG_DIR = STATE_DIR / "voices"
CACHE_MAX_FILES = 600
CATALOG_MAX_AGE = 7 * 86400
DEFAULT_VOICE = "im_nicola"
DEFAULT_FALLBACK = "it_IT-riccardo-x_low"
HOME_LANG = languages.DEFAULT

VOICES = {
    "im_nicola": "Nicola — maschile, naturale (Kokoro)",
    "if_sara": "Sara — femminile, naturale (Kokoro)",
    "it-IT-DiegoNeural": "Diego — maschile, naturalissima (online)",
    "it-IT-GiuseppeMultilingualNeural": "Giuseppe — maschile, multilingue (online)",
    "it-IT-IsabellaNeural": "Isabella — femminile, naturalissima (online)",
    "it-IT-ElsaNeural": "Elsa — femminile, naturalissima (online)",
    "it_IT-serena-high": "Serena — femminile, alta qualità (Piper)",
    "it_IT-riccardo-x_low": "Riccardo — maschile, veloce (Piper)",
    "it_IT-paola-medium": "Paola — femminile, veloce (Piper)",
}

KOKORO_LANGS = {"a": "en-US", "b": "en-GB", "e": "es-ES", "f": "fr-FR", "h": "hi-IN", "i": "it-IT", "j": "ja-JP",
                "p": "pt-BR", "z": "zh-CN"}
KOKORO_KNOWN = (
    "af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river af_sarah af_sky am_adam "
    "am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck am_santa bf_alice bf_emma bf_isabella bf_lily "
    "bm_daniel bm_fable bm_george bm_lewis ef_dora em_alex em_santa ff_siwis hf_alpha hf_beta hm_omega hm_psi "
    "if_sara im_nicola jf_alpha jf_gongitsune jf_nezumi jf_tebukuro jm_kumo pf_dora pm_alex pm_santa zf_xiaobei "
    "zf_xiaoni zf_xiaoxiao zf_xiaoyi zm_yunjian zm_yunxi zm_yunxia zm_yunyang").split()
KOKORO_BEST = {"it": ["im_nicola", "if_sara"], "en": ["am_michael", "am_fenrir", "bm_george", "af_heart"],
               "es": ["em_alex", "ef_dora"], "fr": ["ff_siwis"], "pt": ["pm_alex", "pf_dora"],
               "hi": ["hm_omega", "hf_alpha"], "ja": ["jm_kumo", "jf_alpha"], "zh": ["zm_yunjian", "zf_xiaoxiao"]}

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
PIPER_CATALOG_URL = f"{PIPER_BASE}/voices.json"
PIPER_CATALOG_FILE = CATALOG_DIR / "piper.json"
PIPER_MALE = set(
    "alan amir arjun artur bryce cadu carlfm danny davefx denis dimitar dmitri edresson faber gilles gwryw_gogleddol "
    "harri hfc_male imre jeff jirka joe john kareem karlsson kusal mihai mykyta norman northern_english_male pavoque "
    "pim pratham reza_ibrahim riccardo rohan ronnie ruslan ryan steinn talesyntese thorsten thorsten_emotional tom "
    "upc_pau venkatesh oleksa antton darkman".split())
PIPER_FEMALE = set(
    "aegis_female alba alma amy anna berta cori daniela eva_k gosia hfc_female irina jenny_dioco kasandra kathleen "
    "kerstin kristin kss lada lessac lili lisa ljspeech maider marylux maya meera natia nathalie padmavathi paola "
    "priyamvada ramona rapunzelina raya salka serena siwis southern_english_female tetiana ugla upc_ona xiao_ya "
    "huayan".split())
PIPER_BUILTIN = {
    "it_IT-riccardo-x_low": 28, "it_IT-paola-medium": 63, "it_IT-serena-medium": 63, "it_IT-serena-high": 114,
    "en_US-ryan-medium": 63, "en_US-amy-medium": 63, "en_GB-alan-medium": 63, "es_ES-davefx-medium": 63,
    "fr_FR-siwis-medium": 63, "de_DE-thorsten-medium": 63, "pt_BR-faber-medium": 63, "nl_NL-mls-medium": 63,
    "ru_RU-dmitri-medium": 63, "pl_PL-darkman-medium": 63,
}
_PIPER_RE = re.compile(r"^[a-z]{2,3}_[A-Z]{2}-[a-z0-9_]+-(x_low|low|medium|high)$")
_QUALITY = {"x_low": "rapida", "low": "rapida", "medium": "media", "high": "alta"}
_QUALITY_RANK = {"medium": 0, "high": 1, "low": 2, "x_low": 3}

ONLINE_CATALOG_FILE = CATALOG_DIR / "online.json"
_ONLINE_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8}){1,3}-[A-Za-z]+Neural$")

SAMPLES = {
    "it": "Buongiorno, sono Jarvis. Questa è la mia voce.", "en": "Hello, I'm Jarvis. This is my voice.",
    "es": "Hola, soy Jarvis. Esta es mi voz.", "fr": "Bonjour, je suis Jarvis. Voici ma voix.",
    "de": "Hallo, ich bin Jarvis. Das ist meine Stimme.", "pt": "Olá, eu sou o Jarvis. Esta é a minha voz.",
    "nl": "Hallo, ik ben Jarvis. Dit is mijn stem.", "ru": "Здравствуйте, я Джарвис. Это мой голос.",
    "pl": "Dzień dobry, jestem Jarvis. To jest mój głos.", "ja": "こんにちは、ジャーヴィスです。これが私の声です。",
    "zh": "你好，我是贾维斯。这是我的声音。", "hi": "नमस्ते, मैं जार्विस हूँ। यह मेरी आवाज़ है।",
}


_refreshing: set[str] = set()


def is_piper(voice: str) -> bool:
    return bool(_PIPER_RE.match(voice))


def is_online(voice: str) -> bool:
    return bool(_ONLINE_RE.match(voice))


def engine(voice: str) -> str:
    return "piper" if is_piper(voice) else "online" if is_online(voice) else "kokoro"


def online_enabled() -> bool:
    mode = (env_get("JARVIS_VOICE_ONLINE", "auto") or "auto").lower()
    if mode in ("0", "off", "no"):
        return False
    return importlib.util.find_spec("edge_tts") is not None


def auto_download() -> bool:
    return (env_get("JARVIS_VOICE_AUTO_DOWNLOAD", "1") or "1") not in ("0", "off", "no")


def fallback_voice() -> str:
    return env_get("JARVIS_VOICE_FALLBACK", DEFAULT_FALLBACK) or DEFAULT_FALLBACK


def custom_order() -> list[str]:
    return [v.strip() for v in env_get("JARVIS_VOICE_ORDER", "").split(",") if v.strip()]


def voice_order() -> list[str]:
    order = custom_order() or [env_get("JARVIS_VOICE", DEFAULT_VOICE) or DEFAULT_VOICE]
    return list(dict.fromkeys(order + [fallback_voice()]))


def voice_name() -> str:
    return voice_order()[0]


def lang_prefs() -> dict[str, str]:
    prefs = {}
    for item in env_get("JARVIS_VOICE_LANG", "").split(","):
        lang, _, v = item.partition(":")
        if lang.strip() and v.strip():
            prefs[lang.strip()] = v.strip()
    return prefs


def lang_prefs_env(prefs: dict[str, str]) -> str:
    return ",".join(f"{k}:{v}" for k, v in sorted(prefs.items()) if v)


def piper_installed(voice: str) -> bool:
    return (VOICE_DIR / "voices" / f"{voice}.onnx").exists() and (VOICE_DIR / "voices" / f"{voice}.onnx.json").exists()


def _read_cache(path: Path) -> tuple[object, float]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), path.stat().st_mtime
    except (OSError, ValueError):
        return None, 0.0


def _write_cache(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


async def _refresh_piper() -> None:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(PIPER_CATALOG_URL)
        r.raise_for_status()
    raw = r.json()
    catalog = {}
    for key, v in raw.items():
        files = {p: f.get("size_bytes", 0) for p, f in (v.get("files") or {}).items()}
        model = next((p for p in files if p.endswith(".onnx")), None)
        if not model or not _PIPER_RE.match(key):
            continue
        catalog[key] = {"name": v.get("name", ""), "locale": v["language"]["code"].replace("_", "-"),
                        "quality": v.get("quality", ""), "speakers": v.get("num_speakers", 1),
                        "path": model[:-5], "size_mb": round(files[model] / 1e6)}
    if len(catalog) > 20:
        _write_cache(PIPER_CATALOG_FILE, catalog)


async def _refresh_online() -> None:
    import edge_tts
    raw = await asyncio.wait_for(edge_tts.list_voices(), 30)
    catalog = {v["ShortName"]: {"name": v["ShortName"].split("-")[-1].removesuffix("Neural")
                                .replace("Multilingual", " multilingue"),
                                "locale": v["Locale"], "gender": (v.get("Gender") or "")[:1].lower()}
               for v in raw if _ONLINE_RE.match(v.get("ShortName", ""))}
    if len(catalog) > 50:
        _write_cache(ONLINE_CATALOG_FILE, catalog)


def _refresh_later(kind: str) -> None:
    if kind in _refreshing:
        return
    _refreshing.add(kind)

    async def run():
        try:
            await (_refresh_piper() if kind == "piper" else _refresh_online())
        except Exception as exc:
            store.event("WARN", f"Catalogo delle voci {kind} non aggiornato: {exc}", "voice")
        finally:
            _refreshing.discard(kind)
    try:
        asyncio.get_running_loop().create_task(run())
    except RuntimeError:
        _refreshing.discard(kind)


def piper_catalog() -> dict:
    data, mtime = _read_cache(PIPER_CATALOG_FILE)
    if time.time() - mtime > CATALOG_MAX_AGE:
        _refresh_later("piper")
    if data:
        return data
    return {k: {"name": k.split("-")[1], "locale": k.split("-")[0].replace("_", "-"), "quality": k.rsplit("-", 1)[1],
                "speakers": 1, "path": piper_voice_path(k), "size_mb": mb} for k, mb in PIPER_BUILTIN.items()}


def online_catalog() -> dict:
    if not online_enabled():
        return {}
    data, mtime = _read_cache(ONLINE_CATALOG_FILE)
    if time.time() - mtime > CATALOG_MAX_AGE:
        _refresh_later("online")
    return data or {v: {"name": v.split("-")[-1].removesuffix("Neural"), "locale": "-".join(v.split("-")[:2]),
                        "gender": "m" if v in ("it-IT-DiegoNeural", "it-IT-GiuseppeMultilingualNeural") else "f"}
                    for v in VOICES if is_online(v)}


def piper_voice_path(voice: str) -> str:
    locale, rest = voice.split("-", 1)
    name, quality = (rest[:-6], "x_low") if rest.endswith("-x_low") else rest.rsplit("-", 1)
    return f"{locale.split('_')[0]}/{locale}/{name}/{quality}/{voice}"


def describe(voice: str, piper: dict | None = None, online: dict | None = None) -> dict:
    kind = engine(voice)
    if kind == "piper":
        info = (piper if piper is not None else piper_catalog()).get(voice) or {}
        name = info.get("name") or voice.split("-")[1]
        quality = info.get("quality") or voice.rsplit("-", 1)[-1]
        locale = info.get("locale") or voice.split("-")[0].replace("_", "-")
        gender = "m" if name in PIPER_MALE else "f" if name in PIPER_FEMALE else ""
        return {"id": voice, "name": name.replace("_", " ").capitalize(), "gender": gender,
                "lang": languages.base(locale), "locale": locale, "engine": "piper", "size_mb": info.get("size_mb"),
                "quality": _QUALITY.get(quality, quality), "rank": _QUALITY_RANK.get(quality, 5)}
    if kind == "online":
        info = (online if online is not None else online_catalog()).get(voice) or {}
        locale = info.get("locale") or "-".join(voice.split("-")[:2])
        return {"id": voice, "name": info.get("name") or voice.split("-")[-1].removesuffix("Neural"),
                "gender": info.get("gender", ""), "lang": languages.base(locale), "locale": locale,
                "engine": "online", "size_mb": None, "quality": "naturalissima", "rank": 0,
                "multi": "Multilingual" in voice}
    locale = KOKORO_LANGS.get(voice[:1], "en-US")
    return {"id": voice, "name": voice.split("_", 1)[-1].capitalize(), "gender": voice[1:2],
            "lang": languages.base(locale), "locale": locale, "engine": "kokoro", "size_mb": None,
            "quality": "naturale", "rank": 0}


async def kokoro_voices() -> list[str] | None:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            return (await client.get(f"{KOKORO_URL}/health")).json().get("voices", [])
    except (httpx.HTTPError, ValueError):
        return None


MAIN_LOCALE = {"en": "en-US", "pt": "pt-BR", "zh": "zh-CN", "ar": "ar-SA", "sv": "sv-SE", "da": "da-DK", "ja": "ja-JP",
               "ko": "ko-KR", "el": "el-GR", "cs": "cs-CZ", "uk": "uk-UA", "he": "he-IL", "hi": "hi-IN", "fa": "fa-IR",
               "vi": "vi-VN", "sl": "sl-SI", "et": "et-EE", "ca": "ca-ES", "ur": "ur-PK", "sq": "sq-AL", "ka": "ka-GE",
               "hy": "hy-AM", "kk": "kk-KZ", "ms": "ms-MY", "sw": "sw-KE", "nb": "nb-NO", "no": "nb-NO", "cy": "cy-GB",
               "ga": "ga-IE", "fil": "fil-PH", "bn": "bn-IN", "ta": "ta-IN", "te": "te-IN", "ml": "ml-IN", "mr": "mr-IN",
               "ne": "ne-NP", "sr": "sr-RS", "af": "af-ZA", "eu": "eu-ES", "gl": "gl-ES", "lb": "lb-LU"}


def _best(candidates: list[dict]) -> list[dict]:
    def main(d: dict) -> bool:
        return d.get("locale", "").lower() == MAIN_LOCALE.get(d["lang"], f"{d['lang']}-{d['lang']}").lower()
    return sorted(candidates, key=lambda d: (d["gender"] != "m", not main(d), d.get("rank", 5), d["id"]))


def home_lang() -> str:
    d = describe(voice_name())
    return HOME_LANG if d.get("multi") else d["lang"]


async def voices_for(lang: str, kokoro_list: list[str] | None = None) -> list[str]:
    lang = languages.base(lang)
    kv = kokoro_list if kokoro_list is not None else await kokoro_voices()
    piper, online = piper_catalog(), online_catalog()
    ready: list[str] = []
    pref = lang_prefs().get(lang)
    if pref:
        ready.append(pref)
    ready += [v for v in voice_order() if describe(v, piper, online)["lang"] == lang]
    if kv:
        ready += [v for v in KOKORO_BEST.get(lang, []) if v in kv]
        ready += [d["id"] for d in _best([describe(v) for v in kv if describe(v)["lang"] == lang])]
    ready += [d["id"] for d in _best([describe(v, piper, online) for v in piper if describe(v, piper, online)["lang"] == lang])
              if piper_installed(d["id"])]
    if online:
        ready += [d["id"] for d in _best([describe(v, piper, online) for v, i in online.items()
                                          if languages.base(i["locale"]) == lang])][:3]
        ready += [d["id"] for d in _best([describe(v, piper, online) for v in online if "Multilingual" in v])][:2]
    return list(dict.fromkeys(ready))


def best_download(lang: str) -> str | None:
    piper = piper_catalog()
    options = _best([describe(v, piper, {}) for v, i in piper.items()
                     if languages.base(i["locale"]) == languages.base(lang) and i.get("speakers", 1) == 1])
    return options[0]["id"] if options else None

