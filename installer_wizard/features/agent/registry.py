import inspect

TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, args: dict, confirm=False, full_only: bool = False):
    def wrap(fn):
        TOOLS[name] = {"name": name, "description": description, "args": args, "fn": fn, "confirm": confirm,
                       "full_only": full_only}
        return fn
    return wrap


def available(level: str) -> list[dict]:
    return [t for t in TOOLS.values() if level == "completo" or not t["full_only"]]


def describe(level: str) -> str:
    rows = []
    for t in available(level):
        args = ", ".join(f"{k}: {v}" for k, v in t["args"].items())
        rows.append(f"- {t['name']}({args}): {t['description']}")
    return "\n".join(rows)


def clean_args(name: str, args) -> dict:
    fn = TOOLS[name]["fn"]
    params = inspect.signature(fn).parameters
    args = args if isinstance(args, dict) else {}
    return {k: v for k, v in args.items() if k in params}


def needs_confirm(name: str, args: dict) -> bool:
    rule = TOOLS[name]["confirm"]
    if callable(rule):
        try:
            return bool(rule(args))
        except Exception:
            return True
    return bool(rule)


async def run(name: str, args: dict) -> str:
    out = await TOOLS[name]["fn"](**clean_args(name, args))
    return str(out)[:6000]
