import unittest

from features.chat import intents, templates

FOCUS = {"mode": "focus", "panels": [{"type": "text", "title": "Risposta"}, {"type": "text", "title": "Output del comando"}]}
OTHER = {"mode": "focus", "panels": [{"type": "list", "title": "Punti chiave"}]}


class PredictTest(unittest.TestCase):
    def setUp(self):
        self.saved = templates.TEMPLATES_FILE.read_text(encoding="utf-8") if templates.TEMPLATES_FILE.exists() else None
        templates.TEMPLATES_FILE.unlink(missing_ok=True)

    def tearDown(self):
        if self.saved is None:
            templates.TEMPLATES_FILE.unlink(missing_ok=True)
        else:
            templates.TEMPLATES_FILE.write_text(self.saved, encoding="utf-8")

    def test_generic_question_never_opens_skeleton(self):
        for _ in range(5):
            templates.remember_template("conversation", FOCUS, 900)
        self.assertIsNone(intents.predict("perché il cielo è blu?")["skeleton"])

    def test_skeleton_only_when_stable(self):
        templates.remember_template("weather", FOCUS, 300)
        templates.remember_template("weather", FOCUS, 300)
        self.assertIsNone(templates.predictable("weather"))
        templates.remember_template("weather", FOCUS, 300)
        self.assertIsNotNone(templates.predictable("weather"))
        templates.remember_template("weather", OTHER, 300)
        self.assertIsNone(templates.predictable("weather"))


if __name__ == "__main__":
    unittest.main()
