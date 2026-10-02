import re

from fastapi import APIRouter, Depends

from access import require_admin
from config import DEMO, env_get
from features.actions.common import SMB_CONF, my_ip

public_routes = APIRouter()
admin_routes = APIRouter()
USER = "jarvis-share"


@admin_routes.get("/api/shares")
async def overview(_: str = Depends(require_admin)):
    from health import sh
    try:
        conf = SMB_CONF.read_text(errors="ignore")
    except OSError:
        conf = ""
    shares = []
    for name, body in re.findall(r"(?ms)^\[([^\]]+)\]\s*\n(.*?)(?=^\[|\Z)", conf):
        if name.lower() in ("global", "printers", "print$", "homes"):
            continue
        path = re.search(r"(?m)^\s*path\s*=\s*(.+)$", body)
        guest = re.search(r"(?mi)^\s*guest ok\s*=\s*yes", body)
        shares.append({"name": name, "path": path.group(1).strip() if path else "", "guest": bool(guest)})
    active = "demo" if DEMO else (await sh("systemctl", "is-active", "smbd", timeout=5))[1].strip()
    ip = my_ip()
    return {"active": active, "ip": ip, "windows": f"\\\\{ip}", "user": USER, "password": env_get("JARVIS_SMB_PASSWORD", ""),
            "shares": shares}
