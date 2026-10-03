#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import shutil
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path

VERSION = "1.0.0"
CONFIG = Path(os.environ.get("JARVIS_NODE_CONFIG", "/etc/jarvis-node.json"))
log = logging.getLogger("jarvis-rpa")

ACTIONS = {"capture", "click", "double_click", "right_click", "move", "drag", "type", "key", "scroll", "wait"}
MAX_TEXT = 500
MAX_WAIT = 10.0
MIN_INTERVAL = 0.05
SETTLE_POLL = 0.25
SETTLE_LIMIT = 3.0
STABLE_RATIO = 0.0005
PIXEL_TOLERANCE = 48
SAMPLE_STEP = 4

KEYS = {c: k for c, k in zip("abcdefghijklmnopqrstuvwxyz", (30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50, 49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44))}
KEYS.update({c: k for c, k in zip("1234567890", range(2, 12))})
KEYS.update({"enter": 28, "esc": 1, "tab": 15, "space": 57, "backspace": 14, "delete": 111, "up": 103, "down": 108,
             "left": 105, "right": 106, "home": 102, "end": 107, "pageup": 104, "pagedown": 109, "ctrl": 29,
             "shift": 42, "alt": 56, "super": 125, "-": 12, "=": 13, "[": 26, "]": 27, ";": 39, "'": 40, ",": 51,
             ".": 52, "/": 53, "\\": 43, "`": 41})
KEYS.update({f"f{i}": 58 + i for i in range(1, 11)})
SHIFTED = dict(zip('!@#$%^&*()_+{}:"<>?|~', "1234567890-=[];'" + ",./\\`"))

EV_SYN, EV_KEY, EV_REL, EV_ABS = 0, 1, 2, 3
ABS_X, ABS_Y, REL_WHEEL = 0, 1, 8
BTN = {"left": 0x110, "right": 0x111}
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045566, 0x40045567
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
FBIOGET_VSCREENINFO = 0x4600


def validate(instruction: dict, width: int, height: int) -> dict:
    action = instruction.get("action")
    if action not in ACTIONS:
        raise ValueError(f"unsupported action {action!r}")
    clean = {"id": str(instruction.get("id", ""))[:64], "action": action}
    for name in ("x", "y", "x2", "y2"):
        if name in instruction:
            value = instruction[name]
            limit = width if name.startswith("x") else height
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < limit:
                raise ValueError(f"{name} must be an integer inside the screen")
            clean[name] = value
    needs = {"click": ("x", "y"), "double_click": ("x", "y"), "right_click": ("x", "y"), "move": ("x", "y"),
             "drag": ("x", "y", "x2", "y2")}
    for name in needs.get(action, ()):
        if name not in clean:
            raise ValueError(f"{action} needs {name}")
    if action == "type":
        text = instruction.get("text")
        if not isinstance(text, str) or not text or len(text) > MAX_TEXT or not all(32 <= ord(c) < 127 for c in text):
            raise ValueError("text must be 1-500 printable ASCII characters")
        clean["text"] = text
    if action == "key":
        combo = instruction.get("keys")
        if not isinstance(combo, list) or not 1 <= len(combo) <= 4 or any(k not in KEYS for k in combo):
            raise ValueError("keys must list 1-4 known key names")
        clean["keys"] = combo
    if action == "scroll":
        amount = instruction.get("amount")
        if not isinstance(amount, int) or not -20 <= amount <= 20 or amount == 0:
            raise ValueError("amount must be a non-zero integer between -20 and 20")
        clean["amount"] = amount
    if action == "wait":
        seconds = instruction.get("seconds")
        if not isinstance(seconds, (int, float)) or not 0 < seconds <= MAX_WAIT:
            raise ValueError(f"seconds must be between 0 and {MAX_WAIT:g}")
        clean["seconds"] = float(seconds)
    region = instruction.get("region")
    if region is not None:
        if (not isinstance(region, list) or len(region) != 4 or not all(isinstance(v, int) for v in region)
                or region[2] <= 0 or region[3] <= 0 or region[0] < 0 or region[1] < 0
                or region[0] + region[2] > width or region[1] + region[3] > height):
            raise ValueError("region must be [x, y, w, h] inside the screen")
        clean["region"] = region
    contrast = instruction.get("min_contrast")
    if contrast is not None:
        if not isinstance(contrast, (int, float)) or isinstance(contrast, bool) or not 0 <= contrast <= 255 or region is None:
            raise ValueError("min_contrast must be a number between 0 and 255 and needs a region")
        clean["min_contrast"] = float(contrast)
    clean["return_frame"] = bool(instruction.get("return_frame", False))
    return clean


class Frame:
    def __init__(self, width: int, height: int, rgb: bytes) -> None:
        self.width, self.height, self.rgb = width, height, rgb

    def to_png(self) -> bytes:
        stride = self.width * 3
        raw = b"".join(b"\x00" + self.rgb[y * stride:(y + 1) * stride] for y in range(self.height))

        def chunk(kind: bytes, data: bytes) -> bytes:
            body = kind + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 3)) + chunk(b"IEND", b""))


def decode_png(data: bytes) -> Frame:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    try:
        from io import BytesIO

        from PIL import Image

        image = Image.open(BytesIO(data)).convert("RGB")
        return Frame(image.width, image.height, image.tobytes())
    except ImportError:
        return decode_png_pure(data)


def decode_png_pure(data: bytes) -> Frame:
    position, idat, header = 8, [], None
    while position < len(data):
        length, kind = struct.unpack(">I4s", data[position:position + 8])
        body = data[position + 8:position + 8 + length]
        position += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    if header is None:
        raise ValueError("missing IHDR")
    width, height, depth, color, _, _, interlace = header
    if depth != 8 or color not in (2, 6) or interlace:
        raise ValueError("unsupported PNG format")
    channels = 3 if color == 2 else 4
    raw, stride = zlib.decompress(b"".join(idat)), width * channels
    out, previous = bytearray(), bytearray(stride)
    for row in range(height):
        start = row * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b, c = previous[i], (previous[i - channels] if i >= channels else 0)
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        previous = line
        out += line if channels == 3 else b"".join(line[i:i + 3] for i in range(0, stride, 4))
    return Frame(width, height, bytes(out))


def changed_ratio(before: Frame, after: Frame, region: list | None = None) -> float:
    if (before.width, before.height) != (after.width, after.height):
        return 1.0
    x0, y0, w, h = region or [0, 0, before.width, before.height]
    changed = total = 0
    for y in range(y0, y0 + h, SAMPLE_STEP):
        row = y * before.width * 3
        for x in range(x0, x0 + w, SAMPLE_STEP):
            i = row + x * 3
            diff = abs(before.rgb[i] - after.rgb[i]) + abs(before.rgb[i + 1] - after.rgb[i + 1]) + abs(before.rgb[i + 2] - after.rgb[i + 2])
            changed += diff > PIXEL_TOLERANCE
            total += 1
    return changed / total if total else 0.0


def region_contrast(frame: Frame, region: list) -> float:
    x0, y0, w, h = region
    values = [frame.rgb[(y * frame.width + x) * 3:(y * frame.width + x) * 3 + 3] for y in range(y0, y0 + h, 2) for x in range(x0, x0 + w, 2)]
    if not values:
        return 0.0
    luma = [(v[0] * 299 + v[1] * 587 + v[2] * 114) / 1000 for v in values]
    mean = sum(luma) / len(luma)
    return (sum((v - mean) ** 2 for v in luma) / len(luma)) ** 0.5


def _framebuffer() -> Frame:
    import fcntl

    with open("/dev/fb0", "rb") as fb:
        info = struct.unpack("=" + "I" * 40, fcntl.ioctl(fb, FBIOGET_VSCREENINFO, b"\x00" * 160))
        width, height, virtual_width, bits = info[0], info[1], info[2], info[6]
        step = bits // 8
        if step not in (2, 4):
            raise OSError(f"unsupported framebuffer depth {bits}")
        raw = fb.read(virtual_width * step * height)
    out = bytearray()
    for y in range(height):
        start = y * virtual_width * step
        row = raw[start:start + width * step]
        if step == 4:
            for x in range(0, width * 4, 4):
                out += bytes((row[x + 2], row[x + 1], row[x]))
        else:
            for x in range(0, width * 2, 2):
                value = row[x] | row[x + 1] << 8
                out += bytes(((value >> 11) * 255 // 31, ((value >> 5) & 63) * 255 // 63, (value & 31) * 255 // 31))
    return Frame(width, height, bytes(out))


PNG_TOOLS = (["grim", "-t", "png", "-"], ["maim"], ["import", "-window", "root", "png:-"])


def capture() -> Frame:
    for command in PNG_TOOLS:
        if shutil.which(command[0]):
            result = subprocess.run(command, capture_output=True, timeout=15, check=False)
            if result.returncode == 0 and result.stdout[:4] == b"\x89PNG":
                return decode_png(result.stdout)
    if os.path.exists("/dev/fb0"):
        return _framebuffer()
    raise OSError("no screen capture backend available (install grim, maim or imagemagick, or expose /dev/fb0)")


class VirtualInput:
    def __init__(self, width: int, height: int) -> None:
        import fcntl

        self._fcntl = fcntl
        self.width, self.height = width, height
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        for ev in (EV_KEY, EV_ABS, EV_REL, EV_SYN):
            self._fcntl.ioctl(self.fd, UI_SET_EVBIT, ev)
        for code in set(KEYS.values()) | set(BTN.values()):
            self._fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
        self._fcntl.ioctl(self.fd, UI_SET_RELBIT, REL_WHEEL)
        for axis in (ABS_X, ABS_Y):
            self._fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
        maximum, zeros = [0] * 64, [0] * 64
        maximum[ABS_X], maximum[ABS_Y] = width - 1, height - 1
        os.write(self.fd, struct.pack("80sHHHHi" + "i" * 256, b"jarvis-rpa", 3, 1, 1, 1, 0, *maximum, *zeros, *zeros, *zeros))
        self._fcntl.ioctl(self.fd, UI_DEV_CREATE)
        time.sleep(0.5)

    def _emit(self, kind: int, code: int, value: int) -> None:
        now = time.time()
        os.write(self.fd, struct.pack("llHHi", int(now), int((now % 1) * 1e6), kind, code, value))

    def _sync(self) -> None:
        self._emit(EV_SYN, 0, 0)

    def move(self, x: int, y: int) -> None:
        self._emit(EV_ABS, ABS_X, x)
        self._emit(EV_ABS, ABS_Y, y)
        self._sync()

    def button(self, name: str, pressed: bool) -> None:
        self._emit(EV_KEY, BTN[name], int(pressed))
        self._sync()

    def key(self, code: int, pressed: bool) -> None:
        self._emit(EV_KEY, code, int(pressed))
        self._sync()

    def wheel(self, amount: int) -> None:
        self._emit(EV_REL, REL_WHEEL, amount)
        self._sync()

    def close(self) -> None:
        self._fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        os.close(self.fd)


def keystrokes(text: str) -> list[tuple[int, bool]]:
    steps = []
    for char in text:
        shifted = char.isupper() or char in SHIFTED
        base = "space" if char == " " else SHIFTED.get(char, char.lower())
        if base not in KEYS:
            raise ValueError(f"cannot type {char!r}")
        if shifted:
            steps.append((KEYS["shift"], True))
        steps += [(KEYS[base], True), (KEYS[base], False)]
        if shifted:
            steps.append((KEYS["shift"], False))
    return steps


class Executor:
    def __init__(self, device, grab=capture, sleep=time.sleep) -> None:
        self.device, self.grab, self.sleep = device, grab, sleep
        self._last = 0.0

    def run(self, instruction: dict, frame: Frame) -> dict:
        action = instruction["action"]
        if action == "capture":
            return {"changed_ratio": 0.0, "region_ratio": 0.0, "settled": True, "width": frame.width, "height": frame.height}
        pace = MIN_INTERVAL - (time.monotonic() - self._last)
        if pace > 0:
            self.sleep(pace)
        region = instruction.get("region")
        anchor = round(region_contrast(frame, region), 2) if region else None
        if anchor is not None and anchor < instruction.get("min_contrast", 0.0):
            return {"changed_ratio": 0.0, "region_ratio": 0.0, "settled": True, "width": frame.width, "height": frame.height,
                    "anchor_contrast": anchor, "acted": False}
        self._act(instruction)
        self._last = time.monotonic()
        after, settled = self._settle()
        result = {"changed_ratio": round(changed_ratio(frame, after), 5), "settled": settled, "width": after.width,
                  "height": after.height, "region_ratio": round(changed_ratio(frame, after, region), 5) if region else None,
                  "anchor_contrast": anchor, "acted": True}
        return result | {"_frame": after}

    def _act(self, i: dict) -> None:
        action, d = i["action"], self.device
        if action == "wait":
            self.sleep(i["seconds"])
        elif action in ("move", "click", "double_click", "right_click", "drag"):
            d.move(i["x"], i["y"])
            if action == "drag":
                d.button("left", True)
                for step in range(1, 11):
                    d.move(i["x"] + (i["x2"] - i["x"]) * step // 10, i["y"] + (i["y2"] - i["y"]) * step // 10)
                    self.sleep(0.02)
                d.button("left", False)
            elif action != "move":
                name = "right" if action == "right_click" else "left"
                for _ in range(2 if action == "double_click" else 1):
                    d.button(name, True)
                    d.button(name, False)
                    self.sleep(0.05)
        elif action == "type":
            for code, pressed in keystrokes(i["text"]):
                d.key(code, pressed)
                self.sleep(0.01)
        elif action == "key":
            codes = [KEYS[k] for k in i["keys"]]
            for code in codes:
                d.key(code, True)
            for code in reversed(codes):
                d.key(code, False)
        elif action == "scroll":
            d.wheel(i["amount"])

    def _settle(self) -> tuple[Frame, bool]:
        deadline, previous = time.monotonic() + SETTLE_LIMIT, None
        while True:
            self.sleep(SETTLE_POLL)
            current = self.grab()
            if previous is not None and changed_ratio(previous, current) <= STABLE_RATIO:
                return current, True
            previous = current
            if time.monotonic() > deadline:
                return current, False


def post(cfg: dict, path: str, body: dict, timeout: float = 40) -> dict:
    request = urllib.request.Request(cfg["server"] + path, json.dumps(body).encode(), {
        "Content-Type": "application/json", "Authorization": f"Bearer {cfg['token']}", "X-Jarvis-Node": cfg["id"]})
    with urllib.request.urlopen(request, timeout=timeout) as res:
        return json.loads(res.read() or b"{}")


def handle(raw: dict, executor: Executor, grab=capture) -> dict:
    result = {"id": str(raw.get("id", ""))[:64], "ok": False}
    try:
        frame = grab()
        instruction = validate(raw, frame.width, frame.height)
        outcome = executor.run(instruction, frame)
        after = outcome.pop("_frame", frame)
        result |= {"ok": True, "data": outcome}
        if instruction["return_frame"] or instruction["action"] == "capture":
            result["frame"] = base64.b64encode(after.to_png()).decode()
    except (ValueError, OSError, subprocess.SubprocessError, zlib.error) as exc:
        result["error"] = f"{exc.__class__.__name__}: {exc}"[:300]
    return result


def own_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def serve(cfg: dict) -> None:
    probe = capture()
    executor = Executor(VirtualInput(probe.width, probe.height))
    failures = 0
    while True:
        try:
            reply = post(cfg, "/api/nodes/rpa/poll", {"version": VERSION, "sha": own_sha(), "screen": [probe.width, probe.height]})
            failures = 0
            update = reply.get("update")
            if update and update != own_sha():
                code = urllib.request.urlopen(cfg["server"] + "/nodes/rpa_daemon.py", timeout=30).read()
                if hashlib.sha256(code).hexdigest() == update:
                    Path(__file__).write_bytes(code)
                    os.execv(sys.executable, [sys.executable, __file__, *sys.argv[1:]])
            if reply.get("instruction"):
                post(cfg, "/api/nodes/rpa/result", handle(reply["instruction"], executor))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                sys.exit("Il server ha revocato questo nodo")
            time.sleep(min(60, 5 * (1 + failures)))
            failures += 1
        except (urllib.error.URLError, OSError) as exc:
            failures += 1
            log.warning("Server non raggiungibile: %s", exc)
            time.sleep(min(60, 5 * failures))


def main() -> None:
    parser = argparse.ArgumentParser(description="Demone di controllo dell'host per l'RPA cognitivo di Jarvis")
    parser.add_argument("--check", action="store_true", help="Verifica cattura schermo e input virtuale, poi esce")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not CONFIG.exists():
        sys.exit("Nodo non abbinato: esegui prima l'agente con --join o --code")
    if args.check:
        frame = capture()
        device = VirtualInput(frame.width, frame.height)
        device.close()
        print(f"ok: schermo {frame.width}x{frame.height}, dispositivo di input virtuale creato")
        return
    serve(json.loads(CONFIG.read_text()))


if __name__ == "__main__":
    main()
