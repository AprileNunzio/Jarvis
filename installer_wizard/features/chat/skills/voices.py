import re


async def voices_skill(text: str) -> tuple[str, dict]:
    from features.voices import languages
    from features.voices.catalog import describe
    from features.voices.downloads import ensure_language
    from features.voices.overview import overview
    names = {a: c for c, (_, _, aliases) in languages.LANGS.items() for a in aliases}
    words = re.findall(r"[a-zà-ÿ]+", text.lower())
    lang = next((names.get(w) or names.get(w[:-1] + "o") for w in words if names.get(w) or names.get(w[:-1] + "o")), None)
    if lang:
        label = languages.label(lang).lower()
        state = await ensure_language(lang)
        if state["status"] == "download":
            d = describe(state["voice"])
            speech = (f"Sto scaricando la voce {d['name']} in {label}, circa {d['size_mb'] or 60} megabyte. "
                      f"Tra poco potrò parlarle in {label}: mi dica «parlami in {label}» quando desidera.")
        elif state["status"] == "pronta":
            d = describe(state["voice"])
            speech = (f"Ho già la voce {d['name']} per l'{label}" if label[0] in "aeiou" else
                      f"Ho già la voce {d['name']} per il {label}") + f". Dimmi «parlami in {label}» e la uso."
        else:
            speech = f"Non ho trovato voci in {label} nel catalogo. Posso comunque risponderti per iscritto in {label}."
        return speech, {"mode": "face"}
    data = await overview()
    ready: dict[str, int] = {}
    for v in data["voices"]:
        if v["installed"]:
            ready[v["lang"]] = ready.get(v["lang"], 0) + 1
    labels = [languages.label(c).lower() for c in sorted(ready, key=lambda c: (c != "it", -ready[c]))]
    speech = (f"Posso parlarti subito in {len(labels)} lingue, tra cui {', '.join(labels[:8])}. "
              f"In tutto conosco {len(data['voices'])} voci in {len(data['langs'])} lingue: se me ne chiedi una "
              "nuova la scarico da solo. Prova a dirmi «parlami in inglese» o «insegnami lo spagnolo».")
    items = [{"label": languages.label(c), "value": f"{ready[c]} voci pronte", "status": "ok"}
             for c in sorted(ready, key=lambda c: (c != "it", languages.label(c)))]
    return speech, {"mode": "focus", "title": "Le mie voci", "subtitle": f"{len(data['voices'])} voci nel catalogo",
                    "panels": [{"type": "list", "title": "Lingue pronte", "items": items}]}
