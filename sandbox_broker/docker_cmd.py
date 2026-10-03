from typing import List, Optional

from server.features.sandbox.domain.spec import ExecutionSpec, Language

_ENTRYPOINTS = {
    Language.PYTHON: ("main.py", ["python", "-I", "-B", "/in/main.py"]),
    Language.BASH: ("main.sh", ["bash", "--noprofile", "--norc", "/in/main.sh"]),
}
_TMPFS_MB = 16
_NOFILE = 256


def entrypoint_name(language: Language) -> str:
    return _ENTRYPOINTS[language][0]


def build_run_argv(
    docker_bin: str,
    name: str,
    image: str,
    spec: ExecutionSpec,
    in_dir: str,
    out_dir: str,
    uid: int,
    runtime: Optional[str] = None,
) -> List[str]:
    limits = spec.limits
    argv = [
        docker_bin, "run", "--rm", "--init",
        "--name", name,
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", str(limits.pids),
        "--memory", f"{limits.memory_mb}m",
        "--memory-swap", f"{limits.memory_mb}m",
        "--cpus", f"{limits.cpus:g}",
        "--user", f"{uid}:{uid}",
        "--ulimit", f"fsize={limits.output_bytes}",
        "--ulimit", f"nofile={_NOFILE}",
        "--ulimit", "core=0",
        "--tmpfs", f"/tmp:rw,noexec,nosuid,size={_TMPFS_MB}m",
        "--volume", f"{in_dir}:/in:ro",
        "--volume", f"{out_dir}:/out:rw",
        "--workdir", "/out",
        "--env", "HOME=/tmp",
        "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "PYTHONUNBUFFERED=1",
    ]
    if runtime:
        argv += ["--runtime", runtime]
    argv.append(image)
    argv += _ENTRYPOINTS[spec.language][1]
    return argv
