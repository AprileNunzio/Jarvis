import asyncio
import logging
import time

from config import env_get
from state import store

from features.bluetooth import adapter, prefs
from features.bluetooth.router import router

log = logging.getLogger("jarvis.bluetooth")
TICK = 4
RECONNECT_EVERY = 30


class BluetoothService:
    def __init__(self) -> None:
        self.state: dict = {"controller": {"present": False}, "devices": [], "routing": {}}
        self.connected: set[str] = set()
        self.last_reconnect = 0.0
        self.prepared = False
        self.scanning_until = 0.0
        self.lock = asyncio.Lock()

    @staticmethod
    def enabled() -> bool:
        return env_get("JARVIS_BLUETOOTH", "1") != "0"

    async def _prepare(self) -> None:
        from orchestrator import converge_steps
        self.prepared = True
        store.event("INFO", "Adattatore Bluetooth rilevato: preparo il sistema", "bluetooth")
        await converge_steps(["bluetooth"], "Nuovo adattatore Bluetooth")

    def _announce(self, devs: list[dict]) -> None:
        from features.desktop.desk import desk
        now = {d["mac"] for d in devs if d["connected"]}
        names = {d["mac"]: d["name"] for d in devs}
        for mac in now - self.connected:
            store.event("INFO", f"Bluetooth collegato: {names.get(mac, mac)}", "bluetooth")
            if prefs.load()["announce"]:
                desk.show("notice", {"icon": "🎧", "title": "Bluetooth collegato", "text": names.get(mac, mac)},
                          key=f"bt:{mac}")
        for mac in self.connected - now:
            store.event("INFO", f"Bluetooth scollegato: {names.get(mac, mac)}", "bluetooth")
        self.connected = now

    async def _reconnect(self, devs: list[dict]) -> None:
        data = prefs.load()
        if not data["auto_connect"] or time.time() - self.last_reconnect < RECONNECT_EVERY:
            return
        self.last_reconnect = time.time()
        for d in devs:
            if d["paired"] and not d["connected"] and prefs.device(data, d["mac"])["autoconnect"]:
                try:
                    await adapter.connect(d["mac"])
                except adapter.BluetoothError as exc:
                    log.info("%s non raggiungibile: %s", d["name"], exc)

    async def refresh(self) -> dict:
        async with self.lock:
            ctrl = await adapter.controller()
            devs = await adapter.devices() if ctrl["present"] and ctrl["installed"] else []
            routing = await router.apply(devs) if devs else {}
            if routing.get("changed"):
                store.audio_rev = f"bt-{time.time():.0f}"
                store.touch()
            self._announce(devs)
            self.state = {"controller": ctrl, "devices": devs, "routing": routing,
                          "scanning": time.time() < self.scanning_until}
            return self.state

    async def scan(self, seconds: int = 20) -> None:
        self.scanning_until = time.time() + seconds
        await adapter.power(True)
        await adapter.scan(seconds)
        self.scanning_until = 0.0
        await self.refresh()

    async def run(self) -> None:
        while True:
            if self.enabled():
                try:
                    state = await self.refresh()
                    ctrl = state["controller"]
                    if ctrl["present"] and not ctrl["installed"] and not self.prepared:
                        await self._prepare()
                    elif ctrl["present"] and ctrl["installed"]:
                        await self._reconnect(state["devices"])
                except (OSError, ValueError, adapter.BluetoothError) as exc:
                    log.warning("Controllo Bluetooth non riuscito: %s", exc)
            await asyncio.sleep(TICK)


service = BluetoothService()
