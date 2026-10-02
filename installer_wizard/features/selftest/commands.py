import re

from features.selftest.service import selftest

ASK = re.compile(r"\b(fai|esegui|avvia|lancia)\b.*\b(collaudo|autodiagnosi|auto-?test|controllo completo)\b"
                 r"|\b(collauda\w*)\b.*\b(te stesso|sistem\w+)\b", re.I)


async def answer(text: str) -> tuple[str, dict]:
    if not ASK.search(text):
        raise LookupError
    if selftest.running:
        return "Collaudo già in corso, signore.", {"mode": "face"}
    report = await selftest.run("a voce")
    failed = [r["label"] for r in report["results"] if r["status"] == "errore"]
    total = len(report["results"]) - report["skipped"]
    if not failed:
        return f"Collaudo completato: {report['passed']} prove su {total} superate. Tutti i sistemi nominali, signore.", {"mode": "face"}
    return (f"Collaudo completato: {report['passed']} su {total} superate. Da controllare: {', '.join(failed)}. "
            "I dettagli sono nel pannello, sezione Collaudo, signore."), {"mode": "face"}
