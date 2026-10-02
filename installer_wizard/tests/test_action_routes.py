import unittest

from features.actions import router


def route(text: str) -> str | None:
    found = router.match(text)
    return found[0] if found else None


class ActionRoutesTest(unittest.TestCase):
    def test_site_phrasings(self):
        for text in ["mi crei un sito web?", "creami un sito web per una pizzeria", "puoi farmi un sito internet",
                     "mi faresti una pagina web per il mio negozio", "realizza una landing page per un dentista",
                     "pubblica un sito per la palestra"]:
            self.assertEqual(route(text), "site", text)

    def test_not_sites(self):
        for text in ["il sito che hai creato ieri non si apre?", "che tempo fa", "apri il sito del comune"]:
            self.assertNotEqual(route(text), "site", text)

    def test_sites_list(self):
        for text in ["dove vedo il sito che hai creato?", "quali siti hai creato?", "mostrami i miei siti"]:
            self.assertEqual(route(text), "sites_list", text)

    def test_file_phrasings(self):
        for text in ["mi crei un file di testo con la lista della spesa", "scrivimi un file con gli appunti"]:
            self.assertEqual(route(text), "file", text)


if __name__ == "__main__":
    unittest.main()
