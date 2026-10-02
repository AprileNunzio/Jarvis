import asyncio
import logging
import json
from enum import Enum
from pathlib import Path

logger = logging.getLogger("jarvis.orchestrator.interrupt")

class ProjectState(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"

class LongRunningTaskManager:
    """
    Gestisce i task lunghi (es. tutta la notte) permettendo l'interruzione (Semi-Pausa)
    per gestire richieste utente rapide a più alta priorità.
    """
    def __init__(self, state_dir: str = "data/projects"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.active_tasks = {}

    async def start_project(self, task_id: str, agent_coroutine):
        """Avvia un progetto lungo in background."""
        logger.info("Avvio progetto a lungo termine: %s", task_id)
        
        # Inizializza lo stato
        state_file = self.state_dir / f"{task_id}.json"
        self._save_state(state_file, {"status": ProjectState.RUNNING.value, "progress": 0, "name": task_id})
        
        # Creiamo un Event per controllare la pausa
        pause_event = asyncio.Event()
        pause_event.set() # True significa "corri", False significa "in pausa"
        
        self.active_tasks[task_id] = {
            "task": None,
            "pause_event": pause_event,
            "state_file": state_file
        }
        
        # Avvolgiamo la coroutine dell'agente con il gestore di interruzioni
        async def wrapped_agent():
            try:
                # Simuliamo il loop dell'agente che periodicamente controlla se è in pausa
                for i in range(1, 101):
                    if not pause_event.is_set():
                        logger.info("Progetto %s in SEMI-PAUSA. Attesa ripresa...", task_id)
                        self._save_state(state_file, {"status": ProjectState.PAUSED.value, "progress": i, "name": task_id})
                        await pause_event.wait()
                        logger.info("Progetto %s RIPRESO.", task_id)
                        self._save_state(state_file, {"status": ProjectState.RUNNING.value, "progress": i, "name": task_id})
                        
                    await asyncio.sleep(1) # Simula lavoro pesante
                    self._save_state(state_file, {"status": ProjectState.RUNNING.value, "progress": i, "name": task_id})
                    
                self._save_state(state_file, {"status": ProjectState.COMPLETED.value, "progress": 100, "name": task_id})
                logger.info("Progetto %s completato con successo.", task_id)
            except asyncio.CancelledError:
                logger.warning("Progetto %s cancellato forzatamente.", task_id)
            except Exception as e:
                logger.error("Progetto %s andato in errore: %s", task_id, e)
                self._save_state(state_file, {"status": ProjectState.ERROR.value, "progress": -1, "name": task_id})
            finally:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]

        # Avvia il task asincrono
        task = asyncio.create_task(wrapped_agent())
        self.active_tasks[task_id]["task"] = task
        return task_id

    def pause_project(self, task_id: str):
        """Mette in semi-pausa il progetto per liberare risorse (Interrupt)."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id]["pause_event"].clear()
            return True
        return False

    def resume_project(self, task_id: str):
        """Riprende il progetto."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id]["pause_event"].set()
            return True
        return False

    def _save_state(self, path: Path, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
    async def load_and_resume_all(self):
        """Metodo per auto-resumare i progetti non completati dopo un crash o riavvio"""
        if not self.state_dir.exists():
            return
        logger.info("Verifica di progetti sospesi per auto-resume...")
        for f in self.state_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                if data.get("status") in [ProjectState.RUNNING.value, ProjectState.PAUSED.value]:
                    task_id = f.stem
                    logger.info("Trovato progetto %s interrotto. Ripristino in corso...", task_id)
                    # Nella realtà re-invocheresti la coroutine originale (es. passando l'ID all'agent).
                    # Qui invochiamo il dummy per dimostrazione
                    await self.start_project(task_id, None)
            except Exception as e:
                logger.error("Impossibile caricare lo stato del progetto %s: %s", f, e)

project_manager = LongRunningTaskManager()
