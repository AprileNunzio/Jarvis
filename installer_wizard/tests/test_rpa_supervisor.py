import asyncio
import base64
import struct
import unittest
import zlib
from unittest.mock import patch

from features.rpa.broker import RpaBroker, RpaOffline, RpaTimeout
from features.rpa.controller import RpaController
from features.rpa.steps import parse_steps
from features.vision.ui_anchor import Screen, UiElement, image_size, parse_elements, prompt_for

SCREEN = Screen(1000, 500)


def png(width=1000, height=500):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00" * (width * 3 + 1) * height)) + chunk(b"IEND", b""))


class UiAnchorTest(unittest.TestCase):
    def test_converts_normalised_boxes_to_absolute_pixels(self):
        data = {"found": True, "elements": [{"label": "Salva", "box": [0.1, 0.2, 0.05, 0.1], "confidence": 0.9}]}
        element = parse_elements(data, SCREEN)[0]
        self.assertEqual(element.box, [100, 100, 50, 50])
        self.assertEqual(element.center, (125, 125))
        self.assertEqual(element.to_dict()["cx"], 125)

    def test_sorts_by_confidence_and_caps_candidates(self):
        items = [{"label": str(i), "box": [0.1 * i, 0.1, 0.05, 0.05], "confidence": c} for i, c in enumerate([0.2, 0.9, 0.5, 0.7, 0.1], 1)]
        result = parse_elements({"found": True, "elements": items}, SCREEN)
        self.assertEqual([e.label for e in result], ["2", "4", "3"])

    def test_discards_invalid_hallucinated_boxes(self):
        bad = [
            {"box": [0.1, 0.1, 0.0001, 0.0001]}, {"box": [-0.1, 0.1, 0.1, 0.1]}, {"box": [0.1, 0.1, 1.5, 0.1]},
            {"box": [0, 0, 1, 1]}, {"box": "x"}, {"box": [0.1, 0.1, 0.1]}, {"nobox": 1}, "string", {"box": [0.1, 0.1, "a", 0.1]},
        ]
        self.assertEqual(parse_elements({"found": True, "elements": bad}, SCREEN), [])

    def test_boxes_are_clamped_to_the_screen(self):
        element = parse_elements({"elements": [{"box": [0.95, 0.9, 0.2, 0.2]}]}, SCREEN)[0]
        self.assertEqual((element.x + element.width, element.y + element.height), (1000, 500))

    def test_not_found_and_malformed_answers(self):
        self.assertEqual(parse_elements({"found": False, "elements": [{"box": [0.1, 0.1, 0.1, 0.1]}]}, SCREEN), [])
        self.assertEqual(parse_elements("text", SCREEN), [])
        self.assertEqual(parse_elements(None, SCREEN), [])

    def test_confidence_is_clamped(self):
        element = parse_elements({"elements": [{"box": [0.1, 0.1, 0.1, 0.1], "confidence": 7}]}, SCREEN)[0]
        self.assertEqual(element.confidence, 1.0)

    def test_prompt_mentions_screen_size_query_and_failed_points(self):
        prompt = prompt_for("pulsante {Salva}", Screen(1920, 1080, ((10, 20), (30, 40))))
        for part in ("1920", "1080", "pulsante (Salva)", "(10, 20)", "(30, 40)"):
            self.assertIn(part, prompt)
        self.assertNotIn("già provati", prompt_for("x", SCREEN))

    def test_png_size_reader(self):
        self.assertEqual(image_size(png(123, 45)), (123, 45))
        with self.assertRaises(ValueError):
            image_size(b"\xff\xd8 jpeg")


class StepParsingTest(unittest.TestCase):
    def test_valid_plan(self):
        steps = parse_steps([
            {"do": "click", "target": "menu File"}, {"do": "type", "text": "ciao"}, {"do": "key", "keys": ["ctrl", "s"]},
            {"do": "scroll", "amount": -5}, {"do": "wait", "seconds": 1.5},
        ])
        self.assertEqual([s.do for s in steps], ["click", "type", "key", "scroll", "wait"])
        self.assertTrue(steps[0].pointer)
        self.assertFalse(steps[4].expect_change)

    def test_rejections(self):
        bad = [None, [], "click", [{"do": "click"}], [{"do": "click", "target": "x"}], [{"do": "type", "text": ""}],
               [{"do": "type", "text": "è"}], [{"do": "key", "keys": []}], [{"do": "scroll", "amount": 0}],
               [{"do": "wait", "seconds": 99}], [{"do": "shell", "cmd": "rm"}], ["click"], [{"do": "click", "target": "ok"}] * 13]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_steps(raw)


class BrokerTest(unittest.IsolatedAsyncioTestCase):
    def broker(self):
        broker = RpaBroker()
        broker.note_poll("n1", {"screen": [1920, 1080], "version": "1.0.0"})
        return broker

    async def test_instruction_round_trip(self):
        broker = self.broker()

        async def node():
            instruction = await broker.poll("n1", 1)
            self.assertEqual(instruction["action"], "click")
            self.assertTrue(broker.complete("n1", {"id": instruction["id"], "ok": True, "data": {"changed_ratio": 0.5}}))

        worker = asyncio.create_task(node())
        result = await broker.submit("n1", {"action": "click", "x": 1, "y": 2})
        await worker
        self.assertEqual(result["data"]["changed_ratio"], 0.5)

    async def test_offline_node_is_refused(self):
        with self.assertRaises(RpaOffline):
            await RpaBroker().submit("ghost", {"action": "capture"})

    async def test_timeout_clears_pending_state(self):
        broker = self.broker()
        with self.assertRaises(RpaTimeout):
            await broker.submit("n1", {"action": "capture"}, timeout=0.05)
        self.assertFalse(broker.complete("n1", {"id": "anything"}))

    async def test_poll_returns_none_when_idle(self):
        self.assertIsNone(await self.broker().poll("n1", 0.05))

    async def test_a_node_cannot_complete_another_nodes_instruction(self):
        broker = self.broker()
        broker.note_poll("n2", {})
        submitted = asyncio.create_task(broker.submit("n1", {"action": "capture"}, timeout=1))
        instruction = await broker.poll("n1", 1)
        self.assertFalse(broker.complete("n2", {"id": instruction["id"], "ok": True}))
        self.assertTrue(broker.complete("n1", {"id": instruction["id"], "ok": True}))
        self.assertTrue((await submitted)["ok"])

    async def test_duplicate_completion_is_ignored(self):
        broker = self.broker()
        submitted = asyncio.create_task(broker.submit("n1", {"action": "capture"}, timeout=1))
        instruction = await broker.poll("n1", 1)
        self.assertTrue(broker.complete("n1", {"id": instruction["id"], "ok": True}))
        self.assertFalse(broker.complete("n1", {"id": instruction["id"], "ok": True}))
        await submitted

    def test_screen_info_is_validated(self):
        broker = RpaBroker()
        broker.note_poll("n1", {"screen": [10 ** 9, 5]})
        self.assertIsNone(broker.info("n1")["screen"])
        broker.note_poll("n1", {"screen": [800, 600], "version": "x" * 100})
        self.assertEqual(broker.info("n1")["screen"], [800, 600])
        self.assertEqual(len(broker.info("n1")["version"]), 20)


class ScriptedTransport:
    def __init__(self, click_results):
        self.click_results = list(click_results)
        self.sent = []

    async def submit(self, node_id, instruction, timeout=45.0):
        self.sent.append(instruction)
        if instruction["action"] == "capture":
            return {"ok": True, "frame": base64.b64encode(png()).decode(), "data": {}}
        return self.click_results.pop(0)


class ScriptedLocator:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    async def locate(self, png_bytes, query, screen):
        self.calls.append((query, screen.failed_points))
        return self.answers.pop(0) if self.answers else []


def element(x, y, label="ok"):
    return UiElement(label, x, y, 60, 30, 0.9)


def effect(ratio, region=None, acted=True):
    return {"ok": True, "data": {"changed_ratio": ratio, "region_ratio": region, "settled": True, "acted": acted}}


class ControllerTest(unittest.IsolatedAsyncioTestCase):
    async def run_steps(self, transport, locator, steps, attempts=3):
        frames = {}
        controller = RpaController(transport, locator, max_attempts=attempts, store_frame=frames.__setitem__)
        trace = await controller.run("n1", parse_steps(steps))
        return trace, frames

    async def test_successful_click_is_verified_by_pixels(self):
        transport, locator = ScriptedTransport([effect(0.12, 0.8)]), ScriptedLocator([element(100, 200)])
        trace, frames = await self.run_steps(transport, locator, [{"do": "click", "target": "Salva"}])
        self.assertTrue(trace.ok)
        click = transport.sent[1]
        self.assertEqual((click["action"], click["x"], click["y"]), ("click", 130, 215))
        self.assertEqual(click["region"], [100, 200, 60, 30])
        self.assertIn("min_contrast", click)
        self.assertIn("n1", frames)

    async def test_no_visible_effect_retries_elsewhere_and_feeds_failed_points_back(self):
        transport = ScriptedTransport([effect(0.0, 0.0), effect(0.2, 0.9)])
        locator = ScriptedLocator([element(100, 200)], [element(100, 200), element(400, 300, "altro")])
        trace, _ = await self.run_steps(transport, locator, [{"do": "click", "target": "Invia"}])
        self.assertTrue(trace.ok)
        self.assertEqual(len(trace.steps[0].attempts), 2)
        self.assertEqual(locator.calls[1][1], ((130, 215),))
        self.assertEqual([c["x"] for c in transport.sent if c["action"] == "click"], [130, 430])

    async def test_gives_up_after_max_attempts_with_a_readable_reason(self):
        transport = ScriptedTransport([effect(0.0)] * 3)
        locator = ScriptedLocator([element(10, 10)], [element(200, 10)], [element(400, 10)])
        trace, _ = await self.run_steps(transport, locator, [{"do": "click", "target": "x1"}, {"do": "type", "text": "mai"}])
        self.assertFalse(trace.ok)
        self.assertIn("Passo 1", trace.message)
        self.assertEqual(len(trace.steps), 1)
        self.assertIn("nessuna variazione", trace.steps[0].message)

    async def test_flat_area_is_rejected_without_counting_as_success(self):
        transport = ScriptedTransport([effect(0.0, 0.0, acted=False), effect(0.3, 0.9)])
        locator = ScriptedLocator([element(10, 10)], [element(300, 300)])
        trace, _ = await self.run_steps(transport, locator, [{"do": "click", "target": "bottone fantasma"}])
        self.assertTrue(trace.ok)
        self.assertFalse(trace.steps[0].attempts[0]["acted"])

    async def test_element_not_found(self):
        transport, locator = ScriptedTransport([]), ScriptedLocator([], [], [])
        trace, _ = await self.run_steps(transport, locator, [{"do": "click", "target": "inesistente"}])
        self.assertFalse(trace.ok)
        self.assertIn("non trovato", trace.steps[0].message)
        self.assertEqual([c["action"] for c in transport.sent], ["capture"] * 3)

    async def test_same_candidate_is_not_retried_at_a_failed_point(self):
        transport = ScriptedTransport([effect(0.0)])
        locator = ScriptedLocator([element(100, 100)], [element(105, 103)], [])
        trace, _ = await self.run_steps(transport, locator, [{"do": "click", "target": "x1"}], attempts=3)
        self.assertFalse(trace.ok)
        self.assertEqual(len([c for c in transport.sent if c["action"] == "click"]), 1)

    async def test_keyboard_steps_and_expect_change(self):
        transport = ScriptedTransport([effect(0.05), effect(0.0), effect(0.0)])
        steps = [{"do": "type", "text": "ciao"}, {"do": "key", "keys": ["enter"]}, {"do": "scroll", "amount": 3}]
        trace, _ = await self.run_steps(transport, ScriptedLocator(), steps)
        self.assertTrue(trace.ok)
        self.assertEqual([s["action"] for s in transport.sent], ["type", "key", "scroll"])

    async def test_typing_that_changes_nothing_fails_unless_not_expected(self):
        trace, _ = await self.run_steps(ScriptedTransport([effect(0.0)]), ScriptedLocator(), [{"do": "type", "text": "x"}])
        self.assertFalse(trace.ok)
        trace, _ = await self.run_steps(ScriptedTransport([effect(0.0)]), ScriptedLocator(), [{"do": "type", "text": "x", "expect_change": False}])
        self.assertTrue(trace.ok)

    async def test_node_errors_and_offline_nodes_are_reported(self):
        trace, _ = await self.run_steps(ScriptedTransport([{"ok": False, "error": "OSError: no uinput"}]), ScriptedLocator(), [{"do": "type", "text": "x"}])
        self.assertIn("no uinput", trace.message)

        class Offline:
            async def submit(self, node_id, instruction, timeout=45.0):
                raise RpaOffline("nodo spento")

        trace, _ = await self.run_steps(Offline(), ScriptedLocator(), [{"do": "key", "keys": ["a"]}])
        self.assertFalse(trace.ok)
        self.assertIn("nodo spento", trace.message)

    async def test_trace_is_serialisable(self):
        trace, _ = await self.run_steps(ScriptedTransport([effect(0.1, 0.5)]), ScriptedLocator([element(5, 5)]), [{"do": "click", "target": "ok"}])
        data = trace.to_dict()
        self.assertTrue(data["ok"])
        self.assertEqual(data["steps"][0]["attempts"][0]["element"]["label"], "ok")


class ServicePermissionTest(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_or_unlisted_nodes_are_refused(self):
        from features.rpa import service

        for env in ({}, {"JARVIS_RPA": "1"}, {"JARVIS_RPA": "0", "JARVIS_RPA_NODES": "n1"}, {"JARVIS_RPA": "1", "JARVIS_RPA_NODES": "n2"}):
            with self.subTest(env=env), patch.object(service, "env_get", lambda k, d="": env.get(k, d)):
                with self.assertRaises(PermissionError):
                    await service.rpa.run("n1", [{"do": "wait", "seconds": 1}])

    async def test_permitted_node_with_invalid_steps_is_a_value_error(self):
        from features.rpa import service

        env = {"JARVIS_RPA": "1", "JARVIS_RPA_NODES": "n1, n3"}
        with patch.object(service, "env_get", lambda k, d="": env.get(k, d)):
            self.assertTrue(service.rpa.permitted("n3"))
            with self.assertRaises(ValueError):
                await service.rpa.run("n1", [{"do": "format"}])


if __name__ == "__main__":
    unittest.main()
