import asyncio
import os
import time
import unittest
from datetime import date

from features.automations.bus import bus
from features.mind.mind import mind
from features.people import people
from features.vault import render
from features.vault.service import root, vault


class VaultTest(unittest.TestCase):
    def setUp(self):
        mind.memory.facts = []
        people.ensure("anna-rossi", "Anna Rossi")
        people.update("anna-rossi", {"first_name": "Anna", "last_name": "Rossi", "food_likes": ["pizza", "sushi"],
                                     "health_notes": "dato riservato"})
        mind.memory.add("Anna preferisce il caffè senza zucchero", "fatto", 0.8, who="anna-rossi")
        mind.memory.add("Il gatto si chiama Briciola", "fatto", 0.7, who="anna-rossi")
        mind.memory.add("Il wifi di casa si chiama Stark", "fatto", 0.6)

    def tearDown(self):
        people.delete("anna-rossi")

    def test_export_and_two_way_edit(self):
        vault.export()
        path = root() / "Persone" / "Anna Rossi.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("caffè senza zucchero", text)
        self.assertIn("pizza, sushi", text)
        self.assertNotIn("dato riservato", text)
        self.assertIn("Stark", (root() / "Memoria" / "Fatti generali.md").read_text(encoding="utf-8"))
        edited = text.replace("- Il gatto si chiama Briciola\n", "").rstrip("\n") + "\n- Anna è allergica alle noci\n"
        path.write_text(edited, encoding="utf-8")
        future = time.time() + 5
        os.utime(path, (future, future))
        changes = vault.import_edits()
        self.assertTrue(changes)
        texts = [f["text"] for f in mind.memory.facts if f.get("who") == "anna-rossi"]
        self.assertIn("Anna è allergica alle noci", texts)
        self.assertNotIn("Il gatto si chiama Briciola", texts)
        self.assertIn("Anna preferisce il caffè senza zucchero", texts)
        self.assertEqual(vault.import_edits(), [])

    def test_parse_facts(self):
        md = render.person({"display_name": "X"}, [], [{"text": "uno", "score": 1}], "")
        self.assertEqual(render.parse_facts(md + "\n## Altro\n- non conta\n"), ["uno"])
        self.assertIsNone(render.parse_facts("# senza sezione"))

    def test_diary(self):
        bus.emit("voice_command", {"text": "accendi la luce del salotto"})
        path = asyncio.run(vault.write_diary(date.today(), False))
        text = path.read_text(encoding="utf-8")
        self.assertIn("accendi la luce del salotto", text)
        self.assertIn("Giornata in corso", text)
        from features.vault import commands
        reply, _ = asyncio.run(commands.answer("cosa è successo oggi?"))
        self.assertTrue(reply.startswith("Oggi:"))


if __name__ == "__main__":
    unittest.main()
