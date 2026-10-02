import asyncio

from features.documents import spec

PARALLEL = 3
OUTLINE = {
    "documento": (
        "Sei un autore professionista. Progetta l'indice di un documento completo e approfondito per la richiesta. "
        "Rispondi SOLO con JSON:\n"
        '{"title": "titolo", "subtitle": "sottotitolo", "theme": "moderno|aziendale|elegante|vivace|minimal|natura|tech", '
        '"sections": [{"heading": "titolo della sezione", "points": ["argomenti da trattare"], '
        '"needs": ["table", "chart", "kpi", "callout", "bullets"]}]}\n'
        "Da 6 a 10 sezioni adatte al tipo di documento (per un modulo, una dichiarazione o una lettera usa le parti "
        "proprie di quel documento, non una relazione aziendale); indica tabelle e grafici solo dove ci sono numeri. "
        + spec.VOICE
    ),
    "presentazione": (
        "Sei un consulente che prepara presentazioni efficaci. Progetta la scaletta della presentazione. Rispondi SOLO "
        "con JSON:\n"
        '{"title": "titolo", "subtitle": "sottotitolo", "theme": "moderno|aziendale|elegante|vivace|minimal|natura|tech", '
        '"slides": [{"layout": "title|section|bullets|two_columns|table|chart|kpi|quote|closing", "title": "...", '
        '"idea": "cosa deve mostrare"}]}\n'
        "Da 10 a 16 diapositive: copertina, sezioni, contenuti vari (tabelle, grafici, indicatori, due colonne), "
        "chiusura."
    ),
}
SECTION_SYSTEM = (
    "Sei un autore esperto che scrive una sezione di un documento professionale. Scrivi in modo specifico e corretto, "
    "almeno 3 paragrafi ricchi, con tabelle, grafici o indicatori solo se servono davvero e con dati coerenti. Inizia "
    "con un blocco heading di livello 1 con il titolo della sezione; puoi usare sottotitoli di livello 2. " + spec.VOICE +
    ' Rispondi SOLO con JSON {{"blocks": [...]}} usando questi tipi di blocco:\n{schema}'
)
SECTION = "Documento: «{title}».\nSezione da scrivere: «{heading}».\nArgomenti: {points}.\nSe utili: {needs}."

SLIDES = (
    "Compila queste diapositive della presentazione «{title}» con contenuti esperti, dati realistici, al massimo 5 "
    "punti brevi per diapositiva e note del relatore. Diapositive da compilare (mantieni ordine, layout e titoli):\n"
    "{items}\n" + spec.VOICE + "\nRispondi SOLO con JSON {{\"slides\": [...]}} con questa struttura:\n{schema}"
)


async def _ask(prompt: str, max_tokens: int, timeout: float = 600, system: str = ""):
    from features.brain.llm import generate
    return await generate(prompt, as_json=True, max_tokens=max_tokens, temperature=0.4, kind="deep", timeout=timeout,
                          system=system)


async def _gather(jobs: list) -> list:
    slots = asyncio.Semaphore(PARALLEL)

    async def one(coro):
        async with slots:
            try:
                return await coro
            except Exception:
                return None
    return await asyncio.gather(*(one(j) for j in jobs))


def _base(outline: dict, request: str) -> dict:
    return {"title": spec.text(outline.get("title"), 160) or spec.text(request, 80), "subtitle": spec.text(outline.get("subtitle"), 200),
            "theme": spec.text(outline.get("theme"), 20)}


async def document(request: str, context: str = "") -> dict:
    outline = await _ask(OUTLINE["documento"] + (f"\nContesto: {context}" if context else "") + f"\n\nRichiesta: {request}", 1800)
    sections = [s for s in (outline.get("sections") or []) if isinstance(s, dict) and s.get("heading")][:10] if isinstance(outline, dict) else []
    if len(sections) < 3:
        return await _single("documento", request, context)
    base = _base(outline, request)
    block_schema = spec.SCHEMAS["documento"].split('"blocks": [', 1)[1].rsplit("]", 1)[0]
    system = SECTION_SYSTEM.format(schema=block_schema)
    prompts = [SECTION.format(heading=s["heading"], title=base["title"], points="; ".join(spec.items(s.get("points"), 8)) or "a scelta",
                              needs=", ".join(spec.items(s.get("needs"), 5)) or "solo testo") +
               (f"\nContesto del progetto: {context}" if context else "") + f"\nRichiesta originale: {request}"
               for s in sections]
    parts = await _gather([_ask(p, 2600, system=system) for p in prompts])
    blocks = []
    for s, part in zip(sections, parts):
        got = (part or {}).get("blocks") if isinstance(part, dict) else None
        if not isinstance(got, list) or not got:
            got = [{"type": "heading", "level": 1, "text": s["heading"]},
                   {"type": "bullets", "items": spec.items(s.get("points"), 8) or [s["heading"]]}]
        elif not (isinstance(got[0], dict) and got[0].get("type") == "heading"):
            got = [{"type": "heading", "level": 1, "text": s["heading"]}] + got
        blocks += got
    return spec.normalize("documento", {**base, "blocks": blocks}, request)


async def presentation(request: str, context: str = "") -> dict:
    outline = await _ask(OUTLINE["presentazione"] + (f"\nContesto: {context}" if context else "") + f"\n\nRichiesta: {request}", 1800)
    plan = [s for s in (outline.get("slides") or []) if isinstance(s, dict) and s.get("title")][:18] if isinstance(outline, dict) else []
    if len(plan) < 5:
        return await _single("presentazione", request, context)
    base = _base(outline, request)
    schema = spec.SCHEMAS["presentazione"]
    groups = [plan[i:i + 4] for i in range(0, len(plan), 4)]
    prompts = [SLIDES.format(title=base["title"], schema=schema, items="\n".join(
        f"- layout {g.get('layout', 'bullets')}: «{g['title']}» — {spec.text(g.get('idea'), 300)}" for g in group)) +
        (f"\nContesto del progetto: {context}" if context else "") for group in groups]
    parts = await _gather([_ask(p, 3000) for p in prompts])
    slides = []
    for group, part in zip(groups, parts):
        got = (part or {}).get("slides") if isinstance(part, dict) else None
        if isinstance(got, list) and got:
            slides += got
        else:
            slides += [{"layout": "bullets" if g.get("layout") not in ("title", "section", "closing") else g["layout"],
                        "title": g["title"], "bullets": [spec.text(g.get("idea"), 200)]} for g in group]
    return spec.normalize("presentazione", {**base, "slides": slides}, request)


async def _single(kind: str, request: str, context: str) -> dict:
    raw = await _ask(spec.prompt(kind, request, context), 7000, 900)
    return spec.normalize(kind, raw, request)


async def design(kind: str, request: str, context: str = "") -> dict:
    if kind == "documento":
        return await document(request, context)
    if kind == "presentazione":
        return await presentation(request, context)
    return await _single(kind, request, context)
