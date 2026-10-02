from features.chat.layout import plan_text


def compose_generic(reply: str, question: str) -> tuple[str, dict]:
    return plan_text(reply, question)
