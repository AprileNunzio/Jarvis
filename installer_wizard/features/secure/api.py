import socket

from access import require_display
from config import STATE_DIR
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

public_routes = APIRouter()
TLS_DIR = STATE_DIR / "tls"
CA_FILE = TLS_DIR / "ca.pem"
_active = {"port": 0}


def announce(port: int) -> None:
    _active["port"] = port


@public_routes.get("/jarvis-ca.crt")
async def ca_certificate():
    if not CA_FILE.exists():
        raise HTTPException(404, "Certificato non ancora generato")
    return FileResponse(CA_FILE, media_type="application/x-x509-ca-cert", filename="jarvis-os-ca.crt")


@public_routes.get("/api/secure/status")
async def secure_status(request: Request):
    require_display(request)
    return {"https_port": _active["port"], "ca": "/jarvis-ca.crt", "host": socket.gethostname()}
