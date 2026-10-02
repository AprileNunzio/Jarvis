import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = tempfile.mkdtemp(prefix="jarvis-tests-")
tempfile.tempdir = SANDBOX
os.environ["TMPDIR"] = SANDBOX
os.environ["JARVIS_DEMO"] = "1"
os.environ.setdefault("JARVIS_DIR", str(ROOT.parent))
for p in (str(ROOT / "backend"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT / "backend")
