#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "2.1.0"
DISCOVER_PORT = 50505
ANNOUNCE_PORT = 50506
JOIN_TIMEOUT = 15 * 60
REDISCOVER_AFTER = 3
CONFIG = Path(os.environ.get("JARVIS_NODE_CONFIG", Path.home() / ".config" / "jarvis-node.json"))
SERVICE = Path("/etc/systemd/system/jarvis-node.service")
TYPES = ("satellite", "display", "server", "esp32", "android", "sensor", "other")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jarvis-node")


def post(server: str, path: str, body: dict, headers: dict | None = None) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{server}{path}", data=data, method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read() or b"{}")


def save_config(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(cfg, handle)


def node_id(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{socket.gethostname()}-{name}".lower()).strip("-")
    return (base or "nodo")[:40]


def metrics() -> dict:
    out = {}
    with open("/proc/loadavg") as f:
        out["cpu"] = min(100.0, float(f.read().split()[0]) * 100 / (os.cpu_count() or 1))
    mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line)
    total, avail = int(mem["MemTotal"].split()[0]), int(mem["MemAvailable"].split()[0])
    out["ram"] = (total - avail) * 100 / total
    disk = shutil.disk_usage("/")
    out["disk"] = disk.used * 100 / disk.total
    out["uptime"] = float(Path("/proc/uptime").read_text().split()[0])
    zone = Path("/sys/class/thermal/thermal_zone0/temp")
    if zone.exists():
        out["temp"] = int(zone.read_text()) / 1000
    return out


def capabilities() -> list[str]:
    caps = []
    if shutil.which("arecord") and list(Path("/proc/asound").glob("card*")):
        caps.append("audio")
    if list(Path("/dev").glob("video*")):
        caps.append("camera")
    if Path("/sys/class/bluetooth").exists():
        caps.append("bluetooth")
    return caps


def discover(ident: str = "", paired: bool = False, timeout: float = 4.0) -> str | None:
    hello = json.dumps({"jarvis": "discover", "id": ident, "paired": paired, "version": VERSION}).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        try:
            sock.sendto(hello, ("255.255.255.255", DISCOVER_PORT))
            while True:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data)
                if isinstance(msg, dict) and msg.get("jarvis") == "master":
                    port = int(msg.get("port") or 80)
                    return f"http://{addr[0]}" + ("" if port == 80 else f":{port}")
        except (OSError, ValueError):
            return None


def own_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def self_update(cfg: dict, expected: str) -> None:
    with urllib.request.urlopen(f"{cfg['server']}/nodes/agent.py", timeout=30) as res:
        code = res.read()
    if hashlib.sha256(code).hexdigest() != expected:
        log.warning("Aggiornamento dell'agente scartato: impronta non corrispondente")
        return
    Path(__file__).write_bytes(code)
    log.info("Agente aggiornato: riavvio")
    os.execv(sys.executable, [sys.executable, __file__, *sys.argv[1:]])


def run_command(cmd: str, cfg: dict) -> None:
    log.info("Comando dal server: %s", cmd)
    if cmd == "identify":
        for _ in range(3):
            sys.stdout.write("\a")
            sys.stdout.flush()
            time.sleep(0.4)
        if shutil.which("espeak-ng"):
            subprocess.run(["espeak-ng", "-v", "it", f"Sono {cfg['name']}"], check=False)
    elif cmd == "update" and cfg.get("agent"):
        self_update(cfg, cfg["agent"])
    elif cmd == "restart":
        os.execv(sys.executable, [sys.executable, __file__, *sys.argv[1:]])
    elif cmd == "reboot" and os.geteuid() == 0:
        subprocess.run(["systemctl", "reboot"], check=False)


def pair(args) -> dict:
    ident = node_id(args.name)
    res = post(args.server, "/api/nodes/pair",
               {"code": args.code, "id": ident, "name": args.name, "type": args.type, "room": args.room})
    cfg = {"server": args.server, "id": ident, "token": res["token"], "name": args.name}
    save_config(cfg)
    log.info("Abbinato a %s come %s", args.server, ident)
    return cfg


def join(args) -> dict:
    server = args.server or discover(node_id(args.name))
    if not server:
        sys.exit("Nessun server Jarvis trovato in rete: indica --server http://IP-DI-JARVIS")
    ident, key = node_id(args.name), secrets.token_hex(32)
    res = post(server, "/api/nodes/request", {"id": ident, "key": key, "name": args.name, "type": args.type,
                                              "room": args.room})
    log.info("Richiesta inviata a %s. Nel pannello Nodi approva il codice %s", server, res["fingerprint"])
    print(f"Codice da confermare nel pannello Jarvis: {res['fingerprint']}", flush=True)
    deadline = time.time() + JOIN_TIMEOUT
    while time.time() < deadline:
        time.sleep(5)
        claim = post(server, "/api/nodes/claim", {"id": ident, "key": key})
        if claim.get("approved"):
            cfg = {"server": server, "id": ident, "token": claim["token"], "name": args.name}
            save_config(cfg)
            log.info("Nodo approvato e abbinato come %s", ident)
            return cfg
    sys.exit("Richiesta scaduta: nessuno l'ha approvata nel pannello")


def install_service() -> None:
    if os.geteuid() != 0:
        sys.exit("Per installare il servizio esegui con sudo")
    SERVICE.write_text(f"""[Unit]
Description=Nodo Jarvis
After=network-online.target
Wants=network-online.target

[Service]
Environment=JARVIS_NODE_CONFIG={CONFIG}
ExecStart={sys.executable} {Path(__file__).resolve()}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
""")
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "jarvis-node"], check=True)
    log.info("Servizio jarvis-node installato e avviato")


def loop(cfg: dict) -> None:
    headers = {"Authorization": f"Bearer {cfg['token']}", "X-Jarvis-Node": cfg["id"]}
    wait, failures = 30, 0
    while True:
        try:
            res = post(cfg["server"], "/api/nodes/heartbeat", {"version": VERSION, "hostname": socket.gethostname(),
                                                             "metrics": metrics(), "capabilities": capabilities()}, headers)
            wait, failures = int(res.get("heartbeat") or 30), 0
            cfg["agent"] = res.get("agent") or ""
            if cfg["agent"] and cfg["agent"] != own_sha():
                self_update(cfg, cfg["agent"])
            for cmd in res.get("commands") or []:
                run_command(cmd, cfg)
            settings = res.get("settings")
            if isinstance(settings, dict) and settings != cfg.get("settings"):
                cfg["settings"] = settings
                save_config({k: v for k, v in cfg.items() if k != "agent"})
                log.info("Impostazioni aggiornate dal server (%d personalizzate)", len(res.get("custom") or []))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                sys.exit("Il server ha revocato questo nodo: abbinalo di nuovo")
            log.warning("Server non disponibile: %s", exc)
        except (urllib.error.URLError, OSError) as exc:
            failures += 1
            log.warning("Server non raggiungibile: %s", exc)
            if failures >= REDISCOVER_AFTER:
                found = discover(cfg["id"], paired=True)
                if found and found != cfg["server"]:
                    log.info("Il server Jarvis ha cambiato indirizzo: %s", found)
                    cfg["server"] = found
                    save_config({k: v for k, v in cfg.items() if k != "agent"})
                failures = 0
        time.sleep(wait)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente dei nodi Jarvis")
    parser.add_argument("--server", help="Indirizzo del server Jarvis, es. http://192.168.1.10")
    parser.add_argument("--code", help="Codice di abbinamento mostrato nel pannello Nodi")
    parser.add_argument("--name", default=socket.gethostname())
    parser.add_argument("--room", default="")
    parser.add_argument("--type", default="satellite", choices=TYPES)
    parser.add_argument("--install", action="store_true", help="Installa l'agente come servizio di sistema")
    parser.add_argument("--join", action="store_true", help="Cerca Jarvis in rete e chiedi l'approvazione dal pannello")
    args = parser.parse_args()
    if args.code and args.server:
        cfg = pair(args)
    elif args.join:
        cfg = join(args)
    elif CONFIG.exists():
        cfg = json.loads(CONFIG.read_text())
    else:
        sys.exit("Prima abbina il nodo: --join (automatico) oppure --server http://IP-DI-JARVIS --code CODICE")
    if args.install:
        install_service()
        return
    loop(cfg)


if __name__ == "__main__":
    main()
