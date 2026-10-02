import asyncio
import json
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from config import DEMO, env_get
from state import store

log = logging.getLogger("jarvis.soup")

SOUP_BIN = Path("/opt/jarvis-soup/venv/bin/soup")
WORK = Path("/var/lib/jarvis/study/soup")
STATUS_FILE = WORK / "status.json"
MIN_EXAMPLES = 120
MIN_NEW_EXAMPLES = 60
OLLAMA_MODEL = "jarvis-studio"
DEFAULT_BASE = "Qwen/Qwen2.5-1.5B-Instruct"


def _load() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"runs": [], "trained_examples": 0}


class SoupTrainer:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.data = _load()
        self.proc: asyncio.subprocess.Process | None = None
        self.phase = ""
        self.gpu: dict = {}

    def _save(self) -> None:
        WORK.mkdir(parents=True, exist_ok=True)
        STATUS_FILE.write_text(json.dumps(self.data, indent=1, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def mode() -> str:
        value = env_get("JARVIS_STUDY_FINETUNE", "auto").strip().lower()
        return value if value in ("auto", "1", "0") else "auto"

    def capable(self) -> tuple[bool, str]:
        import psutil
        ram_gb = psutil.virtual_memory().total / 1024 ** 3
        if not self.gpu.get("usable"):
            return False, self.gpu.get("reason") or "Nessuna GPU NVIDIA adatta"
        if ram_gb < 7.5:
            return False, f"Servono almeno 8 GB di RAM (presenti {ram_gb:.0f} GB)"
        return True, f"{self.gpu.get('name', 'GPU')} con {self.gpu.get('vram_mb', 0)} MB e {ram_gb:.0f} GB di RAM"

    def enabled(self) -> bool:
        return self.mode() == "1" or (self.mode() == "auto" and self.capable()[0])

    def decision(self) -> str:
        ok, why = self.capable()
        if self.mode() == "1":
            return "Attivo per scelta dell'utente" + ("" if ok else f" (a tuo rischio: {why.lower()}, addestramento su CPU molto lento)")
        if self.mode() == "0":
            return "Disattivato per scelta dell'utente"
        return f"Automatico: {'attivo' if ok else 'disattivo'} — {why}"

    @staticmethod
    def base_model() -> str:
        return env_get("JARVIS_STUDY_BASE_MODEL", "") or DEFAULT_BASE

    async def probe_gpu(self) -> dict:
        if DEMO or not shutil.which("nvidia-smi"):
            self.gpu = {"present": False, "usable": False, "reason": "Nessuna GPU NVIDIA rilevata"}
            return self.gpu
        try:
            proc = await asyncio.create_subprocess_exec(
                "nvidia-smi", "--query-gpu=name,compute_cap,memory.total", "--format=csv,noheader,nounits",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
            out, _ = await asyncio.wait_for(proc.communicate(), 10)
            name, cap, vram = [x.strip() for x in out.decode().splitlines()[0].split(",")]
            usable = float(cap) >= 5.0 and float(vram) >= 4000
            self.gpu = {"present": True, "name": name, "vram_mb": int(float(vram)), "compute": cap, "usable": usable,
                        "reason": "" if usable else "Serve una GPU con almeno 4 GB e compute capability 5.0"}
        except (OSError, ValueError, IndexError, asyncio.TimeoutError):
            self.gpu = {"present": False, "usable": False, "reason": "GPU NVIDIA non utilizzabile (driver assente?)"}
        return self.gpu

    def export_dataset(self) -> Path:
        rows = self.engine.dataset()
        path = WORK / "data" / "train.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path

    def summary(self) -> dict:
        examples = len(self.engine.dataset())
        return {"enabled": self.enabled(), "mode": self.mode(), "decision": self.decision(), "installed": SOUP_BIN.exists(), "gpu": self.gpu,
                "base_model": self.base_model(), "examples": examples,
                "new_examples": max(0, examples - self.data.get("trained_examples", 0)),
                "min_examples": MIN_EXAMPLES, "phase": self.phase, "running": self.proc is not None,
                "runs": self.data.get("runs", [])[-5:], "ollama_model": OLLAMA_MODEL,
                "model_ready": bool(self.data.get("model_created"))}

    def _config(self, vram_mb: int, gpu: bool = True) -> str:
        stream = "true" if gpu and vram_mb < 8000 else "false"
        return (f"base: {self.base_model()}\n"
                "task: sft\n"
                "data:\n"
                "  train: ./data/train.jsonl\n"
                "  format: alpaca\n"
                "  val_split: 0.05\n"
                "training:\n"
                "  epochs: 2\n"
                "  lr: 2e-4\n"
                "  batch_size: auto\n"
                f"  stream_layers: {stream}\n"
                "  lora:\n"
                "    r: 16\n"
                "    alpha: 32\n"
                + ("  quantization: 4bit\n" if gpu else "")
                + "output: ./output\n")

    async def _run(self, *args: str, timeout: int) -> str:
        log_path = WORK / "soup.log"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n[{datetime.now():%Y-%m-%d %H:%M}] $ soup {' '.join(args)}\n")
        self.proc = await asyncio.create_subprocess_exec(
            "nice", "-n", "15", str(SOUP_BIN), *args, cwd=str(WORK),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        lines = []
        try:
            async def pump():
                async for raw in self.proc.stdout:
                    line = raw.decode(errors="replace").rstrip()
                    lines.append(line)
                    del lines[:-40]
                    with log_path.open("a", encoding="utf-8") as fh:
                        fh.write(line + "\n")
            await asyncio.wait_for(pump(), timeout)
            code = await self.proc.wait()
        except asyncio.TimeoutError:
            self.proc.kill()
            raise RuntimeError(f"soup {args[0]}: tempo scaduto")
        finally:
            self.proc = None
        if code:
            raise RuntimeError(f"soup {args[0]} terminato con codice {code}: {' | '.join(lines[-3:])[:300]}")
        return "\n".join(lines)

    async def _unload_ollama(self) -> None:
        import httpx
        from config import ollama_url
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                loaded = (await client.get(f"{ollama_url()}/api/ps")).json().get("models", [])
                for m in loaded:
                    await client.post(f"{ollama_url()}/api/generate", json={"model": m["name"], "keep_alive": 0})
        except Exception:
            pass

    async def train(self, reason: str = "") -> dict:
        if self.proc is not None:
            return {"ok": False, "message": "Addestramento già in corso"}
        gpu = await self.probe_gpu()
        on_gpu = bool(gpu.get("usable"))
        if not on_gpu and self.mode() != "1":
            return {"ok": False, "message": f"{gpu.get('reason', 'GPU non adatta')}: per addestrare comunque sulla CPU "
                                            "scegli «Sempre attivo» (a tuo rischio, molto lento)"}
        if not SOUP_BIN.exists():
            return {"ok": False, "message": "Ambiente Soup non installato: attiva il consolidamento e attendi l'installazione"}
        dataset = self.export_dataset()
        examples = sum(1 for _ in dataset.open(encoding="utf-8"))
        if examples < MIN_EXAMPLES:
            return {"ok": False, "message": f"Servono almeno {MIN_EXAMPLES} esempi (ora {examples}): Jarvis deve studiare ancora"}
        run = {"started": time.time(), "examples": examples, "base": self.base_model(), "reason": reason, "result": ""}
        self.data.setdefault("runs", []).append(run)
        store.event("INFO", f"Soup: consolidamento nei pesi avviato ({examples} esempi, {self.base_model()})", "study")
        try:
            (WORK / "soup.yaml").write_text(self._config(gpu.get("vram_mb", 0), on_gpu), encoding="utf-8")
            shutil.rmtree(WORK / "output", ignore_errors=True)
            if on_gpu:
                await self._unload_ollama()
            self.phase = "Addestramento LoRA"
            await self._run("train", "--config", "soup.yaml", timeout=6 * 3600)
            self.phase = "Esportazione GGUF"
            try:
                await self._run("export", "--model", "./output", "--format", "gguf", "--quant", "q4_k_m", timeout=3600)
            except RuntimeError:
                self.phase = "Unione dell'adattatore"
                await self._run("merge", "--adapter", "./output", timeout=3600)
                merged = max((p.parent for p in WORK.rglob("config.json") if "output" not in p.parts[-2:-1]),
                             key=lambda p: p.stat().st_mtime, default=WORK / "output")
                await self._run("export", "--model", str(merged), "--format", "gguf", "--quant", "q4_k_m", timeout=3600)
            gguf = max(WORK.rglob("*.gguf"), key=lambda p: p.stat().st_mtime, default=None)
            if gguf is None:
                raise RuntimeError("file GGUF non trovato dopo l'esportazione")
            self.phase = "Registrazione in Ollama"
            (WORK / "Modelfile").write_text(f"FROM {gguf}\nPARAMETER temperature 0.6\n", encoding="utf-8")
            proc = await asyncio.create_subprocess_exec("ollama", "create", OLLAMA_MODEL, "-f", str(WORK / "Modelfile"),
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            out, _ = await asyncio.wait_for(proc.communicate(), 1800)
            if proc.returncode:
                raise RuntimeError(f"ollama create: {out.decode(errors='replace')[-200:]}")
            run["result"] = "ok"
            self.data["trained_examples"] = examples
            self.data["model_created"] = time.time()
            store.event("INFO", f"Soup: modello «{OLLAMA_MODEL}» pronto ({examples} esempi)", "study")
            return {"ok": True, "message": f"Modello {OLLAMA_MODEL} addestrato e registrato"}
        except Exception as exc:
            run["result"] = f"errore: {exc}"[:300]
            store.event("ERROR", f"Soup: consolidamento non riuscito — {exc}"[:300], "study")
            return {"ok": False, "message": str(exc)[:300]}
        finally:
            run["finished"] = time.time()
            self.phase = ""
            self._save()

    def _night(self) -> bool:
        s = self.engine.settings
        if s.get("hours_from") and s.get("hours_to"):
            return self.engine._in_hours()
        return 2 <= datetime.now().hour < 6

    async def run(self) -> None:
        await self.probe_gpu()
        await asyncio.sleep(120)
        while True:
            try:
                if (self.enabled() and SOUP_BIN.exists() and self._night()
                        and time.time() - self.engine.last_activity > 30 * 60 and self.proc is None):
                    examples = len(self.engine.dataset())
                    if (examples >= MIN_EXAMPLES
                            and examples - self.data.get("trained_examples", 0) >= MIN_NEW_EXAMPLES):
                        await self.train("notturno automatico")
            except Exception:
                log.exception("Pianificazione Soup non riuscita")
            await asyncio.sleep(1800)
