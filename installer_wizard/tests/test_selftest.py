import asyncio
import unittest
from datetime import datetime
from unittest import mock

from features.selftest.service import SelfTest


def report(rev: str, **statuses) -> dict:
    results = [{"key": k, "label": k, "critical": k.startswith("c"), "status": s, "detail": "", "ms": 1}
               for k, s in statuses.items()]
    return {"at": 0, "reason": "", "rev": rev, "results": results, "passed": 0, "failed": 0, "skipped": 0}


class SelfTestDecisionTest(unittest.TestCase):
    def setUp(self):
        self.st = SelfTest()
        self.st.data = {"history": [], "tested_rev": "", "good_rev": "aaa", "night": ""}
        self.told: list[str] = []

        async def tell(text):
            self.told.append(text)
        self.st._tell = tell

    def react(self, now: dict, before: dict | None, reason: str, rollback_result: bool = True):
        calls = []

        async def rollback(rep, critical):
            calls.append([r["key"] for r in critical])
            return rollback_result
        self.st._rollback = rollback
        asyncio.run(self.st._react(now, before, reason))
        return calls

    def test_rollback_only_when_critical_breaks_after_update(self):
        calls = self.react(report("bbb", core="errore", extra="ok"), report("aaa", core="ok", extra="ok"), "dopo l'aggiornamento")
        self.assertEqual(calls, [["core"]])
        self.assertEqual(self.told, [])

    def test_no_rollback_for_optional_or_old_failures(self):
        calls = self.react(report("bbb", core="ok", extra="errore"), report("aaa", core="ok", extra="ok"), "dopo l'aggiornamento")
        self.assertEqual(calls, [])
        self.assertTrue(any("Non funziona più" in t for t in self.told))
        self.told.clear()
        calls = self.react(report("bbb", core="errore"), report("aaa", core="errore"), "dopo l'aggiornamento")
        self.assertEqual(calls, [])

    def test_no_rollback_at_night(self):
        calls = self.react(report("bbb", core="errore"), report("aaa", core="ok"), "notturno")
        self.assertEqual(calls, [])
        self.assertTrue(self.told)

    def test_recovery_is_reported(self):
        self.react(report("bbb", extra="ok"), report("aaa", extra="errore"), "manuale")
        self.assertTrue(any("Di nuovo in funzione" in t for t in self.told))

    def test_night_window(self):
        self.assertTrue(SelfTest._night(datetime(2026, 10, 2, 3, 30), "03:30"))
        self.assertTrue(SelfTest._night(datetime(2026, 10, 2, 5, 0), "03:30"))
        self.assertFalse(SelfTest._night(datetime(2026, 10, 1, 21, 0), "03:30"))

    def test_full_run_in_demo(self):
        st = SelfTest()
        with mock.patch.object(st, "_react", new=mock.AsyncMock()):
            rep = asyncio.run(st.run("test"))
        by = {r["key"]: r["status"] for r in rep["results"]}
        self.assertEqual(by["automations"], "ok")
        self.assertEqual(by["sounds"], "ok")
        self.assertEqual(by["display"], "saltato")


if __name__ == "__main__":
    unittest.main()
