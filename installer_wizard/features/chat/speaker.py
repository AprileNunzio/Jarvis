import re

from config import env_get

from features.chat import context as request_context
from features.people import identity

SELF_VOCATIVE = re.compile(r"([,!]\s*|^)(?:J\.\s?A\.\s?R\.\s?V\.\s?I\.\s?S\.?|Jarvis)(?=\s*[!?.,;:]|\s*$)", re.I)


def name() -> str:
    profile = identity.current(request_context.voice.get())
    if profile:
        return identity.first_name(profile)
    return env_get("JARVIS_USER_NAME", "").strip().split(" ")[0]


def instruction() -> str:
    who = name()
    base = ("Tu sei Jarvis (J.A.R.V.I.S.), l'assistente. La persona che ti parla NON si chiama Jarvis: "
            "non chiamarla mai «Jarvis» o «J.A.R.V.I.S.».")
    if who:
        return f"{base} Stai parlando con {who}: chiamalo {who} oppure «signore»."
    return f"{base} Non conosci ancora il suo nome: chiamalo «signore»."


def fix_address(reply: str) -> str:
    if not reply:
        return reply
    who = name()

    def swap(m: re.Match) -> str:
        lead = m.group(1)
        if who:
            return f"{lead}{who}"
        return "" if lead.strip() in (",", "") else lead.strip()

    return SELF_VOCATIVE.sub(swap, reply)
