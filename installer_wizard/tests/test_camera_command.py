import unittest

from features.chat.intents import detect_intent
from features.chat.skills.camera import camera_skill, wants_camera_off


class CameraIntentTest(unittest.TestCase):
    def test_enabling_phrases_are_recognised(self):
        for text in ("Jarvis abilita la webcam", "apri la webcam a tutto schermo", "accendi la fotocamera", "mostrami la webcam",
                     "attiva la web cam per favore", "fammi vedere la webcam"):
            with self.subTest(text=text):
                self.assertEqual(detect_intent(text), "camera")

    def test_closing_phrases_are_recognised(self):
        for text in ("chiudi la webcam", "disattiva la web cam", "spegni la fotocamera", "nascondi la webcam"):
            with self.subTest(text=text):
                self.assertEqual(detect_intent(text), "camera")
                self.assertTrue(wants_camera_off(text))

    def test_other_requests_are_left_alone(self):
        for text in ("fammi vedere la telecamera del giardino", "cosa vedi", "come funziona una webcam", "metti la musica",
                     "abilita il microfono", "scrivi un programma per la webcam"):
            with self.subTest(text=text):
                self.assertNotEqual(detect_intent(text), "camera")

    def test_the_answer_tells_the_display_what_to_do(self):
        speech, ui = camera_skill("abilita la webcam")
        self.assertEqual((ui["camera"], ui["mode"]), ("on", "face"))
        self.assertIn("Webcam attiva", speech)
        speech, ui = camera_skill("chiudi la webcam")
        self.assertEqual(ui, {"mode": "face", "camera": "off"})


if __name__ == "__main__":
    unittest.main()
