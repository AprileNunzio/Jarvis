import html
import json
import re
import time

from state import store

from features.actions.common import SITES_DIR, llm, my_ip, slug

_SITE_CSS = """*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
color:#1d1d1f;background:#fafaf7;line-height:1.6}header{background:linear-gradient(135deg,var(--c1),var(--c2));
color:#fff;padding:72px 20px 56px;text-align:center}header h1{margin:0;font-size:clamp(2rem,6vw,3.4rem)}
header p{margin:.6rem auto 0;max-width:640px;font-size:1.15rem;opacity:.92}nav{position:sticky;top:0;
background:#fff;border-bottom:1px solid #e6e3da;display:flex;justify-content:center;gap:4px;flex-wrap:wrap;z-index:2}
nav a{padding:14px 16px;color:#333;text-decoration:none;font-weight:600}nav a:hover{color:var(--c1)}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}section{padding:32px 0;border-bottom:1px solid #ece9df}
h2{color:var(--c1);font-size:1.7rem;margin:0 0 16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,
minmax(230px,1fr));gap:16px}.card{background:#fff;border:1px solid #ebe7dc;border-radius:14px;padding:18px;
box-shadow:0 1px 3px rgba(0,0,0,.04)}.card h3{margin:0 0 6px;display:flex;justify-content:space-between;gap:8px;
font-size:1.08rem}.price{color:var(--c1);white-space:nowrap}.card p{margin:0;color:#555}.contact{display:grid;
gap:8px;font-size:1.05rem}footer{text-align:center;color:#888;padding:28px;font-size:.9rem}"""


def _card(item: dict, e) -> str:
    price = item.get("price")
    tag = f'<span class="price">{e(price)}</span>' if price else ""
    return (
        f'<div class="card"><h3><span>{e(item.get("name"))}</span>{tag}</h3>'
        f"<p>{e(item.get('description'))}</p></div>"
    )


def render_site(spec: dict) -> str:
    e = lambda s: html.escape(str(s or ""))
    c1, c2 = spec.get("color") or "#b3261e", spec.get("color2") or "#e8871e"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(c1)):
        c1 = "#b3261e"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(c2)):
        c2 = "#e8871e"
    sections, nav = [], []
    for i, s in enumerate(spec.get("sections") or []):
        sid = f"s{i}"
        nav.append(f'<a href="#{sid}">{e(s.get("title"))}</a>')
        body = f"<p>{e(s.get('text'))}</p>" if s.get("text") else ""
        items = s.get("items") or []
        if items:
            body += (
                '<div class="grid">'
                + "".join(_card(it, e) for it in items if isinstance(it, dict))
                + "</div>"
            )
        sections.append(f'<section id="{sid}"><h2>{e(s.get("title"))}</h2>{body}</section>')
    contacts = spec.get("contacts") or {}
    if contacts:
        nav.append('<a href="#contatti">Contatti</a>')
        rows = "".join(f"<div><b>{e(k)}:</b> {e(v)}</div>" for k, v in contacts.items() if v)
        sections.append(f'<section id="contatti"><h2>Contatti</h2><div class="contact">{rows}</div></section>')
    return (
        f'<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>{e(spec.get("title"))}</title>'
        f'<meta name="description" content="{e(spec.get("tagline"))}"><style>:root{{--c1:{c1};--c2:{c2}}}'
        f"{_SITE_CSS}</style></head><body><header><h1>{e(spec.get('title'))}</h1><p>{e(spec.get('tagline'))}</p>"
        f"</header><nav>{''.join(nav)}</nav><main>{''.join(sections)}</main><footer>© {time.strftime('%Y')} "
        f"{e(spec.get('title'))} · creato da Jarvis</footer></body></html>"
    )


async def site_action(text: str) -> tuple[str, dict]:
    spec = await llm(
        "Progetta il contenuto di un sito web per questa richiesta. Inventa contenuti realistici, specifici e "
        "coerenti con l'attività (es. una pizzeria ha pizze con ingredienti veri e prezzi in euro). "
        "Rispondi SOLO con JSON:\n"
        '{"title": "nome", "tagline": "slogan di una frase", "color": "#rrggbb", "color2": "#rrggbb", '
        '"sections": [{"title": "Chi siamo", "text": "2-3 frasi"}, {"title": "Menu", "items": [{"name": "...", '
        '"description": "...", "price": "€ 7,50"}]}], "contacts": {"Indirizzo": "...", "Telefono": "...", '
        '"Email": "...", "Orari": "..."}}\n'
        "Includi tutte le sezioni che l'utente chiede (almeno 6 voci nelle liste).\n\nRichiesta: " + text,
        as_json=True,
        max_tokens=1400,
        temperature=0.4,
    )
    if not spec.get("title") or not spec.get("sections"):
        raise LookupError("contenuto del sito non generato")
    name = slug(str(spec["title"]), "sito")
    folder = SITES_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(render_site(spec), encoding="utf-8")
    (folder / "sito.json").write_text(
        json.dumps({**spec, "request": text, "created_at": time.time()}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    url = f"http://{my_ip()}/siti/{name}/"
    store.event("INFO", f"Sito creato: {url}", "actions")
    n = sum(len(s.get("items") or []) for s in spec["sections"])
    speech = (
        f"Ho creato il sito di {spec['title']} con {len(spec['sections'])} sezioni"
        + (f", {n} voci" if n else "")
        + (" e i contatti" if spec.get("contacts") else "")
        + f". È già online sulla rete di casa all'indirizzo {url}"
    )
    return speech, {
        "mode": "focus",
        "title": f"Sito: {spec['title']}",
        "subtitle": url,
        "panels": [
            {
                "type": "kv",
                "title": "Pubblicato",
                "data": {
                    "Indirizzo": url,
                    "Cartella": str(folder),
                    "Sezioni": ", ".join(s.get("title", "") for s in spec["sections"]),
                },
            }
        ],
    }
