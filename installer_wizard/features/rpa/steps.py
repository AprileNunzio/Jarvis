from dataclasses import dataclass

MAX_STEPS = 12
POINTER_ACTIONS = ("click", "double_click", "right_click")
KEY_ACTIONS = ("type", "key", "scroll", "wait")


@dataclass(frozen=True)
class Step:
    do: str
    target: str = ""
    text: str = ""
    keys: tuple = ()
    amount: int = 0
    seconds: float = 0.0
    expect_change: bool = True

    @property
    def pointer(self) -> bool:
        return self.do in POINTER_ACTIONS


def parse_steps(raw) -> list[Step]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_STEPS:
        raise ValueError(f"servono da 1 a {MAX_STEPS} passi")
    return [_step(item, number) for number, item in enumerate(raw, start=1)]


def _step(item, number: int) -> Step:
    if not isinstance(item, dict):
        raise ValueError(f"passo {number}: formato non valido")
    action = str(item.get("do", ""))
    if action in POINTER_ACTIONS:
        target = str(item.get("target", "")).strip()
        if not 2 <= len(target) <= 200:
            raise ValueError(f"passo {number}: descrivi l'elemento da {action} (2-200 caratteri)")
        return Step(action, target=target, expect_change=bool(item.get("expect_change", True)))
    if action == "type":
        text = str(item.get("text", ""))
        if not text or len(text) > 500 or not all(32 <= ord(c) < 127 for c in text):
            raise ValueError(f"passo {number}: il testo deve essere ASCII stampabile, 1-500 caratteri")
        return Step(action, text=text, expect_change=bool(item.get("expect_change", True)))
    if action == "key":
        keys = item.get("keys")
        if not isinstance(keys, list) or not 1 <= len(keys) <= 4 or not all(isinstance(k, str) for k in keys):
            raise ValueError(f"passo {number}: indica da 1 a 4 tasti")
        return Step(action, keys=tuple(keys), expect_change=bool(item.get("expect_change", False)))
    if action == "scroll":
        amount = item.get("amount")
        if not isinstance(amount, int) or isinstance(amount, bool) or not -20 <= amount <= 20 or amount == 0:
            raise ValueError(f"passo {number}: amount deve essere un intero tra -20 e 20, diverso da 0")
        return Step(action, amount=amount, expect_change=bool(item.get("expect_change", False)))
    if action == "wait":
        seconds = item.get("seconds")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not 0 < seconds <= 10:
            raise ValueError(f"passo {number}: seconds deve essere tra 0 e 10")
        return Step(action, seconds=float(seconds), expect_change=False)
    raise ValueError(f"passo {number}: azione sconosciuta {action!r}")
