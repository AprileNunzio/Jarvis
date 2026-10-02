from contextvars import ContextVar

device: ContextVar[str] = ContextVar("jarvis_device", default="kiosk")
voice: ContextVar[str] = ContextVar("jarvis_voice", default="")
TRUSTED = ("admin", "remote")


def trusted() -> bool:
    return device.get() in TRUSTED
