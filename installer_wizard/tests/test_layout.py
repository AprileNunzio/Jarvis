import unittest

from features.chat import code, layout

EXPLAIN = ("Una pagina HTML ha una testa con le informazioni per il browser e un corpo con ciò che si vede. "
           "Il tag meta charset dichiara la codifica dei caratteri, title dà il nome alla scheda. "
           "Nel corpo h1 è il titolo principale e p un paragrafo; il browser li dispone dall'alto in basso. "
           "Per aggiungere stile si usa un foglio CSS collegato nella testa.")
PAGE = "<!DOCTYPE html>\n<html>\n<head>\n  <meta charset=\"utf-8\">\n  <title>Prova</title>\n</head>\n<body>\n  <h1>Ciao</h1>\n</body>\n</html>"


class LayoutTest(unittest.TestCase):
    def test_short_code_stays_in_widget(self):
        speech, ui = code.answer("Ecco la pagina, signore.\n```html\n" + PAGE + "\n```", "dammi il codice html")
        self.assertEqual(ui.pop("intent"), "code_view")
        self.assertEqual(ui["mode"], "face")
        self.assertEqual(layout.presence(speech, ui), "small")

    def test_explanation_and_code_side_by_side(self):
        speech, ui = code.answer(EXPLAIN + "\n```html\n" + PAGE + "\n```", "spiegami come si scrive una pagina html")
        self.assertEqual(ui.pop("intent"), "code_focus")
        self.assertEqual(ui["mode"], "focus")
        types = [p["type"] for p in ui["panels"]]
        self.assertEqual(types, ["text", "code"])
        self.assertEqual(sum(p["span"] for p in ui["panels"]), 12)
        self.assertLess(len(speech), 330)
        self.assertNotIn("<html>", speech)

    def test_code_first_when_asked_for_code(self):
        _, ui = code.answer(EXPLAIN + "\n```html\n" + PAGE + "\n```", "scrivimi una pagina html")
        self.assertEqual(ui["panels"][0]["type"], "code")

    def test_two_blocks_each_half(self):
        _, ui = code.answer(EXPLAIN + "\n```html\n" + PAGE + "\n```\n```css\nh1 { color: red; }\n```", "dammi html e css")
        codes = [p for p in ui["panels"] if p["type"] == "code"]
        self.assertEqual([p["span"] for p in codes], [6, 6])

    def test_presence_by_answer_size(self):
        self.assertEqual(layout.presence("Sono le 10 e 2, signore.", {"mode": "face"}), "large")
        self.assertEqual(layout.presence(" ".join(["parola"] * 40), {"mode": "face"}), "normal")
        speech, ui = layout.plan_text("Ecco.\n- il primo punto con molti dettagli\n- il secondo punto con altri dettagli\n"
                                      "- il terzo punto conclusivo", "elenca tre cose")
        self.assertEqual(ui["mode"], "focus")
        self.assertEqual([p["span"] for p in ui["panels"]], [5, 7])


if __name__ == "__main__":
    unittest.main()
