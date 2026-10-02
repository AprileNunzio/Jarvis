import re
import time

import httpx
from config import DEMO, ollama_remote, ollama_url, read_env

from features.cloud.catalog import BY_ID, is_cloud, is_server, parse_ref
from features.cloud.vault import vault

CATALOG = [
    {"name": "qwen2.5:0.5b", "label": "Qwen 2.5 · 0,5 B", "size_gb": 0.4, "roles": ["chat"],
     "notes": "Minuscolo e istantaneo; italiano essenziale. Per dispositivi con poca memoria."},
    {"name": "qwen2.5:1.5b", "label": "Qwen 2.5 · 1,5 B", "size_gb": 1.0, "roles": ["chat"],
     "notes": "Rapidissimo, buon italiano: ideale per la conversazione su CPU."},
    {"name": "llama3.2:1b", "label": "Llama 3.2 · 1 B", "size_gb": 1.3, "roles": ["chat"],
     "notes": "Molto veloce, italiano discreto."},
    {"name": "gemma2:2b", "label": "Gemma 2 · 2 B", "size_gb": 1.6, "roles": ["chat"],
     "notes": "Veloce e cordiale, italiano buono."},
    {"name": "qwen2.5:3b", "label": "Qwen 2.5 · 3 B", "size_gb": 1.9, "roles": ["chat", "deep"],
     "notes": "Equilibrio tra velocità e qualità: il cervello predefinito su CPU con 8 GB."},
    {"name": "llama3.2:3b", "label": "Llama 3.2 · 3 B", "size_gb": 2.0, "roles": ["chat", "deep"],
     "notes": "Alternativa a Qwen 3B, buone istruzioni."},
    {"name": "phi3.5", "label": "Phi 3.5 mini · 3,8 B", "size_gb": 2.2, "roles": ["deep"],
     "notes": "Ragionamento e matematica sopra la media per la taglia."},
    {"name": "gemma3:4b", "label": "Gemma 3 · 4 B", "size_gb": 3.3, "roles": ["deep"],
     "notes": "Ottimo italiano e comprensione, più lento su CPU."},
    {"name": "qwen2.5:7b", "label": "Qwen 2.5 · 7 B", "size_gb": 4.7, "roles": ["deep"],
     "notes": "Risposte articolate e precise: il cervello potente consigliato con 16 GB o GPU da 6 GB."},
    {"name": "qwen2.5-coder:7b", "label": "Qwen 2.5 Coder · 7 B", "size_gb": 4.7, "roles": ["deep"],
     "notes": "Specializzato nel codice e nell'automazione."},
    {"name": "deepseek-r1:7b", "label": "DeepSeek R1 · 7 B", "size_gb": 4.7, "roles": ["deep"],
     "notes": "Ragiona passo passo prima di rispondere: lento ma accurato su problemi logici."},
    {"name": "llama3.1:8b", "label": "Llama 3.1 · 8 B", "size_gb": 4.9, "roles": ["deep"],
     "notes": "Generalista solido."},
    {"name": "gemma2:9b", "label": "Gemma 2 · 9 B", "size_gb": 5.4, "roles": ["deep"],
     "notes": "Italiano molto naturale, serve una GPU per essere scorrevole."},
    {"name": "mistral-nemo", "label": "Mistral Nemo · 12 B", "size_gb": 7.1, "roles": ["deep"],
     "notes": "Europeo, ottimo nelle lingue romanze."},
    {"name": "gemma3:12b", "label": "Gemma 3 · 12 B", "size_gb": 8.1, "roles": ["deep"],
     "notes": "Qualità alta, richiede GPU da 10-12 GB."},
    {"name": "qwen2.5:14b", "label": "Qwen 2.5 · 14 B", "size_gb": 9.0, "roles": ["deep"],
     "notes": "Il più capace per GPU da 12-16 GB."},
    {"name": "qwen2.5:32b", "label": "Qwen 2.5 · 32 B", "size_gb": 20.0, "roles": ["deep"],
     "notes": "Livello professionale: GPU da 24 GB."},
]
_BY_NAME = {m["name"]: m for m in CATALOG}

MAX_TOKENS = {"chat": 320, "deep": 1200}

_DEEP = re.compile(
    r"\b(spiega(mi)?|spiegazione|analizza|analisi|confronta|differenz[ae]|vantaggi|svantaggi|perch[ée]"
    r"|come funziona|in dettaglio|dettagliat\w*|approfondi\w*|passo (a|per) passo|ragiona|dimostra|valuta"
    r"|riassumi|riassunto|traduci|scrivi (un|una|il|la|lo|dei|delle)|componi|progetta|pianifica|organizza"
    r"|strategia|calcola|risolvi|equazion\w*|codice|script|programma|funzione|python|javascript|bash|sql"
    r"|algoritmo|errore|debug|configura|installa|consigli(ami)?|elenca|lista di|pro e contro|storia d\w*)\b",
    re.I)
_CHITCHAT = re.compile(r"^\s*(ciao|buongiorno|buonasera|buonanotte|grazie|ok|okay|va bene|perfetto|come stai"
                       r"|chi sei|sei li|ci sei|salve|hey|ehi)\b", re.I)


def _split(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for x in items:
        key = norm(x)
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


def norm(model: str) -> str:
    return model if ":" in model else f"{model}:latest"


class Brains:
    def __init__(self) -> None:
        self._installed: tuple[float, list[str]] = (0.0, [])
        self.stats: dict[str, dict] = {}
        self.last: dict = {}

    @staticmethod
    def config() -> dict:
        env = read_env()
        main = env.get("JARVIS_LLM_MODEL") or "qwen2.5:3b"
        fast = env.get("JARVIS_LLM_FAST_MODEL") or main
        chat_custom, deep_custom = _split(env.get("JARVIS_LLM_CHAT_ORDER", "")), _split(env.get("JARVIS_LLM_DEEP_ORDER", ""))
        return {
            "routing": env.get("JARVIS_LLM_ROUTING", "auto") if env.get("JARVIS_LLM_ROUTING") in ("auto", "1", "0") else "auto",
            "main": main, "fast": fast,
            "chat": _dedupe(chat_custom or [fast, main]), "deep": _dedupe(deep_custom or [main, fast]),
            "chat_custom": bool(chat_custom), "deep_custom": bool(deep_custom),
        }

    async def installed(self) -> list[str]:
        ts, names = self._installed
        if time.time() - ts < 30:
            return names
        if DEMO:
            names = ["qwen2.5:3b", "qwen2.5:1.5b", "nomic-embed-text:latest"]
        else:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    names = [m["name"] for m in (await client.get(f"{ollama_url()}/api/tags")).json().get("models", [])]
            except (httpx.HTTPError, ValueError, KeyError):
                return names
        self._installed = (time.time(), names)
        return names

    @staticmethod
    def usable(model: str, installed: set) -> bool:
        if is_cloud(model):
            try:
                provider, _ = parse_ref(model)
            except ValueError:
                return False
            return vault.configured(provider)
        return not installed or norm(model) in installed

    @staticmethod
    def describe(model: str) -> dict:
        if is_cloud(model):
            try:
                provider, name = parse_ref(model)
            except ValueError:
                return {"ref": model, "model": model, "origin": "cloud", "provider": "rimosso", "label": model}
            return {"ref": model, "model": name, "origin": "server" if is_server(provider) else "cloud",
                    "provider": BY_ID[provider].name,
                    "label": f"{name} · {BY_ID[provider].name}"}
        where = ollama_url().split("//", 1)[-1] if ollama_remote() else "Questo server"
        return {"ref": model, "model": model, "origin": "local", "provider": where,
                "label": f"{model} · {where if ollama_remote() else 'locale'}"}

    def active_now(self, kind: str) -> dict | None:
        cfg = self.config()
        installed = {norm(n) for n in self._installed[1]}
        for model in _dedupe(cfg[kind] + cfg["deep" if kind == "chat" else "chat"]):
            if self.usable(model, installed):
                return self.describe(model)
        return None

    def invalidate(self) -> None:
        self._installed = (0.0, [])

    @staticmethod
    def classify(text: str) -> tuple[str, str]:
        t = text.strip()
        if _CHITCHAT.match(t) and len(t) < 60:
            return "chat", "saluto o conversazione breve"
        if "```" in t or t.count("\n") >= 3:
            return "deep", "testo strutturato o codice"
        if len(t) > 220:
            return "deep", "richiesta lunga"
        if t.count("?") >= 2:
            return "deep", "più domande insieme"
        m = _DEEP.search(t)
        if m:
            return "deep", f"richiede ragionamento («{m.group(0).lower()}»)"
        if re.search(r"\d+\s*[-+*/^x×÷]\s*\d+", t):
            return "deep", "calcolo"
        return "chat", "conversazione"

    async def route(self, text: str) -> dict:
        cfg, installed = self.config(), {norm(n) for n in await self.installed()}
        routing = cfg["routing"]
        split = routing == "1" or (routing == "auto" and norm(cfg["chat"][0]) != norm(cfg["deep"][0]))
        kind, reason = self.classify(text) if split else ("deep", "cervello unico")
        primary = cfg[kind]
        other = cfg["deep" if kind == "chat" else "chat"]
        chain = [m for m in _dedupe(primary + other) if self.usable(m, installed)]
        if not chain:
            chain = primary[:1]
        return {"kind": kind, "reason": reason, "models": chain, "max_tokens": MAX_TOKENS[kind]}

    def record(self, model: str, ms: float, ok: bool, kind: str) -> None:
        s = self.stats.setdefault(model, {"ok": 0, "fail": 0, "avg_ms": ms})
        s["ok" if ok else "fail"] += 1
        if ok:
            s["avg_ms"] = round(s["avg_ms"] * 0.7 + ms * 0.3)
        self.last = {"model": model, "kind": kind, "ms": round(ms), "at": time.time()}

    @staticmethod
    def fit(size_gb: float, hw: dict) -> dict:
        vram, ram = hw.get("vram_gb", 0), hw.get("ram_gb", 8)
        on_gpu = vram and size_gb * 1.2 + 0.5 <= vram
        free_ram = ram - 3.0
        if on_gpu:
            tps, where = 180 / max(size_gb, 0.3), "GPU"
        else:
            tps, where = 14 / max(size_gb, 0.3), "CPU"
        if not on_gpu and size_gb * 1.25 + 0.4 > free_ram:
            return {"level": "no", "label": "troppo grande per questa macchina", "tps": round(tps, 1), "where": where}
        speed = "istantaneo" if tps >= 25 else "veloce" if tps >= 11 else "medio" if tps >= 5 else "lento"
        level = "ok" if tps >= 5 else "slow"
        return {"level": level, "label": f"{speed} (~{tps:.0f} parole/s su {where})", "tps": round(tps, 1), "where": where}

    async def overview(self, hw: dict) -> dict:
        cfg = self.config()
        names = await self.installed()
        installed = {norm(n) for n in names}
        catalog = []
        for m in CATALOG:
            catalog.append({**m, "installed": norm(m["name"]) in installed, "fit": self.fit(m["size_gb"], hw)})
        extra = [n for n in names if norm(n) not in {norm(m["name"]) for m in CATALOG} and "embed" not in n]
        for n in extra:
            catalog.append({"name": n, "label": n, "size_gb": None, "roles": ["chat", "deep"], "installed": True,
                            "notes": "Installato manualmente", "fit": {"level": "ok", "label": "installato"}})

        def entries(lst):
            return [{"name": n, "installed": norm(n) in installed, "available": self.usable(n, installed),
                     "stats": self.stats.get(norm(n)) or self.stats.get(n), **self.describe(n)} for n in lst]
        auto_fast, auto_main = self.auto_pick(hw)
        active = {"chat": self.active_now("chat"), "deep": self.active_now("deep")}
        last = {**self.last, **self.describe(self.last["model"])} if self.last.get("model") else {}
        return {"routing": cfg["routing"], "chat": entries(cfg["chat"]), "deep": entries(cfg["deep"]),
                "active": active, "last_used": last,
                "chat_custom": cfg["chat_custom"], "deep_custom": cfg["deep_custom"],
                "main": cfg["main"], "fast": cfg["fast"], "suggested": {"chat": auto_fast, "deep": auto_main},
                "catalog": catalog, "last": self.last, "hardware": hw}

    @staticmethod
    def auto_pick(hw: dict) -> tuple[str, str]:
        vram, ram = hw.get("vram_gb", 0), hw.get("ram_gb", 8)
        if vram >= 20:
            deep = "qwen2.5:14b"
        elif vram >= 8 or ram >= 24:
            deep = "qwen2.5:7b"
        elif ram >= 7:
            deep = "qwen2.5:3b"
        else:
            deep = "qwen2.5:1.5b"
        if vram >= 6:
            fast = "qwen2.5:3b"
        elif ram >= 6:
            fast = "qwen2.5:1.5b"
        else:
            fast = "qwen2.5:0.5b"
        return fast, deep


brains = Brains()
