import asyncio
import unittest

from features.chat import assistant, code
from features.desktop.desk import desk

FENCED = "Ecco una pagina minima, signore.\n```html\n<!DOCTYPE html>\n<html>\n<body><h1>Ciao</h1></body>\n</html>\n```"
BARE = "Ecco il codice: <!DOCTYPE html><html><head><title>Prova</title></head><body><p>Ciao</p></body></html>"


class CodeViewTest(unittest.TestCase):
    def test_extract_fenced_and_bare(self):
        prose, blocks = code.extract(FENCED, "dammi il codice html")
        self.assertEqual(blocks[0]["language"], "html")
        self.assertIn("<h1>Ciao</h1>", blocks[0]["content"])
        self.assertNotIn("<html>", prose)
        prose, blocks = code.extract(BARE, "scrivimi una pagina html")
        self.assertEqual(blocks[0]["language"], "html")
        self.assertNotIn("<body>", prose)
        self.assertEqual(code.extract("Il tag <b> serve per il grassetto.", "che ore sono")[1], [])

    def test_reply_opens_widget_without_reading_code(self):
        async def core_call(_):
            return {"speech_output": FENCED, "agent_id": "test"}

        desk.scan()
        result = asyncio.run(assistant.handle("scrivimi il codice html di una pagina che dice ciao", core_call))
        self.assertEqual(result["intent"], "code_view")
        self.assertNotIn("<", result["reply"])
        desk.on_intent(result["intent"], result["ui"])
        shown = [i for i in desk.instances.values() if i["id"] == "code_view"]
        self.assertTrue(shown)
        self.assertIn("<h1>Ciao</h1>", shown[0]["data"]["content"])


if __name__ == "__main__":
    unittest.main()
