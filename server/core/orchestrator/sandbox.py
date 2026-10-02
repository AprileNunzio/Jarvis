import docker
import os
import logging
import tempfile

logger = logging.getLogger(__name__)

class EphemeralSandbox:
    """
    Esegue codice o script generati in un container Docker effimero,
    proteggendo il sistema host da codice malevolo (Zero-Trust).
    """
    def __init__(self, image="python:3.11-slim"):
        self.image = image
        try:
            self.client = docker.from_env()
        except Exception:
            logger.warning("Docker SDK non disponibile: impossibile usare la sandbox effimera.")
            self.client = None

    def run_code(self, code: str, timeout: int = 30) -> dict:
        if not self.client:
            return {"error": "Sandbox environment is not available."}
            
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
                
            try:
                container = self.client.containers.run(
                    self.image,
                    command=["python", "/workspace/script.py"],
                    volumes={tmpdir: {'bind': '/workspace', 'mode': 'ro'}},
                    working_dir="/workspace",
                    remove=True,
                    detach=False,
                    stdout=True,
                    stderr=True,
                    network_disabled=True,
                    mem_limit="128m",
                    cpu_quota=50000,
                )
                return {"stdout": container.decode("utf-8"), "error": None}
            except docker.errors.ContainerError as e:
                return {"stdout": None, "error": e.stderr.decode("utf-8")}
            except Exception as e:
                return {"stdout": None, "error": str(e)}
