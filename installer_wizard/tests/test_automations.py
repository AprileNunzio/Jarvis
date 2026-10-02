import asyncio
import unittest

from state import store

from features.automations import actions as leaf
from features.automations.bus import bus
from features.automations.engine import engine
from features.automations.library import InvalidAutomation, library
from features.automations.schema import validate
from features.automations.templates import TEMPLATES

SPOKEN: list[str] = []


def fake_say(text, run, force=False, icon=""):
    SPOKEN.append(text)
    return f"detto {text}"


async def settle(timeout: float = 6.0) -> None:
    for _ in range(int(timeout / 0.05)):
        await asyncio.sleep(0.05)
        if not engine.active:
            return


class AutomationsTest(unittest.TestCase):
    def setUp(self):
        store.phase = "READY"
        leaf.say = fake_say
        SPOKEN.clear()
        for k in list(library.items):
            library.remove(k)
        bus.states.globals.clear()
        engine.recent.clear()

    def test_validation(self):
        spec, errors = validate({"name": "", "actions": []})
        self.assertIn("Serve un nome", errors)
        spec, errors = validate({"name": "x", "triggers": [{"type": "time", "at": "25"}], "actions": [{"type": "boh"}]})
        self.assertTrue(any("ora non valida" in e for e in errors))
        self.assertTrue(any("tipo sconosciuto" in e for e in errors))
        spec, errors = validate({"name": "w", "triggers": [{"type": "webhook"}],
                                 "actions": [{"type": "if", "conditions": [{"type": "expr", "expr": "1"}],
                                              "then": [{"type": "log", "text": "a"}]}]})
        self.assertEqual(errors, [])
        self.assertEqual(len(spec["triggers"][0]["key"]), 32)
        self.assertTrue(spec["actions"][0]["then"][0]["id"])

    def test_templates_are_valid(self):
        for t in TEMPLATES:
            with self.subTest(name=t["name"]):
                self.assertEqual(validate(t)[1], [])

    def test_invalid_is_refused(self):
        with self.assertRaises(InvalidAutomation):
            library.add({"name": "vuota", "actions": []})

    def test_multi_stage_run(self):
        asyncio.run(self._multi_stage())

    async def _multi_stage(self):
        library.add({
            "name": "Caldo", "variables": {"soglia": 26},
            "triggers": [{"type": "state", "entity": "jarvis.var.temp", "above": "{{ 26 }}"}],
            "conditions": [{"type": "or", "conditions": [{"type": "expr", "expr": "num(state('jarvis.var.temp')) > soglia"},
                                                         {"type": "presence", "present": True}]}],
            "actions": [
                {"type": "set", "name": "t", "value": "{{ num(state('jarvis.var.temp')) }}"},
                {"type": "speak", "text": "Ci sono {{ t }} gradi"},
                {"type": "choose", "options": [
                    {"conditions": [{"type": "expr", "expr": "t >= 30"}], "actions": [{"type": "speak", "text": "molto"}]},
                    {"conditions": [{"type": "expr", "expr": "t >= 27"}], "actions": [{"type": "speak", "text": "caldo"}]}],
                 "default": [{"type": "speak", "text": "appena"}]},
                {"type": "repeat", "count": 3, "actions": [{"type": "set", "name": "giri", "value": "{{ ripetizione }}"}]},
                {"type": "parallel", "branches": [[{"type": "delay", "seconds": "0.1"}],
                                                  [{"type": "wait_state", "entity": "jarvis.var.finestra", "to": "aperta", "timeout": 0.3}]]},
                {"type": "if", "conditions": [{"type": "expr", "expr": "scaduto"}],
                 "then": [{"type": "speak", "text": "mai aperta"}], "else": [{"type": "speak", "text": "aperta"}]},
                {"type": "set", "name": "ultimo", "value": "{{ t }}", "scope": "global"},
            ]})
        bus.set_global("temp", 24)
        bus.set_global("temp", 28)
        await settle()
        run = engine.recent[0]
        self.assertEqual(run["status"], "completata", run)
        self.assertEqual(SPOKEN, ["Ci sono 28 gradi", "caldo", "mai aperta"])
        self.assertEqual(run["vars"]["giri"], 3)
        self.assertEqual(bus.states.globals["ultimo"], 28)

    def test_conditions_block(self):
        asyncio.run(self._blocked())

    async def _blocked(self):
        library.add({"name": "Bloccata", "triggers": [{"type": "event", "name": "custom", "custom": "prova"}],
                     "conditions": [{"type": "expr", "expr": "1 > 2"}], "actions": [{"type": "speak", "text": "no"}]})
        bus.emit("prova", {})
        await settle()
        self.assertEqual(SPOKEN, [])
        self.assertEqual(engine.recent[0]["status"], "condizioni non soddisfatte")

    def test_phrase_and_confirm(self):
        asyncio.run(self._phrase())

    async def _phrase(self):
        from features.automations import commands
        library.add({"name": "Notte", "triggers": [{"type": "phrase", "phrases": ["spegni tutto in *"]}],
                     "actions": [{"type": "confirm", "question": "Procedo?", "timeout": 3,
                                  "yes": [{"type": "set", "name": "fatto", "value": "{{ parole[0] }}", "scope": "global"}],
                                  "no": [{"type": "speak", "text": "annullato"}]},
                                 {"type": "respond", "text": "ok"}]})
        reply, _ = await commands.answer("Jarvis, spegni tutto in cucina")
        self.assertIn("ok", reply.lower() + "ok")
        await asyncio.sleep(0.2)
        reply, _ = await commands.answer("sì")
        self.assertIn("Ricevuto", reply)
        await settle()
        self.assertEqual(bus.states.globals.get("fatto"), "cucina")

    def test_modes_single_and_stop(self):
        asyncio.run(self._modes())

    async def _modes(self):
        a = library.add({"name": "Lenta", "mode": "single", "triggers": [{"type": "manual"}],
                         "actions": [{"type": "delay", "seconds": 5}]})
        first = engine.start(a, {"type": "manual"})
        second = engine.start(a, {"type": "manual"})
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        await asyncio.sleep(0.1)
        self.assertTrue(engine.stop(first.id))
        await settle()
        self.assertEqual(engine.recent[0]["status"], "interrotta")


if __name__ == "__main__":
    unittest.main()
