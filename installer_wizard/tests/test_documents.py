import asyncio
import unittest
import zipfile

from features.documents import builder, convert, jobs, spec
from features.shares import archive

CHART = {"chart": "column", "title": "Ricavi per trimestre", "categories": ["T1", "T2", "T3", "T4"],
         "series": [{"name": "2026", "values": [120, 135, 150, 170]}, {"name": "2025", "values": [100, 110, 125, 140]}], "unit": "k€"}
DOCUMENT = {"title": "Relazione trimestrale", "subtitle": "Andamento e prospettive", "theme": "aziendale", "blocks": [
    {"type": "heading", "level": 1, "text": "Sintesi"},
    {"type": "paragraph", "text": "Il trimestre chiude con **ricavi in crescita** del *12%* e un margine stabile. Vedi [sito](https://example.com)."},
    {"type": "kpi", "items": [{"label": "Ricavi", "value": "170 k€", "delta": "+12%"}, {"label": "Costi", "value": "120 k€", "delta": "-3%"}]},
    {"type": "bullets", "items": ["Nuovi clienti: 14", "Abbandoni: 2"]},
    {"type": "table", "columns": ["Voce", "Importo"], "rows": [["Vendite", 150000], ["Servizi", "20.000,50"]], "totals": True, "caption": "Ricavi"},
    {"type": "chart", **CHART}, {"type": "pie", "text": "ignorato"},
    {"type": "callout", "tone": "warning", "title": "Attenzione", "text": "I costi energetici restano elevati."},
    {"type": "quote", "text": "La qualità non è un atto, è un'abitudine.", "author": "Aristotele"},
    {"type": "link", "text": "Apri il budget", "target": "budget"}]}
SHEET = {"title": "Budget 2027", "theme": "moderno", "sheets": [{"name": "Budget", "description": "Spese previste",
         "columns": [{"title": "Voce", "type": "text"}, {"title": "Quantità", "type": "integer"},
                     {"title": "Prezzo", "type": "currency"}, {"title": "Sconto", "type": "percent"}],
         "rows": [["Licenze", 10, "49,90", 10], ["Hardware", 3, 1200, 5], ["Consulenza", 20, 80, 0]],
         "formulas": {"Totale": "=B{r}*C{r}*(1-D{r})"}, "totals": True, "chart": CHART,
         "links": [{"text": "Relazione", "target": "relazione"}]}]}
DECK = {"title": "Piano commerciale", "subtitle": "Strategia 2027", "theme": "tech", "slides": [
    {"layout": "title", "title": "Piano commerciale", "subtitle": "Strategia 2027"},
    {"layout": "section", "title": "Mercato"},
    {"layout": "bullets", "title": "Obiettivi", "bullets": ["Crescere del **20%**", "Aprire 2 sedi"], "notes": "Sottolineare i tempi"},
    {"layout": "two_columns", "title": "Punti di forza", "left_title": "Oggi", "right_title": "Domani", "left": ["A"], "right": ["B"]},
    {"layout": "table", "title": "Listino", "table": {"columns": ["Prodotto", "Prezzo"], "rows": [["Base", 10], ["Pro", 25]]}},
    {"layout": "chart", "title": "Ricavi", "chart": {**CHART, "chart": "line"}},
    {"layout": "chart", "title": "Quote", "chart": {**CHART, "chart": "doughnut"}},
    {"layout": "kpi", "title": "Numeri", "items": [{"label": "Clienti", "value": "1.240", "delta": "+8%"}]},
    {"layout": "quote", "text": "Semplice è meglio.", "author": "Team"},
    {"layout": "closing", "title": "Grazie", "subtitle": "info@example.com"}]}


def run(coro):
    return asyncio.run(coro)


class DocumentsTest(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(builder.formats("creami una presentazione powerpoint"), ["pptx"])
        self.assertEqual(builder.formats("un foglio excel con il budget"), ["xlsx"])
        self.assertEqual(builder.formats("una relazione in pdf"), ["pdf"])
        self.assertEqual(builder.formats("un documento libreoffice per la riunione"), ["odt"])
        self.assertIn("docx", builder.formats("una lettera in word e in pdf"))
        self.assertTrue(jobs.wants_project("prepara un progetto per il lancio del prodotto"))
        self.assertTrue(jobs.wants_project("fammi una presentazione e un foglio excel per il budget"))

    def test_render_office_formats(self):
        folder = archive.folder("documenti")
        made = []
        for kind, raw, fmt in (("documento", DOCUMENT, "docx"), ("foglio", SHEET, "xlsx"), ("presentazione", DECK, "pptx")):
            doc = spec.normalize(kind, raw, raw["title"])
            target = archive.unique(folder, archive.dated(f"test-{kind}.{fmt}"))
            run(builder.render(doc, fmt, target, {"budget": "../budget.xlsx", "relazione": "relazione.docx"}))
            self.assertTrue(zipfile.is_zipfile(target))
            made.append(target)
        with zipfile.ZipFile(made[0]) as z:
            xml = z.read("word/document.xml").decode()
            self.assertIn("Relazione trimestrale", xml)
            self.assertTrue(any(n.startswith("word/media/") for n in z.namelist()))
        with zipfile.ZipFile(made[1]) as z:
            self.assertTrue(any("charts/chart" in n for n in z.namelist()))
            self.assertIn("SUM(", z.read("xl/worksheets/sheet1.xml").decode())
        with zipfile.ZipFile(made[2]) as z:
            self.assertEqual(sum(1 for n in z.namelist() if n.startswith("ppt/slides/slide")), 10)
        for path in made:
            path.unlink()

    @unittest.skipUnless(convert.office(), "LibreOffice non installato")
    def test_libreoffice_formats(self):
        folder = archive.folder("documenti")
        for kind, raw, fmt in (("documento", DOCUMENT, "odt"), ("documento", DOCUMENT, "pdf"),
                               ("foglio", SHEET, "ods"), ("presentazione", DECK, "odp")):
            doc = spec.normalize(kind, raw, raw["title"])
            target = archive.unique(folder, archive.dated(f"test-{kind}.{fmt}"))
            run(builder.render(doc, fmt, target))
            self.assertGreater(target.stat().st_size, 2000, fmt)
            target.unlink()

    @unittest.skipUnless(convert.office(), "LibreOffice non installato")
    def test_conversion_recipes_are_learned_and_reused(self):
        from features.documents import recipes, word
        recipes.FILE.unlink(missing_ok=True)
        folder = archive.folder("documenti")
        source = folder / "ricetta-prova.docx"
        word.write(spec.normalize("documento", DOCUMENT, "prova"), source)
        out, how = run(recipes.transform(source, "pdf", folder))
        self.assertEqual(how, "appresa ora")
        self.assertTrue(recipes.valid(out, "pdf"))
        out.unlink()
        out, how = run(recipes.transform(source, "pdf", folder))
        self.assertEqual(how, "dalla memoria")
        self.assertEqual(recipes.load()["docx>pdf"]["uses"], 2)
        out.unlink()
        data = recipes.load()
        data["docx>pdf"]["route"] = [{"to": "pdf", "filter": "pdf:filtro_inesistente"}]
        recipes.save(data)
        out, how = run(recipes.transform(source, "pdf", folder))
        self.assertEqual(how, "appresa ora")
        self.assertNotEqual(recipes.load()["docx>pdf"]["route"][0]["filter"], "pdf:filtro_inesistente")
        out.unlink()
        source.unlink()

    def test_project_with_links(self):
        from features.brain import llm

        async def fake(prompt, **_):
            if prompt.startswith(jobs.PLAN[:40]):
                return {"project": "Lancio prodotto", "description": "Kit completo per il lancio.", "theme": "vivace",
                        "folders": ["01 Analisi", "02 Finanza"],
                        "documents": [{"key": "relazione", "title": "Analisi di mercato", "folder": "01 Analisi", "format": "docx",
                                       "brief": "mercato", "links": ["budget"]},
                                      {"key": "budget", "title": "Budget", "folder": "02 Finanza", "format": "xlsx",
                                       "brief": "costi", "links": ["relazione"]},
                                      {"key": "pitch", "title": "Presentazione", "format": "pptx", "brief": "sintesi"}]}
            if "foglio di calcolo" in prompt:
                return SHEET
            if "presentazione moderna" in prompt:
                return DECK
            return DOCUMENT

        original = llm.generate
        llm.generate = fake
        try:
            entry = run(jobs.project("prepara un progetto per il lancio del prodotto"))
        finally:
            llm.generate = original
        root = archive.ROOT / entry["project"]
        self.assertTrue((root / "01-Analisi").is_dir() and (root / "02-Finanza").is_dir())
        self.assertEqual(len(entry["files"]), 4)
        self.assertEqual(entry.get("errors"), [])
        index = archive.ROOT / entry["files"][0]
        with zipfile.ZipFile(index) as z:
            rels = z.read("word/_rels/document.xml.rels").decode()
        self.assertIn("02-Finanza/", rels)
        with zipfile.ZipFile(archive.ROOT / entry["files"][1]) as z:
            self.assertIn("../02-Finanza/", z.read("word/_rels/document.xml.rels").decode())


if __name__ == "__main__":
    unittest.main()
