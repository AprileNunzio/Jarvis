from fastapi import APIRouter, Depends

from access import require_admin
from features.selftest.checks import CHECKS
from features.selftest.service import selftest
from tasks import background

public_routes = APIRouter()
admin_routes = APIRouter()


@admin_routes.get("/api/selftest")
async def overview(_: str = Depends(require_admin)):
    return {"running": selftest.running, "history": selftest.data["history"], "good_rev": selftest.data.get("good_rev", ""),
            "checks": [{"key": k, "label": label, "critical": crit} for k, label, crit, _ in CHECKS]}


@admin_routes.post("/api/selftest/run")
async def run_now(_: str = Depends(require_admin)):
    if selftest.running:
        return {"ok": False, "message": "Collaudo già in corso"}
    background(selftest.run("dal pannello"))
    return {"ok": True, "message": "Collaudo avviato: circa un minuto"}
