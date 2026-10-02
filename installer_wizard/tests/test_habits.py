import random
import time
import unittest
from datetime import datetime, timedelta

from features.automations import sun
from features.automations.schema import validate
from features.habits.miner import mine

START = datetime(2026, 9, 1)


def row(dt: datetime, entity: str, state: str, kind: str = "action", sun_up: int = 0) -> tuple:
    return (dt.timestamp(), entity, state, dt.weekday(), dt.hour * 60 + dt.minute, 1, sun_up, kind)


def history(days: int = 14) -> list[tuple]:
    rnd = random.Random(7)
    rows = []
    for d in range(days):
        day = START + timedelta(days=d)
        rows.append(row(day.replace(hour=8, minute=0), "sensor.ignored", "x", "noise"))
        if day.weekday() < 5:
            rows.append(row(day.replace(hour=23, minute=5) + timedelta(minutes=rnd.randint(0, 12)), "light.soggiorno", "off"))
        sunset = sun.times(day.date())["sunset"].replace(tzinfo=None)
        rows.append(row(sunset + timedelta(minutes=15 + rnd.randint(-3, 3)), "cover.salotto", "closed"))
        if d % 2 == 0:
            arrive = day.replace(hour=19, minute=30) + timedelta(minutes=rnd.randint(0, 60))
            rows.append(row(arrive, "presence", "arrived", "arrival"))
            rows.append(row(arrive + timedelta(seconds=40), "light.ingresso", "on"))
        rows.append(row(day.replace(hour=rnd.randint(9, 20), minute=rnd.randint(0, 59)), "light.cucina", "on", sun_up=1))
    return sorted(rows)


class MinerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sun.set_place(41.9, 12.5)
        now = (START + timedelta(days=14)).timestamp()
        cls.found = {(s["entity"], s["kind"]): s for s in mine(history(), {"light.soggiorno": "Luce soggiorno"}, 0.7, now)}

    def test_weekday_time_habit(self):
        s = self.found[("light.soggiorno", "time")]
        trig = s["automation"]["triggers"][0]
        self.assertEqual(trig["days"], [0, 1, 2, 3, 4])
        self.assertIn(trig["at"], ("23:05", "23:10", "23:15"))
        self.assertIn("nei giorni feriali", s["text"])
        self.assertIn("Luce soggiorno", s["text"])
        self.assertEqual(s["automation"]["actions"][0]["service"], "light.turn_off")

    def test_sunset_habit(self):
        s = self.found[("cover.salotto", "sun")]
        trig = s["automation"]["triggers"][0]
        self.assertEqual(trig["event"], "sunset")
        self.assertIn(trig["offset"], (10, 15, 20))
        self.assertEqual(s["automation"]["actions"][0]["service"], "cover.close_cover")

    def test_arrival_habit_in_the_dark(self):
        s = self.found[("light.ingresso", "arrival")]
        self.assertEqual(s["automation"]["triggers"][0]["type"], "presence")
        self.assertIn({"type": "sun", "when": "night"}, s["automation"]["conditions"])

    def test_random_use_is_not_a_habit(self):
        self.assertFalse(any(e == "light.cucina" for e, _ in self.found))
        self.assertFalse(any(e == "sensor.ignored" for e, _ in self.found))

    def test_proposals_are_valid_automations(self):
        for s in self.found.values():
            with self.subTest(s=s["text"]):
                self.assertEqual(validate(s["automation"])[1], [])

    def test_too_little_data(self):
        now = (START + timedelta(days=3)).timestamp()
        self.assertEqual(mine(history(3), {}, 0.7, now), [])


class ServiceTest(unittest.TestCase):
    def test_own_actions_are_ignored_and_accept_creates_automation(self):
        from features.automations.bus import bus
        from features.automations.library import library
        from features.habits.service import habits
        before = habits.journal.count()
        bus.state_changed("light.prova", {"state": "off"}, {"state": "on"})
        self.assertEqual(habits.journal.count(), before + 1)
        habits.mark_commanded(["light.prova"])
        bus.state_changed("light.prova", {"state": "on"}, {"state": "off"})
        self.assertEqual(habits.journal.count(), before + 1)
        s = mine(history(), {}, 0.7, (START + timedelta(days=14)).timestamp())[0]
        habits.data["suggestions"][s["id"]] = {**s, "status": "new", "created": time.time()}
        message = habits.decide(s["id"], "accept")
        self.assertIn("ci penso io", message)
        aid = habits.data["suggestions"][s["id"]]["automation"]
        self.assertTrue(library.items[aid]["enabled"])
        library.remove(aid)


if __name__ == "__main__":
    unittest.main()
