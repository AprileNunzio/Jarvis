import ast
import asyncio
import glob
import json
import logging
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

from config import DEMO, SKILLS_DIR, STATE_DIR, env_get
from state import store

log = logging.getLogger("jarvis.skills")

SYSTEM_DIR = SKILLS_DIR
USER_DIR = STATE_DIR / "skills"
STATS_FILE = STATE_DIR / "skills_stats.json"
WORKER = Path(__file__).resolve().parent / "worker.py"
RUN_TIMEOUT = 4.0
CATEGORIES = {"matematica": "Matematica", "unita": "Unità di misura", "date": "Date e tempo",
              "finanza": "Finanza", "testo": "Testo", "casa": "Casa", "altro": "Altro"}

ALLOWED_IMPORTS = {"math", "cmath", "statistics", "fractions", "decimal", "datetime", "calendar", "re", "json",
                   "itertools", "functools", "collections", "random", "string", "unicodedata", "operator",
                   "numbers", "bisect", "heapq", "textwrap", "time"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "input",
                   "breakpoint", "getattr", "setattr", "delattr", "memoryview", "exit", "quit", "help"}

NEED = re.compile(
    r"\b(calcola\w*|quanto fa|quanto (è|e'|vale|fanno)|converti\w*|conversione|percentual\w*|radice|fattoriale"
    r"|potenza|media (di|tra)|mediana|somma (di|tra)|moltiplica|dividi|quanti (giorni|minuti|secondi|anni|mesi|ore)"
    r"|iva|sconto|interess[ei]|rata|mutuo|bmi|indice di massa|in (km|chilometri|miglia|metri|litri|kg|grammi|fahrenheit|celsius)"
    r"|codice fiscale|numero primo|primi (fino|tra)|mcm|mcd|equazione)\b", re.I)


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")[:40] or "algoritmo"


def check_code(code: str) -> None:
    tree = ast.parse(code)
    has_run = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise ValueError(f"modulo non ammesso: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS or node.level:
                raise ValueError(f"modulo non ammesso: {node.module}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError(f"funzione non ammessa: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"attributo non ammesso: {node.attr}")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ValueError("variabili globali non ammesse")
        elif isinstance(node, ast.FunctionDef) and node.name == "run" and node.col_offset == 0:
            has_run = True
    if not has_run:
        raise ValueError("manca la funzione run(text)")


class Worker:

    def __init__(self) -> None:
        self.proc: asyncio.subprocess.Process | None = None
        self.lock = asyncio.Lock()

    async def _ensure(self) -> asyncio.subprocess.Process:
        if self.proc is None or self.proc.returncode is not None:
            self.proc = await asyncio.create_subprocess_exec(
                sys.executable, "-I", str(WORKER), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, cwd="/" if os.name != "nt" else None, limit=1 << 20)
        return self.proc

    async def call(self, path: Path, text: str, timeout: float = RUN_TIMEOUT) -> dict:
        async with self.lock:
            proc = await self._ensure()
            proc.stdin.write((json.dumps({"path": str(path), "text": text}) + "\n").encode())
            await proc.stdin.drain()
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout)
            except asyncio.TimeoutError:
                proc.kill()
                self.proc = None
                return {"ok": False, "error": f"tempo scaduto ({timeout:.0f} s)"}
            if not line:
                self.proc = None
                return {"ok": False, "error": "esecutore terminato"}
            return json.loads(line)


class Library:
    def __init__(self) -> None:
        self.skills: dict[str, dict] = {}
        self.errors: list[dict] = []
        self.signature = ""
        self.worker = Worker()
        self.stats = self._load_stats()
        self.generating: dict[str, float] = {}
        USER_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_stats() -> dict:
        try:
            return json.loads(STATS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_stats(self) -> None:
        tmp = STATS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.stats, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STATS_FILE)

    @staticmethod
    def enabled() -> bool:
        return env_get("JARVIS_SKILLS", "1") != "0"

    @staticmethod
    def may_generate() -> bool:
        return env_get("JARVIS_SKILLS_GENERATE", "1") != "0"

    def scan(self) -> None:
        paths = sorted(glob.glob(str(SYSTEM_DIR / "*" / "*" / "skill.json")) + glob.glob(str(USER_DIR / "*" / "*" / "skill.json")))
        sig = "|".join(f"{p}:{os.path.getmtime(p)}" for p in paths if os.path.exists(p))
        if sig == self.signature:
            return
        self.signature = sig
        found, errors = {}, []
        for p in paths:
            folder = Path(p).parent
            try:
                m = json.loads(Path(p).read_text(encoding="utf-8"))
                m.setdefault("id", folder.name)
                m["category"] = folder.parent.name
                code = (folder / "main.py").read_text(encoding="utf-8")
                check_code(code)
                m["_patterns"] = [re.compile(x, re.I) for x in m.get("patterns", [])]
                if not m["_patterns"]:
                    raise ValueError("nessun pattern di attivazione")
            except (OSError, ValueError, SyntaxError, re.error, TypeError) as exc:
                errors.append({"path": p, "error": str(exc)[:200]})
                continue
            m["key"] = f"{m['category']}/{m['id']}"
            m["source"] = "system" if folder.is_relative_to(SYSTEM_DIR) else (m.get("source") or "user")
            m["path"] = folder / "main.py"
            m.setdefault("priority", 50 if m["source"] == "system" else 40)
            if m["key"] in found:
                errors.append({"path": p, "error": "algoritmo già presente"})
                continue
            found[m["key"]] = m
        self.skills, self.errors = found, errors
        store.touch()

    def _record(self, key: str, ok: bool, ms: float) -> None:
        s = self.stats.setdefault(key, {"uses": 0, "fails": 0, "avg_ms": ms, "enabled": True})
        s["uses" if ok else "fails"] += 1
        if ok:
            s["avg_ms"] = round(s["avg_ms"] * 0.8 + ms * 0.2, 2)
            s["last_used"] = time.time()
        self._save_stats()

    def is_enabled(self, key: str) -> bool:
        return self.stats.get(key, {}).get("enabled", True)

    def candidates(self, text: str) -> list[dict]:
        out = [m for k, m in self.skills.items() if self.is_enabled(k) and any(p.search(text) for p in m["_patterns"])]
        return sorted(out, key=lambda m: -m["priority"])

    async def try_answer(self, text: str) -> dict | None:
        if not self.enabled():
            return None
        self.scan()
        for m in self.candidates(text):
            started = time.perf_counter()
            out = await self.worker.call(m["path"], text)
            ms = (time.perf_counter() - started) * 1000
            if out.get("ok") and (out.get("speech") or out.get("result") is not None):
                self._record(m["key"], True, ms)
                out.setdefault("speech", str(out.get("result")))
                return {**out, "skill": m["key"], "name": m["name"], "total_ms": round(ms, 1)}
            if out.get("error"):
                self._record(m["key"], False, ms)
                log.info("Algoritmo %s non adatto a «%s»: %s", m["key"], text[:60], out["error"])
        return None

    def needs_algorithm(self, text: str) -> bool:
        return bool(NEED.search(text)) and len(text) < 400

    async def learn(self, text: str, models: list[str]) -> None:
        if not (self.enabled() and self.may_generate()) or DEMO:
            return
        sig = _slug(text)[:30]
        if time.time() - self.generating.get(sig, 0) < 600:
            return
        self.generating[sig] = time.time()
        prompt = (
            "Scrivi un algoritmo Python riutilizzabile che risolve richieste come questa (in italiano):\n"
            f"«{text}»\n\n"
            "Rispondi SOLO con un oggetto JSON con i campi:\n"
            '  "name": nome breve in italiano, "category": una tra ' + ", ".join(CATEGORIES) + ",\n"
            '  "description": una frase, "patterns": 1-4 espressioni regolari Python (case-insensitive) che riconoscono '
            "richieste simili con numeri o parole diverse (non solo questa frase),\n"
            '  "examples": 3 richieste di esempio, "code": il sorgente Python.\n'
            "Regole per il codice: definisci def run(text: str) -> dict che estrae i valori dal testo, calcola e "
            'restituisce {"ok": True, "result": valore, "speech": "frase in italiano con il risultato"}; se il testo '
            'non contiene i dati necessari restituisci {"ok": False, "error": "motivo"}. Usa solo i moduli: '
            + ", ".join(sorted(ALLOWED_IMPORTS)) + ". Niente file, rete, input, eval o exec. Numeri italiani: "
            "accetta la virgola decimale e le parole (più, meno, per, diviso). Arrotonda i risultati in modo leggibile.")
        from features.brain.llm import BrainUnavailable, generate
        for temperature in (0.2, 0.45):
            try:
                spec = await generate(prompt, as_json=True, max_tokens=1400, temperature=temperature, kind="deep",
                                      prefer=models)
                saved = await self._install(spec, text)
                if saved:
                    store.event("INFO", f"Nuovo algoritmo imparato: {saved}", "skills")
                    return
            except (BrainUnavailable, ValueError, KeyError, TypeError, AttributeError) as exc:
                log.info("Creazione dell'algoritmo non riuscita: %s", exc)
        log.info("Nessun algoritmo creato per «%s»", text[:80])

    async def _install(self, spec: dict, text: str) -> str | None:
        code = str(spec.get("code", ""))
        check_code(code)
        patterns = [str(p) for p in spec.get("patterns", [])][:4]
        compiled = [re.compile(p, re.I) for p in patterns]
        if not any(p.search(text) for p in compiled):
            raise ValueError("i pattern non riconoscono la richiesta di partenza")
        if any(p.search("ciao come stai") or p.search("") for p in compiled):
            raise ValueError("pattern troppo generici")
        category = spec.get("category") if spec.get("category") in CATEGORIES else "altro"
        name = str(spec.get("name") or "Algoritmo")[:60]
        folder = USER_DIR / category / _slug(name)
        if folder.exists():
            folder = USER_DIR / category / f"{_slug(name)}_{int(time.time()) % 100000}"
        tmp = folder.with_name(folder.name + ".prova")
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / "main.py").write_text(code, encoding="utf-8")
        out = await self.worker.call(tmp / "main.py", text)
        if not out.get("ok") or not (out.get("speech") or out.get("result") is not None):
            for f in tmp.iterdir():
                f.unlink()
            tmp.rmdir()
            raise ValueError(f"prova fallita: {out.get('error') or 'nessun risultato'}")
        (tmp / "skill.json").write_text(json.dumps({
            "id": folder.name, "name": name, "description": str(spec.get("description", ""))[:200],
            "patterns": patterns, "examples": [str(e)[:120] for e in spec.get("examples", [])][:5],
            "source": "ai", "created_at": time.time(), "created_from": text[:200],
            "test": {"input": text, "output": out.get("speech") or str(out.get("result"))}},
            ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(folder)
        self.signature = ""
        self.scan()
        return f"{category}/{folder.name}"

    def listing(self) -> dict:
        self.scan()
        items = []
        for k, m in sorted(self.skills.items(), key=lambda x: (x[1]["category"], x[1]["name"])):
            items.append({"key": k, "id": m["id"], "name": m["name"], "category": m["category"],
                          "category_label": CATEGORIES.get(m["category"], m["category"]),
                          "description": m.get("description", ""), "patterns": m.get("patterns", []),
                          "examples": m.get("examples", []), "source": m["source"], "priority": m["priority"],
                          "created_at": m.get("created_at"), "test": m.get("test"),
                          "stats": self.stats.get(k, {"uses": 0, "fails": 0, "enabled": True})})
        return {"skills": items, "errors": self.errors, "categories": CATEGORIES, "enabled": self.enabled(),
                "generate": self.may_generate(), "user_dir": str(USER_DIR)}

    def code(self, key: str) -> str:
        return self.skills[key]["path"].read_text(encoding="utf-8")

    def set_enabled(self, key: str, on: bool) -> None:
        if key not in self.skills:
            raise KeyError(key)
        self.stats.setdefault(key, {"uses": 0, "fails": 0, "avg_ms": 0})["enabled"] = bool(on)
        self._save_stats()

    def delete(self, key: str) -> None:
        m = self.skills.get(key)
        if not m:
            raise KeyError(key)
        if m["source"] == "system":
            raise ValueError("Gli algoritmi di sistema si possono solo disattivare")
        folder = m["path"].parent
        for f in folder.iterdir():
            f.unlink()
        folder.rmdir()
        self.stats.pop(key, None)
        self._save_stats()
        self.signature = ""
        self.scan()

    async def test(self, key: str, text: str) -> dict:
        m = self.skills.get(key)
        if not m:
            raise KeyError(key)
        started = time.perf_counter()
        out = await self.worker.call(m["path"], text)
        return {**out, "matches": any(p.search(text) for p in m["_patterns"]),
                "total_ms": round((time.perf_counter() - started) * 1000, 1)}


library = Library()
