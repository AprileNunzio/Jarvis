#!/usr/local/bin/python3 -I
import base64
import ctypes
import io
import json
import os
import re
import resource
import signal
import subprocess
import sys
import tarfile

MARK = "@@JARVIS@@"
UID = 65534
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ENTRY = {"python": ["python3", "-I", "-B", "/in/main.py"], "bash": ["bash", "--noprofile", "--norc", "/in/main.sh"]}
MS_NOSUID, MS_NODEV, MS_NOEXEC = 2, 4, 8
RESTART = 0x01234567
libc = ctypes.CDLL(None, use_errno=True)


def mount(source, target, fstype, flags=0, data=""):
    if libc.mount(source.encode(), target.encode(), fstype.encode(), flags, data.encode() or None) != 0:
        raise OSError(ctypes.get_errno(), "mount " + target)


def emit(key, value):
    raw = value if isinstance(value, bytes) else str(value).encode()
    sys.stdout.write(MARK + " " + key + " " + base64.b64encode(raw).decode("ascii") + "\n")
    sys.stdout.flush()


def read_spec():
    with open("/proc/cmdline", encoding="ascii") as handle:
        for token in handle.read().split():
            if token.startswith("jarvis.spec="):
                return json.loads(base64.b64decode(token.split("=", 1)[1]))
    raise RuntimeError("missing spec")


def read_frame(device):
    with open(device, "rb") as handle:
        length = int.from_bytes(handle.read(8), "big")
        return handle.read(length)


def extract_inputs(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:") as archive:
        for member in archive.getmembers():
            if member.isreg() and NAME.match(member.name):
                target = os.path.join("/in", member.name)
                with open(target, "wb") as handle:
                    handle.write(archive.extractfile(member).read())
                os.chmod(target, 0o444)


def collect_outputs(limit):
    buffer = io.BytesIO()
    total = 0
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for entry in sorted(os.scandir("/out"), key=lambda e: e.name):
            info = entry.stat(follow_symlinks=False)
            if not entry.is_file(follow_symlinks=False) or not NAME.match(entry.name) or total + info.st_size > limit:
                continue
            tar_info = tarfile.TarInfo(entry.name)
            tar_info.size = info.st_size
            tar_info.mode = 0o444
            with open(entry.path, "rb") as handle:
                archive.addfile(tar_info, handle)
            total += info.st_size
    payload = buffer.getvalue()
    with open("/dev/vdc", "r+b") as device:
        device.write(len(payload).to_bytes(8, "big") + payload)
        device.flush()
        os.fsync(device.fileno())


def prepare_child(spec):
    def apply():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_NPROC, (spec["pids"], spec["pids"]))
        resource.setrlimit(resource.RLIMIT_FSIZE, (spec["out"], spec["out"]))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.setgroups([])
        os.setgid(UID)
        os.setuid(UID)
    return apply


def run_payload(spec):
    process = subprocess.Popen(
        ENTRY[spec["language"]], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd="/out", preexec_fn=prepare_child(spec),
        env={"HOME": "/tmp", "PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"},
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=spec["wall"])
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    emit("stdout", stdout[: spec["out"]])
    emit("stderr", stderr[: spec["out"]])
    if timed_out:
        emit("timeout", "1")
    emit("exit", process.returncode)


def mount_all(spec):
    mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC)
    mount("tmpfs", "/tmp", "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "size=16m,mode=1777")
    mount("tmpfs", "/in", "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "size=9m,mode=0755")
    mount("tmpfs", "/out", "tmpfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, "size=%d,mode=0700" % (spec["out"] + 65536))
    os.chown("/out", UID, UID)


def mount_devices():
    try:
        mount("devtmpfs", "/dev", "devtmpfs", MS_NOSUID | MS_NOEXEC)
    except OSError:
        if not os.path.exists("/dev/vdb"):
            raise


def main():
    try:
        mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC)
        spec = read_spec()
        mount_devices()
        mount_all(spec)
        extract_inputs(read_frame("/dev/vdb"))
        run_payload(spec)
        collect_outputs(spec["out"])
    except BaseException as exc:
        print("guest failure: %s: %s" % (type(exc).__name__, exc))
        emit("stderr", "guest failure: %s: %s" % (type(exc).__name__, exc))
        emit("exit", 125)
    sys.stdout.flush()
    os.sync()
    libc.reboot(RESTART)


if __name__ == "__main__":
    main()
