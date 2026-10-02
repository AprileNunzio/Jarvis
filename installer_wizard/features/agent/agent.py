import json
import time

from state import store

from features.agent import registry, tools_comm, tools_display, tools_files, tools_system
from features.agent.paths import FILES, AccessDenied, level
from features.automations import tools as tools_automations
from features.documents import tools as tools_documents
from features.autonomy import tools as tools_autonomy
from features.brain.llm import BrainUnavailable, generate

MODULES = (tools_comm, tools_display, tools_files, tools_system, tools_autonomy, tools_automations, tools_documents)
MAX_STEPS = 8
PENDING_TTL = 180

RULES = (
    "Sei Jarvis, l'assistente che agisce davvero sul server di casa usando gli strumenti qui sotto.\n"
    "Strumenti disponibili:\n{tools}\n\n"
    "Cartella di lavoro: {files} (i percorsi relativi partono da qui).\n"
    "Rispondi SEMPRE e SOLO con un oggetto JSON, uno di questi due:\n"
    '{{"tool": "nome_strumento", "args": {{...}}}}  per usare UNO strumento e vederne l\'esito;\n'
    '{{"answer": "frase finale breve in italiano, da dire a voce, dando del Lei e chiamando «signore» chi parla"}}  quando hai finito, oppure per chiedere '
    "un'informazione che manca (per esempio l'indirizzo email).\n"
    "Regole: non inventare esiti, aspetta il risultato di ogni strumento; non ripetere uno strumento già riuscito; "
    "per mandare un progetto usa i percorsi restituiti dagli strumenti; se un destinatario è un nome, cercalo con "
    "find_contact; se uno strumento fallisce prova un'alternativa o spiega il problema. Esegui SUBITO ciò che "
    "viene chiesto con gli strumenti diretti (create_site, write_file, make_dir, create_3d, share_folder…): crea "
    "automazioni o compiti programmati solo se l'utente chiede esplicitamente qualcosa di ricorrente, programmato "
    "o condizionato. Tutto ciò che crei va nella cartella condivisa di Jarvis, già organizzata in sottocartelle."
)


def _summary(name: str, args: dict) -> str:
    a = registry.clean_args(name, args)
    if name == "send_email":
        att = a.get("attachments")
        extra = f" con allegati {att}" if att else ""
        return f"invio l'email a {a.get('to')} con oggetto «{a.get('subject', '')}»{extra}"
    if name == "delete":
        return f"sposto nel cestino {a.get('path')}"
    if name == "run_command":
        return f"eseguo il comando «{a.get('command')}»"
    if name in ("write_file", "make_dir"):
        return f"scrivo in {a.get('path')}, fuori dalla cartella di lavoro"
    if name in ("copy", "move"):
        return f"{'copio' if name == 'copy' else 'sposto'} {a.get('src')} in {a.get('dst')}"
    return f"eseguo {name} con {json.dumps(a, ensure_ascii=False)[:200]}"


class Agent:
    def __init__(self) -> None:
        self.pending: dict | None = None
        self.last_steps: list[dict] = []

    def tools(self) -> str:
        return registry.describe(level())

    async def _decide(self, request: str, steps: list[dict]) -> dict:
        history = "\n".join(f"{i + 1}. {s['tool']}({json.dumps(s['args'], ensure_ascii=False)[:300]}) → {s['result'][:1200]}"
                            for i, s in enumerate(steps))
        prompt = f"Richiesta: {request}\n\n" + (f"Passi già eseguiti:\n{history}\n\nProssima mossa?" if steps else "Prima mossa?")
        reply = await generate(prompt, as_json=True, max_tokens=900, temperature=0.1, kind="deep",
                               system=RULES.format(tools=self.tools(), files=FILES), timeout=240)
        return reply if isinstance(reply, dict) else {}

    async def _execute(self, name: str, args: dict, steps: list[dict]) -> None:
        try:
            result = await registry.run(name, args)
        except (AccessDenied, PermissionError) as exc:
            result = f"NEGATO: {exc}"
        except Exception as exc:
            result = f"ERRORE: {str(exc)[:300]}"
        steps.append({"tool": name, "args": registry.clean_args(name, args), "result": result})
        store.event("INFO", f"Agente · {name}: {result[:140]}", "agent")

    async def run(self, request: str, steps: list[dict] | None = None, auto: str = "", trusted: bool = False,
                  routine: str = "") -> str:
        steps = [] if steps is None else steps
        self.last_steps = steps
        registry.REQUEST.set(request)
        allowed = {t["name"] for t in registry.available(level())}
        for _ in range(MAX_STEPS):
            try:
                move = await self._decide(request, steps)
            except BrainUnavailable as exc:
                return f"Il mio cervello non è raggiungibile in questo momento: {exc}"
            if move.get("answer") or not move.get("tool"):
                return str(move.get("answer") or "Fatto, signore.")[:600]
            name, args = str(move["tool"]), move.get("args") or {}
            if name not in allowed:
                steps.append({"tool": name, "args": {}, "result": "ERRORE: strumento inesistente o non consentito"})
                continue
            if registry.needs_confirm(name, args) and not (auto and trusted):
                if auto:
                    from features.autonomy import approvals
                    item = approvals.add(auto, _summary(name, args), request, steps, name, args, routine)
                    await self.on_approval(item)
                    return f"In attesa della sua approvazione, signore: {_summary(name, args)}."
                self.pending = {"request": request, "steps": steps, "tool": name, "args": args, "at": time.time()}
                return f"Prima di procedere: {_summary(name, args)}. Confermi?"
            await self._execute(name, args, steps)
        done = [s for s in steps if not s["result"].startswith(("ERRORE", "NEGATO"))]
        return f"Ho eseguito {len(done)} passi ma non ho finito del tutto: ripetimi cosa manca."

    async def on_approval(self, item: dict) -> None:
        pass

    async def resume(self, item: dict, yes: bool) -> str:
        if not yes:
            return "Annullato."
        steps = item["steps"]
        await self._execute(item["tool"], item["args"], steps)
        return await self.run(item["request"], steps, auto=item["title"], trusted=bool(item.get("trusted")),
                              routine=item.get("routine", ""))

    def has_pending(self) -> bool:
        if self.pending and time.time() - self.pending["at"] > PENDING_TTL:
            self.pending = None
        return bool(self.pending)

    async def confirm(self, yes: bool) -> str:
        p, self.pending = self.pending, None
        if not p:
            return "Non avevo nulla in sospeso."
        if not yes:
            return "Annullato, signore."
        await self._execute(p["tool"], p["args"], p["steps"])
        return await self.run(p["request"], p["steps"])


agent = Agent()
__all__ = ["agent", "MODULES"]
