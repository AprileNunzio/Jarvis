import asyncio
import re
import unittest

from features.actions.smb import smb_action
from features.agent import registry
from features.automations import tools as automation_tools
from features.chat import code
from features.shares import archive

TODAY = re.compile(r"^\d{8}_")


class ArchiveTest(unittest.TestCase):
    def test_dated_names(self):
        self.assertTrue(TODAY.match(archive.dated("Lista della spesa.txt")))
        self.assertTrue(archive.dated("Lista della spesa.txt").endswith("_Lista-della-spesa.txt"))
        self.assertEqual(archive.dated("20250101_vecchio.docx"), "20250101_vecchio.docx")
        self.assertNotIn(":", archive.dated("perché: è così?.md"))

    def test_unique_and_folders(self):
        archive.ensure()
        self.assertTrue((archive.ROOT / "LEGGIMI.txt").exists())
        self.assertEqual([f["name"] for f in archive.overview()], list(archive.FOLDERS.values()))
        first = archive.new_path("documenti", "prova.txt")
        first.write_text("uno", encoding="utf-8")
        second = archive.new_path("documenti", "prova.txt")
        self.assertNotEqual(first, second)
        self.assertTrue(second.name.endswith("_prova_2.txt"))
        first.unlink()

    def test_shared_folder_goes_inside_archive(self):
        _, ui = asyncio.run(smb_action("crea una cartella condivisa chiamata progetti"))
        target = archive.path("scambio") / "progetti"
        self.assertTrue(target.is_dir())
        self.assertIn("\\condivisa\\06 Scambio\\progetti", ui["panels"][0]["data"]["Windows"])
        target.rmdir()

    def test_code_is_saved(self):
        _, ui = code.answer("Ecco.\n```html\n<p>ciao</p>\n```", "scrivimi un paragrafo html")
        self.assertTrue(ui["files"][0].endswith(".html"))
        saved = archive.path("codice") / ui["files"][0]
        self.assertTrue(saved.exists())
        saved.unlink()

    def test_agent_cannot_invent_automations(self):
        token = registry.REQUEST.set("creami una cartella condivisa con dentro un sito web")
        try:
            with self.assertRaises(ValueError):
                asyncio.run(automation_tools.create_automation("crea la cartella e il sito"))
        finally:
            registry.REQUEST.reset(token)
        token = registry.REQUEST.set("ogni mattina alle 8 accendi la luce")
        try:
            self.assertTrue(registry.asked_for_recurring())
        finally:
            registry.REQUEST.reset(token)


if __name__ == "__main__":
    unittest.main()
