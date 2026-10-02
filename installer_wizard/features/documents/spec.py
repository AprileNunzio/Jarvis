import re

KINDS = {"docx": "documento", "odt": "documento", "pdf": "documento", "xlsx": "foglio", "ods": "foglio",
         "pptx": "presentazione", "odp": "presentazione"}
BASE_FORMAT = {"documento": "docx", "foglio": "xlsx", "presentazione": "pptx"}
CHARTS = {"bar", "column", "line", "pie", "doughnut", "area", "scatter"}
TONES = {"info", "success", "warning", "danger"}
PLACEHOLDER = re.compile(r"^\s*(<[^<>]{1,60}>|\.\.\.|…)\s*$")
MARKS = re.compile(r"\*\*|(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)|`")
VOICE = ("Il testo è un documento destinato a lettori terzi: scrivi in modo impersonale o istituzionale, non rivolgerti "
         "all'utente, non usare «Signore» o «Signor», non commentare queste istruzioni e non ripeterle. I valori tra < > "
         "sono solo segnaposto: sostituiscili sempre con contenuti veri. Se non conosci con certezza un dato specifico "
         "(norme, scadenze, importi ufficiali), scrivi cosa va verificato invece di inventarlo.")
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")

COMMON = ('"title": "titolo", "subtitle": "sottotitolo", "author": "autore", "theme": "moderno|aziendale|elegante|'
          'vivace|minimal|natura|tech", "palette": ["#rrggbb"] facoltativa, "font": "carattere" facoltativo')
CHART = ('{"type": "chart", "chart": "bar|column|line|pie|doughnut|area|scatter", "title": "...", '
         '"categories": ["<categoria>"], "series": [{"name": "<serie>", "values": ["<numeri>"]}], "unit": "<unità>"}')
SCHEMAS = {
    "documento": (
        "{" + COMMON + ', "blocks": [\n'
        '  {"type": "heading", "level": 1, "text": "..."},\n'
        '  {"type": "paragraph", "text": "paragrafo completo; **grassetto** per i concetti chiave, *corsivo*, [link](https://...)", '
        '"align": "left|center|right|justify"},\n'
        '  {"type": "bullets", "items": ["..."]}, {"type": "numbered", "items": ["..."]},\n'
        '  {"type": "table", "columns": ["<colonna>", "<colonna>"], "rows": [["<testo>", "<numero>"]], "caption": "<didascalia>", '
        '"totals": true solo se ha senso sommare},\n'
        "  " + CHART + ",\n"
        '  {"type": "kpi", "items": [{"label": "<nome indicatore>", "value": "<valore>", "delta": "<variazione>"}]},\n'
        '  {"type": "callout", "tone": "info|success|warning|danger", "title": "...", "text": "..."},\n'
        '  {"type": "quote", "text": "...", "author": "..."},\n'
        '  {"type": "link", "text": "testo del collegamento", "target": "chiave di un altro documento del progetto, solo se esiste"},\n'
        '  {"type": "pagebreak"}\n]}'
    ),
    "foglio": (
        "{" + COMMON + ', "sheets": [{"name": "<nome foglio>", "description": "<riga introduttiva>", '
        '"columns": [{"title": "<titolo colonna>", "type": "text|number|currency|percent|date|integer", "width": 24}], '
        '"rows": [["<testo>", "<numero>"]], "formulas": {"<colonna calcolata>": "=B{r}*C{r}"}, "totals": true, '
        '"chart": ' + CHART + ', "links": [{"text": "<testo>", "target": "<chiave documento>"}]}]}'
    ),
    "presentazione": (
        "{" + COMMON + ', "slides": [\n'
        '  {"layout": "title", "title": "...", "subtitle": "..."},\n'
        '  {"layout": "section", "title": "..."},\n'
        '  {"layout": "bullets", "title": "...", "bullets": ["..."], "notes": "note del relatore"},\n'
        '  {"layout": "two_columns", "title": "...", "left": ["..."], "right": ["..."], "left_title": "...", '
        '"right_title": "..."},\n'
        '  {"layout": "table", "title": "...", "table": {"columns": ["..."], "rows": [["..."]]}},\n'
        '  {"layout": "chart", "title": "...", "chart": ' + CHART + "},\n"
        '  {"layout": "kpi", "title": "...", "items": [{"label": "...", "value": "...", "delta": "..."}]},\n'
        '  {"layout": "quote", "text": "...", "author": "..."},\n'
        '  {"layout": "closing", "title": "Grazie", "subtitle": "contatti"}\n]}'
    ),
}
GUIDE = {
    "documento": ("Scrivi come un professionista del settore: struttura chiara con titoli, testo ricco e specifico, "
                  "tabelle con dati realistici e coerenti, almeno un grafico quando ci sono numeri, indicatori chiave "
                  "per i riepiloghi."),
    "foglio": ("Progetta un foglio di calcolo professionale: colonne tipizzate, dati realistici, formule per i calcoli "
               "(usa {r} per il numero di riga), totali, un grafico che riassume i dati, più fogli se utile."),
    "presentazione": ("Progetta una presentazione moderna di 8-14 diapositive: copertina, sezioni, al massimo 5 punti "
                      "brevi per diapositiva, tabelle e grafici con dati realistici, indicatori, chiusura; aggiungi le "
                      "note del relatore."),
}


def prompt(kind: str, request: str, context: str = "") -> str:
    return (f"{GUIDE[kind]} {VOICE}\nRispondi SOLO con un oggetto JSON con questa struttura (usa solo i tipi elencati):\n"
            f"{SCHEMAS[kind]}\n" + (f"\nContesto del progetto:\n{context}\n" if context else "") +
            f"\nRichiesta: {request}")


def text(value, limit: int = 4000) -> str:
    out = str(value if value is not None else "").strip()[:limit]
    return "" if PLACEHOLDER.match(out) else out


def plain(value) -> str:
    return MARKS.sub("", value) if isinstance(value, str) else value


def sentences_once(value: str) -> str:
    seen, out = set(), []
    for sentence in re.split(r"(?<=[.!?])\s+", value):
        key = re.sub(r"\W+", " ", sentence.lower()).strip()
        if key and key in seen:
            continue
        seen.add(key)
        out.append(sentence)
    return " ".join(out)


LEADING_NUMBER = re.compile(r"^\s*(\d+[.)]|[-*•])\s+")


def item_text(value) -> str:
    if isinstance(value, dict):
        value = next((value[k] for k in ("text", "label", "title", "value", "item", "name") if value.get(k)), "")
    return LEADING_NUMBER.sub("", text(value, 600))


def items(value, limit: int = 40) -> list[str]:
    if isinstance(value, str):
        value = [v for v in re.split(r"\n+", value) if v.strip()]
    if not isinstance(value, list):
        return []
    out = []
    for v in value[:limit]:
        t = item_text(v)
        if t and t not in out:
            out.append(t)
    return out


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    raw = re.sub(r"[^\d,.\-]", "", str(value or ""))
    if not raw or raw in "-.,":
        return None
    raw = raw.replace(".", "").replace(",", ".") if raw.count(",") == 1 and raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def chart(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    cats = [text(c, 60) for c in (value.get("categories") or [])][:40]
    series = []
    for s in (value.get("series") or [])[:8]:
        if isinstance(s, dict):
            vals = [number(v) or 0 for v in (s.get("values") or [])][:len(cats) or 40]
            if vals:
                series.append({"name": text(s.get("name"), 60) or "Serie", "values": vals})
    if not series:
        return None
    if not cats:
        cats = [str(i + 1) for i in range(len(series[0]["values"]))]
    kind = text(value.get("chart") or value.get("kind"), 20).lower()
    return {"chart": kind if kind in CHARTS else "column", "title": text(value.get("title"), 120), "categories": cats,
            "series": [{**s, "values": (s["values"] + [0] * len(cats))[:len(cats)]} for s in series],
            "unit": text(value.get("unit"), 8)}


def table(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    cols = [text(c.get("title") if isinstance(c, dict) else c, 80) for c in (value.get("columns") or [])][:20]
    rows = [[r[i] if i < len(r) else "" for i in range(len(cols))] for r in (value.get("rows") or [])[:500]
            if isinstance(r, list) and any(str(c).strip() for c in r)] if cols else []
    rows = [[plain(c) for c in r] for r in rows]
    totals = bool(value.get("totals"))
    while rows and re.match(r"^\s*(totale|total|somma)\b", str(rows[-1][0]), re.I):
        rows.pop()
        totals = True
    if not cols or not rows:
        return None
    return {"columns": cols, "rows": rows, "caption": text(value.get("caption"), 200), "totals": totals}


def block(b: dict) -> dict | None:
    if not isinstance(b, dict):
        return None
    t = text(b.get("type"), 20).lower()
    if t == "heading":
        return {"type": t, "level": max(1, min(3, int(number(b.get("level")) or 1))), "text": text(b.get("text"), 200)}
    if t in ("paragraph", "quote"):
        body = sentences_once(text(b.get("text")))
        if t == "paragraph" and len(body) < 25 and not re.search(r"[.!?:]$", body):
            return None
        if t == "quote":
            body = body.strip("«»\"“”' ")
        return {"type": t, "text": body, "align": text(b.get("align"), 10), "author": text(b.get("author"), 80)}
    if t in ("bullets", "numbered"):
        return {"type": t, "items": items(b.get("items"))}
    if t == "table":
        return {"type": t, **(table(b) or {})} if table(b) else None
    if t == "chart":
        c = chart(b)
        return {"type": t, **c} if c else None
    if t == "kpi":
        kp = [{"label": text(i.get("label"), 60), "value": text(i.get("value"), 30),
               "delta": text(i.get("delta"), 20) if re.search(r"\d", str(i.get("delta") or "")) else ""}
              for i in (b.get("items") or [])[:6] if isinstance(i, dict) and text(i.get("value"))]
        return {"type": t, "items": kp} if kp else None
    if t == "callout":
        tone = text(b.get("tone"), 10).lower()
        return {"type": t, "tone": tone if tone in TONES else "info", "title": text(b.get("title"), 120), "text": text(b.get("text"))}
    if t == "link":
        return {"type": t, "text": text(b.get("text"), 200), "target": text(b.get("target"), 120)}
    if t == "pagebreak":
        return {"type": t}
    return None


def normalize(kind: str, raw: dict, request: str) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    doc = {"kind": kind, "title": text(raw.get("title"), 160) or text(request, 80), "subtitle": text(raw.get("subtitle"), 200),
           "author": text(raw.get("author"), 80) or "Jarvis", "theme": text(raw.get("theme"), 20),
           "palette": raw.get("palette") if isinstance(raw.get("palette"), list) else [], "font": text(raw.get("font"), 40)}
    if kind == "documento":
        blocks, seen = [], set()
        for x in (block(b) for b in (raw.get("blocks") or [])):
            if not x or not (x.get("text") or x.get("items") or x["type"] in ("table", "chart", "pagebreak", "kpi")):
                continue
            if x["type"] in ("paragraph", "bullets", "numbered", "callout", "quote"):
                sig = (x["type"], x.get("text") or tuple(x.get("items") or ()))
                if sig in seen:
                    continue
                seen.add(sig)
            blocks.append(x)
        doc["blocks"] = blocks
        if not doc["blocks"]:
            raise ValueError("documento vuoto")
    elif kind == "foglio":
        sheets = []
        for s in (raw.get("sheets") or [])[:12]:
            if not isinstance(s, dict):
                continue
            cols = [c if isinstance(c, dict) else {"title": c} for c in (s.get("columns") or [])][:30]
            cols = [{"title": text(c.get("title"), 60) or f"Colonna {i + 1}", "type": text(c.get("type"), 10).lower() or "text",
                     "width": number(c.get("width"))} for i, c in enumerate(cols)]
            rows = [r for r in (s.get("rows") or [])[:2000] if isinstance(r, list)]
            if cols and rows:
                sheets.append({"name": text(s.get("name"), 31) or f"Foglio{len(sheets) + 1}", "description": text(s.get("description"), 300),
                               "columns": cols, "rows": rows, "totals": bool(s.get("totals")),
                               "formulas": {text(k, 60): text(v, 200) for k, v in (s.get("formulas") or {}).items()} if isinstance(s.get("formulas"), dict) else {},
                               "chart": chart(s.get("chart")),
                               "links": [{"text": text(li.get("text"), 120), "target": text(li.get("target"), 120)}
                                         for li in (s.get("links") or []) if isinstance(li, dict)]})
        if not sheets:
            raise ValueError("foglio vuoto")
        doc["sheets"] = sheets
    else:
        slides = []
        for s in (raw.get("slides") or [])[:40]:
            if not isinstance(s, dict):
                continue
            layout = text(s.get("layout"), 20).lower() or "bullets"
            slides.append({"layout": layout, "title": text(s.get("title"), 160), "subtitle": text(s.get("subtitle"), 240),
                           "bullets": items(s.get("bullets"), 8), "left": items(s.get("left"), 8), "right": items(s.get("right"), 8),
                           "left_title": text(s.get("left_title"), 80), "right_title": text(s.get("right_title"), 80),
                           "table": table(s.get("table")), "chart": chart(s.get("chart")),
                           "items": [{"label": text(i.get("label"), 60), "value": text(i.get("value"), 30), "delta": text(i.get("delta"), 20)}
                                     for i in (s.get("items") or [])[:4] if isinstance(i, dict)],
                           "text": text(s.get("text"), 400), "author": text(s.get("author"), 80), "notes": text(s.get("notes"), 2000)})
        if not slides:
            raise ValueError("presentazione vuota")
        doc["slides"] = slides
    return doc


def runs(value: str) -> list[tuple[str, dict]]:
    out = []
    value = value or ""
    if value.count("**") % 2:
        value = value.replace("**", "")
    for part in INLINE.split(value):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            out.append((part[2:-2], {"bold": True}))
        elif part.startswith("`") and part.endswith("`"):
            out.append((part[1:-1], {"code": True}))
        elif part.startswith("[") and "](" in part:
            label, url = part[1:-1].split("](", 1)
            out.append((label, {"link": url}))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append((part[1:-1], {"italic": True}))
        else:
            out.append((part, {}))
    return out
