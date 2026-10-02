import asyncio
from datetime import date

from fastapi import APIRouter, Depends

from access import require_admin
from features.shares import archive
from features.vault.service import enabled, root, vault

public_routes = APIRouter()
admin_routes = APIRouter()


@admin_routes.get("/api/vault")
async def overview(_: str = Depends(require_admin)):
    files = sorted(vault.meta["files"])
    return {"enabled": enabled(), "root": str(root()), "share": f"{archive.SHARE}/{archive.FOLDERS['memoria']}",
            "files": files, "last_export": vault.last_export, "imports": vault.meta["imports"][:10],
            "today": vault.read_diary(date.today())[:6000]}


@admin_routes.post("/api/vault/sync")
async def sync(_: str = Depends(require_admin)):
    imported = await asyncio.to_thread(vault.import_edits)
    written = await asyncio.to_thread(vault.export)
    await vault.write_diary(date.today(), False)
    return {"imported": imported, "written": written, "message": f"Memoria sincronizzata: {written} file aggiornati, {len(imported)} modifiche lette"}
