import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parent.parent))

import uvicorn
from fastapi import FastAPI

import health
import pages
import registry_api
import system_api
import updater
from config import ADMIN_PORT, DEMO, PUBLIC_PORT, VERSION
from feature_registry import registry
from features.brain import api as brain_api
from features.brain import routing as brain_routing
from features.presentation import api as presentation_api
from features.actions import api as actions_api
from features.bluetooth import api as bluetooth_api
from features.bluetooth.service import service as bluetooth_service
from features.vision.tips import tips as object_tips
from features.nodes.beacon import beacon as node_beacon
from features.chat import api as chat_api
from features.nodes import api as nodes_api
from features.cloud import api as cloud_api
from features.desktop import api as desktop_api
from features.desktop.desk import desk
from features.documents import api as documents_api
from features.devices import api as devices_api
from features.devices import audio
from features.google import api as google_api
from features.google.gservices import google
from features.home_assistant import api as home_api
from features.home_assistant import home
from features.location import api as location_api
from features.cameras import api as cameras_api
from features.models3d import api as models3d_api
from features.ear import api as ear_api
from features.automations import api as automations_api
from features.automations.engine import engine as automations_engine
from features.autonomy import api as autonomy_api
from features.habits import api as habits_api
from features.kiosk import driver as display_driver
from features.habits.service import habits
from features.selftest import api as selftest_api
from features.shares import api as shares_api
from features.vault import api as vault_api
from features.vault.service import vault
from features.selftest.service import selftest
from features.sounds import api as sounds_api
from features.autonomy.engine import autonomy
from features.cameras.recorder import recorder as cameras_recorder
from features.laws import api as laws_api
from features.maps import api as maps_api
from features.mind import api as mind_api
from features.maps.maps import maps
from features.music import api as music_api
from features.network import api as network_api
from features.network.explorer import explorer
from features.people import api as people_api
from features.people import presence
from features.skills import api as skills_api
from features.soup import api as soup_api
from features.spotify import api as spotify_api
from features.spotify.spotify import spotify
from features.study import api as study_api
from features.study import study
from features.telegram import api as telegram_api
from features.telegram.bot import bot
from features.vision import api as vision_api
from features.voices import api as voices_api
from orchestrator import orch, telemetry_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("jarvis.supervisor")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

FEATURE_APIS = (presentation_api, actions_api, bluetooth_api, chat_api, cloud_api, voices_api, vision_api, devices_api, location_api,
                people_api, music_api, study_api, soup_api, network_api, telegram_api, home_api, brain_api,
                desktop_api, spotify_api, google_api, maps_api, skills_api, nodes_api, mind_api, laws_api, cameras_api,
                models3d_api, documents_api, ear_api, autonomy_api, automations_api, sounds_api, selftest_api, habits_api, vault_api, shares_api)


def build(admin: bool) -> FastAPI:
    title = "Jarvis OS Admin" if admin else "Jarvis OS"
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=None)
    if admin:
        pages.mount_static(app, "shared", "admin")
    else:
        pages.mount_static(app, "shared", "display", "monitor", "screen")
    kind = "admin_routes" if admin else "public_routes"
    for module in (*FEATURE_APIS, registry_api, pages, system_api):
        routes = getattr(module, kind, None)
        if routes is not None:
            app.include_router(routes)
    return app


public = build(admin=False)
admin = build(admin=True)


async def main() -> None:
    servers = [
        uvicorn.Server(uvicorn.Config(public, host="0.0.0.0", port=PUBLIC_PORT, log_level="warning",
                                     timeout_graceful_shutdown=3)),
        uvicorn.Server(uvicorn.Config(admin, host="0.0.0.0", port=ADMIN_PORT, log_level="warning",
                                     timeout_graceful_shutdown=3)),
    ]
    log.info("Jarvis OS Supervisor v%s — utente :%d — admin :%d%s", VERSION, PUBLIC_PORT, ADMIN_PORT,
             " (DEMO)" if DEMO else "")
    tasks = [asyncio.create_task(job) for job in (
        telemetry_loop(), orch.boot(), health.Watchdog(orch).run(), updater.scheduler(), presence.monitor.run(),
        bot.run(), explorer.run(), audio.watcher.run(), study.engine.run(), soup_api.trainer.run(), registry.run(),
        desk.run(), spotify.run(), google.run(), maps.run(), home.brain.run(), bluetooth_service.run(),
        object_tips.run(), node_beacon.run(), cameras_recorder.run(), autonomy.run(), automations_engine.run(), selftest.loop(), habits.run(), vault.run(), display_driver.guard(), brain_routing.run(),
    )]
    try:
        await asyncio.gather(*(s.serve() for s in servers))
    finally:
        for t in tasks:
            t.cancel()
        study.engine.save()


if __name__ == "__main__":
    asyncio.run(main())
