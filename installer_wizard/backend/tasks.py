import asyncio
import logging

import health
from config import DEMO
from state import store

log = logging.getLogger("jarvis.supervisor")
_background_tasks: set = set()


def _task_done(task: asyncio.Task) -> None:
    _background_tasks.discard(task)
    if not task.cancelled() and task.exception():
        log.error("Azione in background fallita: %s", task.exception())
        store.event("ERROR", f"Azione fallita: {task.exception()}", "admin")


def background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_task_done)


async def delayed(*cmd: str) -> None:
    await asyncio.sleep(2)
    if not DEMO:
        await health.sh(*cmd, timeout=30)
