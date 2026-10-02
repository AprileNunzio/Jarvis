import re
from datetime import datetime

FACTS_TITLE = "## Cosa so"
HINT = ("_Può modificare questo elenco: cancelli una riga e Jarvis la dimentica, la corregga e Jarvis aggiorna il ricordo, "
        "ne aggiunga una (iniziando con «- ») e Jarvis la impara._")


def safe_name(text: str) -> str:
    return re.sub(r"[^\w\- àèéìòùÀÈÉÌÒÙ']", "", text).strip()[:60] or "Senza nome"


def _value(v) -> str:
    if isinstance(v, (list, tuple)):
        return ", ".join(_value(x) for x in v if x not in (None, "", [], {}))
    if isinstance(v, dict):
        return ", ".join(f"{k} {_value(x)}" for k, x in v.items() if x not in (None, "", [], {}))
    return str(v).strip()


def facts_block(facts: list[dict]) -> str:
    lines = [f"- {f['text']}" for f in sorted(facts, key=lambda f: -f.get("score", 0))]
    return f"{FACTS_TITLE}\n{HINT}\n\n" + ("\n".join(lines) if lines else "- ") + "\n"


def person(profile: dict, sections: list[dict], facts: list[dict], habits: str) -> str:
    name = profile.get("display_name") or profile.get("name") or profile.get("slug")
    out = [f"# {name}", ""]
    for sec in sections:
        if sec.get("private"):
            continue
        rows = []
        for f in sec["fields"]:
            v = _value(profile.get(f["key"]))
            if v:
                rows.append(f"- **{f['label']}**: {v}")
        if rows:
            out += [f"## {sec.get('icon', '')} {sec['title']}".replace("  ", " "), *rows, ""]
    if habits:
        out += ["## Abitudini osservate", habits, ""]
    out.append(facts_block(facts))
    return "\n".join(out)


def general(facts: list[dict]) -> str:
    return "# Fatti generali\n\nCiò che Jarvis ricorda e non riguarda una persona precisa.\n\n" + facts_block(facts)


def parse_facts(text: str) -> list[str] | None:
    if FACTS_TITLE not in text:
        return None
    block = text.split(FACTS_TITLE, 1)[1]
    block = re.split(r"\n## ", block, maxsplit=1)[0]
    out = []
    for line in block.splitlines():
        m = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if m and len(m.group(1)) >= 3:
            out.append(m.group(1))
    return out


def automations(items: list[dict], kinds: dict) -> str:
    out = ["# Automazioni", "", f"Aggiornato il {datetime.now():%d/%m/%Y alle %H:%M}. Si modificano dal pannello, scheda Automazioni.", ""]
    for a in items:
        state = "attiva" if a.get("enabled", True) else "disattivata"
        out.append(f"## {a['name']} ({state})")
        if a.get("description"):
            out.append(a["description"])
        out.append("- **Quando**: " + "; ".join(kinds["triggers"].get(t["type"], {}).get("label", t["type"]) for t in a.get("triggers", [])))
        if a.get("conditions"):
            out.append("- **Solo se**: " + "; ".join(kinds["conditions"].get(c["type"], {}).get("label", c["type"]) for c in a["conditions"]))
        out.append("- **Allora**: " + "; ".join(kinds["actions"].get(x["type"], {}).get("label", x["type"]) for x in a.get("actions", [])))
        out.append(f"- Eseguita {a.get('runs', 0)} volte, ultima: {a.get('last_status') or 'mai'}")
        out.append("")
    return "\n".join(out)


def habits(suggestions: list[dict]) -> str:
    labels = {"new": "da decidere", "snoozed": "rimandata", "accepted": "automatizzata", "rejected": "rifiutata"}
    out = ["# Abitudini della casa", "", "Regolarità che Jarvis ha notato nell'uso della casa.", ""]
    for s in sorted(suggestions, key=lambda s: -s["confidence"]):
        out.append(f"- {s['text'][0].upper() + s['text'][1:]} — {s['support']} volte su {s['observed']} ({labels.get(s['status'], s['status'])})")
    return "\n".join(out) + "\n"


def readme(root: str) -> str:
    return (
        "# La memoria di Jarvis\n\n"
        "Questa cartella è la memoria di Jarvis in chiaro: la può leggere, correggere e completare.\n\n"
        "- **Persone/**: una scheda per persona con anagrafica, gusti e ciò che Jarvis sa di lei. "
        "Salute e documenti restano solo nel pannello.\n"
        "- **Memoria/Fatti generali.md**: ciò che Jarvis ricorda e non riguarda una persona.\n"
        "- **Diario/**: una nota per ogni giorno con ciò che è successo.\n"
        "- **Casa/Abitudini.md**: le regolarità notate nell'uso della casa.\n"
        "- **Automazioni.md**: cosa fanno le automazioni attive.\n\n"
        "Nelle sezioni «Cosa so» può cancellare, correggere o aggiungere righe: Jarvis le rilegge entro pochi minuti. "
        "Le altre parti vengono riscritte da Jarvis.\n\n"
        f"Percorso sul server: `{root}`\n"
    )
