import asyncio
import unittest
from datetime import datetime
from unittest import mock

from features.sounds import commands, policy as policy_module
from features.sounds.policy import policy


def env(values: dict):
    return mock.patch.object(policy_module, "env_get", lambda k, d="": values.get(k, d))


class QuietHoursTest(unittest.TestCase):
    def setUp(self):
        policy.manual = {}

    def test_overnight_window(self):
        with env({"JARVIS_QUIET_START": "23:00", "JARVIS_QUIET_END": "07:00"}):
            self.assertTrue(policy.scheduled(datetime(2026, 10, 1, 23, 30)))
            self.assertTrue(policy.scheduled(datetime(2026, 10, 2, 6, 59)))
            self.assertFalse(policy.scheduled(datetime(2026, 10, 2, 7, 0)))
            self.assertFalse(policy.scheduled(datetime(2026, 10, 1, 22, 59)))

    def test_day_window_and_off(self):
        with env({"JARVIS_QUIET_START": "13:00", "JARVIS_QUIET_END": "15:00"}):
            self.assertTrue(policy.scheduled(datetime(2026, 10, 1, 14, 0)))
            self.assertFalse(policy.scheduled(datetime(2026, 10, 1, 16, 0)))
        with env({"JARVIS_QUIET_MODE": "off"}):
            self.assertFalse(policy.scheduled(datetime(2026, 10, 1, 23, 30)))

    def test_weekend_nights(self):
        with env({"JARVIS_QUIET_DAYS": "weekend"}):
            self.assertTrue(policy.scheduled(datetime(2026, 10, 3, 1, 0)))
            self.assertFalse(policy.scheduled(datetime(2026, 10, 1, 23, 30)))

    def test_dnd_and_urgent(self):
        with env({"JARVIS_QUIET_MODE": "off"}):
            policy.set_dnd(30)
            self.assertTrue(policy.quiet())
            self.assertIn("silenzio", policy.play("notify"))
            self.assertIn("riprodotto", policy.play("alert"))
            policy.clear_dnd()
            self.assertFalse(policy.quiet())
            self.assertIn("riprodotto", policy.play("notify"))
        with self.assertRaises(ValueError):
            policy.play("inesistente")

    def test_voice_commands(self):
        with env({"JARVIS_QUIET_MODE": "off"}):
            reply, _ = asyncio.run(commands.answer("non disturbare per un'ora"))
            self.assertIn("Non disturbare attivo fino", reply)
            self.assertAlmostEqual(policy.dnd()["until"] - policy.dnd()["since"], 3600, delta=5)
            reply, _ = asyncio.run(commands.answer("riattiva i suoni"))
            self.assertIn("riattivati", reply)
            with self.assertRaises(LookupError):
                asyncio.run(commands.answer("che tempo fa domani"))


if __name__ == "__main__":
    unittest.main()
