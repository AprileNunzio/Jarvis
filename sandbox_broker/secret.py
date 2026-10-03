from typing import Callable

_KEY = "JARVIS_SECRET_KEY"


def read_secret(env_file: str) -> str:
    try:
        with open(env_file, encoding="utf-8") as handle:
            for line in handle:
                name, _, value = line.strip().partition("=")
                if name == _KEY:
                    return value.strip().strip("'\"")
    except OSError:
        return ""
    return ""


def secret_provider(env_file: str) -> Callable[[], str]:
    return lambda: read_secret(env_file)
