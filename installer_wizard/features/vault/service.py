import asyncio
import json
import logging
import time
from datetime import date, datetime
from pathlib import Path

from config import STATE_DIR, env_get
from state import store

from features.automations.bus import bus
from features.vault import diary, render

log = logging.getLogger("jarvis.vault")
FILE = STATE_DIR / "vault.json"
EXPORT_EVERY = 300
DIARY_EVERY = 1800
FINAL_AT = "23:50"


def enabled() -> bool:
    return env_get("JARVIS_VAULT", "1") != "0"


def root() -> Path:
    custom = env_get("JARVIS_VAULT_DIR", "").strip()
    if custom:
        return Path(custom)
    from features.shares import archive
    return archive.path("memoria")


class Vault:
    def __init__(self) -> None:
        try:
            self.meta = json.loads(FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.meta = {}
        self.meta.setdefault("files", {})
        self.meta.setdefault("requests", [])
        self.meta.setdefault("imports", [])
        self.last_export = 0.0
        self.last_diary = 0.0
        self.signature = ""
        bus.listen(self.on_event)

    def _save(self) -> None:
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.meta, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(FILE)

    def on_event(self, ev: dict) -> None:
        if ev["name"] == "voice_command" and enabled():
            text = str(ev["data"].get("text") or "").strip()
            if text:
                cutoff = time.time() - 2 * 86400
                self.meta["requests"] = [r for r in self.meta["requests"] if r["at"] > cutoff][-400:] + [{"at": ev["at"], "text": text[:160]}]

    def _write(self, rel: str, content: str, who: str | None = None) -> bool:
        path = root() / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if path.read_text(encoding="utf-8") == content:
                return False
        except OSError:
            pass
        path.write_text(content, encoding="utf-8")
        self.meta["files"][rel] = {"mtime": path.stat().st_mtime, "who": who}
        return True

    @staticmethod
    def _memory():
        from features.mind.mind import mind
        return mind.memory

    def import_edits(self) -> list[str]:
        memory, changed = self._memory(), []
        for rel, info in list(self.meta["files"].items()):
            if info.get("who") is None:
                continue
            path = root() / rel
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime <= info["mtime"] + 1:
                continue
            bullets = render.parse_facts(path.read_text(encoding="utf-8"))
            info["mtime"] = mtime
            if bullets is None:
                continue
            who = info["who"]
            current = [f for f in memory.facts if (f.get("who") or "") == who]
            texts = {f["text"].strip().lower() for f in current}
            wanted = {b.strip().lower() for b in bullets}
            removed = [f for f in current if f["text"].strip().lower() not in wanted]
            for f in removed:
                memory.forget(f["id"])
            added = [b for b in bullets if b.strip().lower() not in texts]
            for b in added:
                memory.add(b, "dal diario", score=0.85, who=who)
            if removed or added:
                note = f"{rel}: {len(added)} aggiunti o corretti, {len(removed)} dimenticati"
                changed.append(note)
                self.meta["imports"] = ([{"at": time.time(), "text": note}] + self.meta["imports"])[:30]
                store.event("INFO", f"Memoria aggiornata dai file: {note}", "vault")
        if changed:
            self.signature = ""
            self._save()
        return changed

    def export(self) -> int:
        from features.automations.library import library
        from features.automations.schema import catalog
        from features.people import people
        from features.people.schema import SECTIONS
        memory = self._memory()
        written = 0
        written += self._write("LEGGIMI.md", render.readme(str(root())))
        keep = {"LEGGIMI.md"}
        for p in people.all_profiles():
            slug = p.get("slug")
            name = people.display_name(p)
            rel = f"Persone/{render.safe_name(name)}.md"
            keep.add(rel)
            facts = [f for f in memory.facts if f.get("who") == slug]
            text = render.person({**p, "display_name": name, **people.computed(p)}, SECTIONS, facts,
                                 people.habits(p)["summary"] if p.get("sessions") else "")
            written += self._write(rel, text, who=slug)
        general = [f for f in memory.facts if not f.get("who")]
        written += self._write("Memoria/Fatti generali.md", render.general(general), who="")
        keep.add("Memoria/Fatti generali.md")
        written += self._write("Automazioni.md", render.automations(library.all(), catalog()))
        keep.add("Automazioni.md")
        try:
            from features.habits.service import habits
            written += self._write("Casa/Abitudini.md", render.habits(list(habits.data["suggestions"].values())))
            keep.add("Casa/Abitudini.md")
        except Exception as exc:
            log.debug("Abitudini non esportate: %s", exc)
        for rel in [r for r in self.meta["files"] if r.startswith("Persone/") and r not in keep]:
            (root() / rel).unlink(missing_ok=True)
            self.meta["files"].pop(rel, None)
        self.last_export = time.time()
        self._save()
        return written

    async def write_diary(self, day: date, final: bool) -> Path:
        data = diary.gather(day, self.meta["requests"])
        recap = await diary.summary(data) if final else ""
        rel = str(diary.path_for(Path(""), day)).replace("\\", "/")
        self._write(rel, diary.render(day, data, recap, final))
        if final:
            self.meta["final"] = day.isoformat()
        self._save()
        return root() / rel

    def read_diary(self, day: date) -> str:
        try:
            return diary.path_for(root(), day).read_text(encoding="utf-8")
        except OSError:
            return ""

    def _changed(self) -> bool:
        memory = self._memory()
        sig = f"{len(memory.facts)}:{max((f.get('updated', 0) for f in memory.facts), default=0)}"
        if sig != self.signature:
            self.signature = sig
            return True
        return time.time() - self.last_export > EXPORT_EVERY

    async def run(self) -> None:
        await asyncio.sleep(150)
        while True:
            try:
                if enabled() and store.phase in ("READY", "DEGRADED"):
                    root().mkdir(parents=True, exist_ok=True)
                    await asyncio.to_thread(self.import_edits)
                    if self._changed():
                        await asyncio.to_thread(self.export)
                    today = date.today()
                    if (self.meta.get("final") or "") < diary.yesterday().isoformat():
                        await self.write_diary(diary.yesterday(), True)
                    if datetime.now().strftime("%H:%M") >= FINAL_AT and self.meta.get("final") != today.isoformat():
                        await self.write_diary(today, True)
                    elif time.time() - self.last_diary > DIARY_EVERY:
                        self.last_diary = time.time()
                        await self.write_diary(today, False)
            except Exception as exc:
                log.warning("Memoria in file: %s", exc)
            await asyncio.sleep(60)


vault = Vault()
