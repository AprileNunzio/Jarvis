import unittest

from features.laws import laws as module
from features.laws.defaults import SEED_VERSION, behaviour


class LawsSeedTest(unittest.TestCase):
    def setUp(self):
        self.saved_rules = module.RULES_FILE.read_text(encoding="utf-8") if module.RULES_FILE.exists() else None
        self.saved_seed = module.SEEDED_FILE.read_text(encoding="utf-8") if module.SEEDED_FILE.exists() else None
        module.RULES_FILE.unlink(missing_ok=True)
        module.SEEDED_FILE.unlink(missing_ok=True)

    def tearDown(self):
        for path, text in ((module.RULES_FILE, self.saved_rules), (module.SEEDED_FILE, self.saved_seed)):
            if text is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(text, encoding="utf-8")

    def test_seeded_once_and_editable(self):
        first = module.Laws()
        self.assertEqual(len(first.rules), len(behaviour()))
        self.assertTrue(all(r["origin"] == SEED_VERSION for r in first.rules))
        first.delete(first.rules[0]["id"])
        first.update(first.rules[0]["id"], "Regola cambiata dall'utente")
        second = module.Laws()
        self.assertEqual(len(second.rules), len(behaviour()) - 1)
        self.assertEqual(second.rules[0]["text"], "Regola cambiata dall'utente")
        self.assertIn("Regola cambiata dall'utente", second.preamble())


if __name__ == "__main__":
    unittest.main()
