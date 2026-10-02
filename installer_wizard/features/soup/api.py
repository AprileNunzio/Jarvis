import re

from fastapi import APIRouter, Depends, HTTPException, Request

from access import require_admin
from config import write_env
from features.soup.trainer import SoupTrainer
from features.study import study
from orchestrator import orch
from state import store
from tasks import background

admin_routes = APIRouter()
trainer = SoupTrainer(study.engine)
study.engine.external_busy = lambda: trainer.proc is not None
_HF_MODEL_RE = re.compile(r"^[\w.\-]+/[\w.\-]+$")


@admin_routes.put("/api/study/soup")
async def admin_study_soup(request: Request, user: str = Depends(require_admin)):
    body = await request.json()
    updates = {}
    if body.get("mode") in ("auto", "1", "0"):
        updates["JARVIS_STUDY_FINETUNE"] = body["mode"]
    if "base_model" in body:
        base = str(body["base_model"]).strip()
        if base and not _HF_MODEL_RE.match(base):
            raise HTTPException(400, "Modello base non valido (formato organizzazione/nome di Hugging Face)")
        updates["JARVIS_STUDY_BASE_MODEL"] = base
    if updates:
        write_env(updates)
        store.event("INFO", f"Consolidamento Soup aggiornato da {user}", "study")
        if "JARVIS_STUDY_FINETUNE" in updates:
            background(orch.converge(["soup"], reason="Configurazione del consolidamento dello studio"))
    await trainer.probe_gpu()
    return trainer.summary()


@admin_routes.post("/api/study/soup/train")
async def admin_study_train(user: str = Depends(require_admin)):
    if trainer.proc is not None:
        raise HTTPException(409, "Addestramento già in corso")
    background(trainer.train(f"avviato da {user}"))
    return {"ok": True}
