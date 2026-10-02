import unittest

from features.models3d import commands


def subject(text: str) -> str | None:
    m = commands.CREATE_MODEL.search(text) or commands.CREATE.search(text)
    return m.group("what").strip(" ?.!") if m else None


class Create3dTest(unittest.TestCase):
    def test_all_phrasings_create(self):
        cases = {
            "mi crei un martello 3d?": "martello",
            "creami un martello in 3D": "martello",
            "puoi crearmi una tazza 3d": "tazza",
            "mi faresti una sedia in 3d": "sedia",
            "fammi un cacciavite in tre dimensioni": "cacciavite",
            "disegnami una chiave inglese 3d": "chiave inglese",
            "mi progetti un vaso tridimensionale": "vaso",
            "realizza per favore un cubo in 3d": "cubo",
            "crea un modello 3d di una lampada": "lampada",
        }
        for text, want in cases.items():
            self.assertEqual(subject(text), want, text)

    def test_past_or_unrelated_do_not_create(self):
        for text in ["ho creato un cubo in 3d ieri", "che tempo fa domani", "creami un file di testo",
                     "il martello che hai disegnato in 3d"]:
            self.assertIsNone(subject(text), text)


if __name__ == "__main__":
    unittest.main()
