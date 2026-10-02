import asyncio
import json
import re
import ssl
import time

from config import DEMO
from features.home_assistant.constants import RESYNC_EVERY, log
from features.home_assistant.demo import demo_payload
from state import store

try:
    import websockets
except ImportError:
    websockets = None


class HAError(Exception):
    pass


class AuthError(HAError):
    pass


class HomeConnection:
    async def run(self) -> None:
        if DEMO:
            self._ingest(**demo_payload())
            self.status, self.ha_version, self.ha_name = "online", "2026.9.0 (demo)", "Casa dimostrativa"
            return
        backoff = 2
        asyncio.create_task(self._flusher())
        while True:
            s = self.settings()
            self._creds = (s["url"], s["token"])
            if not s["enabled"]:
                self._set_status("disabled", "")
                await asyncio.sleep(5)
                continue
            if not s["url"] or not s["token"]:
                self._set_status("not_configured", "")
                await asyncio.sleep(5)
                continue
            if websockets is None:
                self._set_status("offline", "Libreria websockets mancante: verrà installata all'aggiornamento")
                await asyncio.sleep(60)
                continue
            try:
                self._set_status("connecting", "")
                await self._session(s)
                backoff = 2
            except AuthError as exc:
                self._set_status("auth_failed", str(exc) or "Token non valido")
                store.event("WARN", "Home Assistant ha rifiutato il token: rigeneralo e salvalo nelle impostazioni", "home")
                await self._wait_creds_change(300)
                continue
            except Exception as exc:
                self._set_status("offline", f"{type(exc).__name__}: {exc}"[:200])
                log.info("Home Assistant non raggiungibile: %s", exc)
            finally:
                self._ws = None
                for f in self._futures.values():
                    if not f.done():
                        f.set_exception(HAError("collegamento chiuso"))
                self._futures.clear()
            await self._wait_creds_change(backoff)
            backoff = min(60, backoff * 2)

    async def _wait_creds_change(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            s = self.settings()
            if (s["url"], s["token"]) != self._creds or not s["enabled"]:
                return
            await asyncio.sleep(2)

    def _set_status(self, status: str, error: str) -> None:
        if (status, error) != (self.status, self.error):
            self.status, self.error = status, error
            self.rev += 1
            store.touch()

    async def _session(self, s: dict) -> None:
        url = s["url"]
        ws_url = re.sub(r"^http", "ws", url, count=1) + "/api/websocket"
        ctx = None
        if ws_url.startswith("wss"):
            ctx = ssl.create_default_context()
            if not s["verify_ssl"]:
                ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        async with websockets.connect(ws_url, max_size=None, open_timeout=15, ping_interval=30, ping_timeout=30,
                                      close_timeout=3, ssl=ctx) as ws:
            first = json.loads(await asyncio.wait_for(ws.recv(), 15))
            if first.get("type") != "auth_required":
                raise HAError("risposta inattesa da Home Assistant")
            await ws.send(json.dumps({"type": "auth", "access_token": s["token"]}))
            auth = json.loads(await asyncio.wait_for(ws.recv(), 15))
            if auth.get("type") != "auth_ok":
                raise AuthError(auth.get("message", "Token non valido"))
            self._ws, self.url = ws, url
            self.ha_version = auth.get("ha_version", "")
            reader = asyncio.create_task(self._reader(ws))
            try:
                await self._call({"type": "supported_features", "features": {"coalesce_messages": 1}}, 10)
            except HAError:
                pass
            for ev in ("state_changed", "area_registry_updated", "device_registry_updated",
                       "entity_registry_updated", "floor_registry_updated"):
                await self._call({"type": "subscribe_events", "event_type": ev}, 10)
            await self.sync("collegamento")
            self.connected_at = time.time()
            self._set_status("online", "")
            store.event("INFO", f"Casa collegata: Home Assistant {self.ha_version}, {self.summary_line()}", "home")
            watcher = asyncio.create_task(self._watch(ws))
            done, _ = await asyncio.wait({reader, watcher}, return_when=asyncio.FIRST_COMPLETED)
            for t in (reader, watcher):
                t.cancel()
            for t in done:
                if t.exception() and not isinstance(t.exception(), asyncio.CancelledError):
                    raise t.exception()

    async def _watch(self, ws) -> None:
        while True:
            await asyncio.sleep(3)
            s = self.settings()
            if (s["url"], s["token"]) != self._creds or not s["enabled"]:
                await ws.close()
                return
            if time.time() - self.synced_at > RESYNC_EVERY:
                await self.sync("controllo periodico")

    async def _reader(self, ws) -> None:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            for msg in data if isinstance(data, list) else [data]:
                if msg.get("type") == "event":
                    try:
                        self._on_event(msg.get("event") or {})
                    except Exception:
                        log.exception("Evento di Home Assistant non gestito")
                    continue
                fut = self._futures.pop(msg.get("id"), None)
                if fut and not fut.done():
                    fut.set_result(msg)
        raise HAError("collegamento chiuso da Home Assistant")

    async def _call(self, payload: dict, timeout: float = 20):
        if self._ws is None:
            raise HAError("Home Assistant non collegato")
        self._id += 1
        mid = self._id
        fut = asyncio.get_running_loop().create_future()
        self._futures[mid] = fut
        await self._ws.send(json.dumps({"id": mid, **payload}))
        try:
            msg = await asyncio.wait_for(fut, timeout)
        finally:
            self._futures.pop(mid, None)
        if not msg.get("success", True):
            err = msg.get("error") or {}
            raise HAError(err.get("message") or err.get("code") or "errore")
        return msg.get("result")
