import asyncio
import ipaddress
import re
import socket
import unicodedata

from features.actions.common import sh

NOISE = {"localdomain", "local", "lan", "home", "fritz", "box", "domain"}


def tokens(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return [t for t in re.split(r"[^a-z0-9]+", plain) if t and t not in NOISE]


def score(wanted: list[str], names: list[str]) -> float:
    have = {t for n in names for t in tokens(n)}
    if not wanted or not have:
        return 0.0
    joined = ["".join(tokens(n)) for n in names]
    whole = "".join(wanted)
    hits = sum(t in have for t in wanted) / len(wanted)
    exact = any(j == whole for j in joined)
    return hits + (0.5 if exact else 0.0)


async def reverse_names(ips: list[str], limit: int = 48) -> dict[str, str]:
    gate = asyncio.Semaphore(limit)

    async def one(ip: str) -> tuple[str, str]:
        async with gate:
            try:
                host = await asyncio.wait_for(asyncio.to_thread(socket.gethostbyaddr, ip), 1.5)
            except (OSError, asyncio.TimeoutError):
                return ip, ""
            return ip, host[0]

    return {ip: name for ip, name in await asyncio.gather(*(one(ip) for ip in ips)) if name}


def subnet_hosts(subnet: str, cap: int = 1024) -> list[str]:
    if not subnet:
        return []
    net = ipaddress.ip_network(subnet, strict=False)
    return [str(h) for i, h in enumerate(net.hosts()) if i < cap]


async def reachable(ip: str) -> bool:
    code, _ = await sh("ping", "-c", "1", "-W", "1", ip, timeout=4)
    return code == 0


async def candidates(explorer, wanted: str) -> list[dict]:
    known = {d["ip"]: d for d in explorer.listing()["devices"] if d.get("ip")}
    names = await reverse_names(sorted(set(subnet_hosts(explorer.subnet)) | set(known)))
    want = tokens(wanted)
    found = []
    for ip in set(known) | set(names):
        d = known.get(ip, {})
        labels = [d.get("name"), d.get("hostname"), d.get("label"), d.get("web_title"), names.get(ip)]
        value = score(want, [x for x in labels if x])
        if value >= 0.66:
            title = names.get(ip) or d.get("hostname") or d.get("label") or ip
            found.append({"score": value, "ip": ip, "name": title.removesuffix(".localdomain"), "device": d})
    found.sort(key=lambda c: -c["score"])
    for c in found[:4]:
        c["online"] = await reachable(c["ip"])
    return found
