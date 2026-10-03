import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Dict, Optional

from server.core.kernel.domain.node import NodeState

logger = logging.getLogger("jarvis.orchestrator.interrupt")


class ProjectState(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    INTERRUPTED = "interrupted"


@dataclass
class ProjectHandle:
    task_id: str
    name: str
    state_file: Path
    pause_event: asyncio.Event
    task: Optional[asyncio.Task] = None


class ProjectCheckpoint:
    def __init__(self, manager: "LongRunningTaskManager", handle: ProjectHandle) -> None:
        self._manager = manager
        self._handle = handle

    async def wait_if_paused(self) -> None:
        if self._handle.pause_event.is_set():
            return
        self._manager.write_state(self._handle, ProjectState.PAUSED, None)
        await self._handle.pause_event.wait()
        self._manager.write_state(self._handle, ProjectState.RUNNING, None)


class ProjectObserver:
    def __init__(self, manager: "LongRunningTaskManager", handle: ProjectHandle) -> None:
        self._manager = manager
        self._handle = handle

    async def on_transition(self, node_id: str, state: NodeState, completed: int, total: int) -> None:
        self._manager.write_state(self._handle, ProjectState.RUNNING, int(completed * 100 / max(total, 1)))


ProjectWork = Callable[[ProjectCheckpoint, ProjectObserver], Awaitable[bool]]


class LongRunningTaskManager:
    def __init__(self, state_dir: str = "data/projects") -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.active_tasks: Dict[str, ProjectHandle] = {}

    async def start_project(self, task_id: str, name: str, work: ProjectWork) -> str:
        pause_event = asyncio.Event()
        pause_event.set()
        handle = ProjectHandle(task_id, name, self.state_dir / f"{task_id}.json", pause_event)
        self.active_tasks[task_id] = handle
        self.write_state(handle, ProjectState.RUNNING, 0)
        handle.task = asyncio.create_task(self._supervise(handle, work))
        return task_id

    async def _supervise(self, handle: ProjectHandle, work: ProjectWork) -> None:
        try:
            succeeded = await work(ProjectCheckpoint(self, handle), ProjectObserver(self, handle))
            self.write_state(handle, ProjectState.COMPLETED if succeeded else ProjectState.ERROR, 100 if succeeded else None)
        except asyncio.CancelledError:
            self.write_state(handle, ProjectState.INTERRUPTED, None)
            raise
        except Exception:
            logger.exception("project %s failed", handle.task_id)
            self.write_state(handle, ProjectState.ERROR, None)
        finally:
            self.active_tasks.pop(handle.task_id, None)

    def pause_project(self, task_id: str) -> bool:
        handle = self.active_tasks.get(task_id)
        if handle is None:
            return False
        handle.pause_event.clear()
        return True

    def resume_project(self, task_id: str) -> bool:
        handle = self.active_tasks.get(task_id)
        if handle is None:
            return False
        handle.pause_event.set()
        return True

    def write_state(self, handle: ProjectHandle, state: ProjectState, progress: Optional[int]) -> None:
        previous = self._read(handle.state_file)
        payload = {"status": state.value, "progress": previous.get("progress", 0) if progress is None else progress, "name": handle.name}
        handle.state_file.write_text(json.dumps(payload), encoding="utf-8")

    def mark_interrupted_projects(self) -> int:
        marked = 0
        for path in self.state_dir.glob("*.json"):
            data = self._read(path)
            if data.get("status") in (ProjectState.RUNNING.value, ProjectState.PAUSED.value):
                data["status"] = ProjectState.INTERRUPTED.value
                path.write_text(json.dumps(data), encoding="utf-8")
                marked += 1
        return marked

    @staticmethod
    def _read(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}


project_manager = LongRunningTaskManager()
