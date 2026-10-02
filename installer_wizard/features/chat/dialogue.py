import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass

KEEP = 10
STALE_SECONDS = 15 * 60
ELLIPSIS = re.compile(r"^\s*(?:e|ed|invece|anche|mentre)\s+(?P<rest>.{1,60}?)\s*\??\s*$", re.I)
TIME_WORDS = re.compile(r"\b(?:oggi|domani|dopodomani|stasera|stanotte|stamattina|ieri|questa settimana|"
                        r"(?:questo |il prossimo )?weekend|fine settimana|luned[iì]|marted[iì]|mercoled[iì]|"
                        r"gioved[iì]|venerd[iì]|sabato|domenica|tra \d+ giorni|la prossima settimana)\b", re.I)
PLACE = re.compile(r"\b(?:a|ad|in|per|da|su)\s+([A-ZÀ-Ý][\wÀ-ÿ'-]+(?:\s+[A-ZÀ-Ý][\wÀ-ÿ'-]+)?)")
SKILL_INTENTS = {"weather", "gservices", "maps", "place", "home", "action", "system", "network", "time", "music"}


@dataclass
class Turn:
    text: str
    reply: str
    intent: str
    at: float


class Dialogue:

    def __init__(self) -> None:
        self.turns: dict[str, deque] = defaultdict(lambda: deque(maxlen=KEEP))

    def remember(self, device: str, text: str, reply: str, intent: str) -> None:
        self.turns[device].append(Turn(text[:400], reply[:600], intent or "", time.time()))

    def recent(self, device: str) -> list[Turn]:
        now = time.time()
        return [t for t in self.turns[device] if now - t.at < STALE_SECONDS]

    def last(self, device: str) -> Turn | None:
        turns = self.recent(device)
        return turns[-1] if turns else None

    def resolve(self, device: str, text: str) -> str:
        last = self.last(device)
        m = ELLIPSIS.match(text)
        if not last or not m or last.intent not in SKILL_INTENTS:
            return text
        rest = m.group("rest").strip(" ?!.")
        new_time, new_place = TIME_WORDS.search(rest), PLACE.search(rest)
        base = last.text.rstrip(" ?!.")
        if new_time and TIME_WORDS.search(base):
            base = TIME_WORDS.sub(new_time.group(0), base, count=1)
        elif new_time:
            base = f"{base} {new_time.group(0)}"
        if new_place and PLACE.search(base):
            base = PLACE.sub(new_place.group(0), base, count=1)
        elif new_place:
            base = f"{base} {new_place.group(0)}"
        if not new_time and not new_place:
            return text
        return base + "?"

    def context(self, device: str) -> str:
        lines = []
        for t in self.recent(device)[-6:]:
            lines.append(f"Utente: {t.text}")
            lines.append(f"Jarvis: {t.reply[:300]}")
        return "\n".join(lines)

    def asked_question(self, device: str) -> bool:
        last = self.last(device)
        return bool(last and last.reply.rstrip().endswith("?") and time.time() - last.at < 60)

    def since_reply(self, device: str) -> float:
        last = self.last(device)
        return time.time() - last.at if last else 1e9


dialogue = Dialogue()
