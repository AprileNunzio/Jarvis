import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from features.presentation.application.gate import worth_planning
from features.presentation.application.planner import PresentationPlanner
from features.presentation.domain.plan import Block, PlanError, fill_rows, parse_block, parse_plan
from features.presentation.domain.stage import ImageAsset, to_ui
from features.presentation.infrastructure import wikimedia
from features.presentation.infrastructure.image_store import ImageStore

try:
    import cv2
    import numpy as np
    from features.presentation.infrastructure import cutout
    from features.presentation.infrastructure.commons_images import CommonsImages
    IMAGING = True
except Exception:
    IMAGING = False

LESSON = {
    "mode": "focus", "title": "Il diodo", "speech": "Il diodo lascia passare la corrente in un solo verso.",
    "blocks": [
        {"type": "text", "body": "Un diodo è un componente a due terminali.", "span": 7},
        {"type": "image", "query": "diode symbol", "caption": "Simbolo", "span": 5},
        {"type": "steps", "items": ["Polarizzazione diretta", "Polarizzazione inversa"]},
        {"type": "model3d", "subject": "diodo"},
    ],
}


class PlanParsingTest(unittest.TestCase):
    def test_a_lesson_plan_is_accepted_and_normalised(self):
        plan = parse_plan(LESSON)
        self.assertEqual((plan.mode, plan.title, len(plan.blocks)), ("focus", "Il diodo", 4))
        self.assertEqual([b.span for b in plan.blocks], [7, 5, 12, 12])

    def test_face_mode_needs_only_speech(self):
        plan = parse_plan({"mode": "face", "speech": "Certo."})
        self.assertEqual((plan.mode, plan.blocks), ("face", ()))

    def test_rejections_explain_what_is_wrong(self):
        bad = [
            ({"mode": "focus", "speech": "x", "blocks": []}, "block"),
            ({"mode": "wide", "speech": "x"}, "mode"),
            ({"mode": "focus", "blocks": [{"type": "text", "body": "ciao"}]}, "speech"),
            ({"mode": "focus", "speech": "x", "blocks": [{"type": "hologram"}]}, "unknown"),
            ({"mode": "focus", "speech": "x", "blocks": [{"type": "text", "body": ""}]}, "body"),
            ({"mode": "focus", "speech": "x", "blocks": [{"type": "model3d", "subject": "a"}]}, "subject"),
            ({"mode": "focus", "speech": "x", "blocks": [{"type": "model3d", "subject": "diodo"}]}, "visible"),
            ({"mode": "focus", "speech": "x", "blocks": [{"type": "image", "query": "a b"}] * 3}, "images"),
            ({"mode": "focus", "speech": "x", "blocks": [{"type": "table", "columns": ["a"], "rows": "no"}]}, "table"),
            ("not an object", "object"),
        ]
        for raw, word in bad:
            with self.subTest(word=word), self.assertRaises(PlanError) as ctx:
                parse_plan(raw)
            self.assertIn(word, str(ctx.exception))

    def test_limits_are_enforced_not_trusted(self):
        block = parse_block({"type": "list", "items": [f"voce {i}" for i in range(40)], "span": 99})
        self.assertEqual((len(block.fields["items"]), block.span), (12, 12))
        small = parse_block({"type": "text", "body": "ciao ciao", "span": 0})
        self.assertEqual(small.span, 3)
        table = parse_block({"type": "table", "columns": ["a", "b"], "rows": [["1"]] * 50})
        self.assertEqual(len(table.fields["rows"]), 20)
        self.assertEqual(table.fields["rows"][0], ["1", ""])
        code = parse_block({"type": "code", "content": "print(1)", "language": "py thon;rm"})
        self.assertEqual(code.fields["language"], "testo")

    def test_rows_always_fill_twelve_columns(self):
        blocks = [Block("text", 7), Block("image", 7), Block("list", 3), Block("kv", 6)]
        self.assertEqual([b.span for b in fill_rows(blocks)], [12, 7, 5, 12])
        self.assertEqual([b.span for b in fill_rows([Block("text", 4)])], [12])
        self.assertEqual(fill_rows([]), [])


class StageTest(unittest.TestCase):
    def test_unresolved_images_are_dropped_and_rows_refilled(self):
        plan = parse_plan(LESSON)
        ui = to_ui(plan, {})
        self.assertEqual([p["type"] for p in ui["panels"]], ["text", "steps"])
        self.assertEqual([p["span"] for p in ui["panels"]], [12, 12])
        self.assertEqual((ui["mode"], ui["layout"]), ("focus", "grid"))

    def test_resolved_images_carry_credit_and_license(self):
        ui = to_ui(parse_plan(LESSON), {1: ImageAsset("/api/presentation/image/x.png", "Mario", "CC BY 4.0", "https://c/x")})
        image = next(p for p in ui["panels"] if p["type"] == "image")
        self.assertEqual((image["credit"], image["src"], image["caption"]), ("Mario · CC BY 4.0", "/api/presentation/image/x.png", "Simbolo"))
        self.assertEqual([p["span"] for p in ui["panels"]][:2], [7, 5])

    def test_model_only_plans_fall_back_to_the_face(self):
        plan = parse_plan({"mode": "focus", "speech": "x", "blocks": [{"type": "kv", "items": [{"k": "a", "v": "b"}]}]})
        self.assertEqual(to_ui(plan, {})["panels"][0]["data"], {"a": "b"})

    def test_face_plans_have_no_panels(self):
        self.assertEqual(to_ui(parse_plan({"mode": "face", "speech": "ok"}), {}), {"mode": "face"})


class GateTest(unittest.TestCase):
    def test_trivial_chat_is_not_planned(self):
        self.assertFalse(worth_planning("ciao", "Buongiorno signore, come posso aiutarla oggi? " * 10))
        self.assertFalse(worth_planning("che ore sono", "Sono le dieci."))

    def test_show_and_explain_requests_are_planned_when_there_is_content(self):
        self.assertTrue(worth_planning("mostrami un diodo", "Un diodo è un componente elettronico a due terminali."))
        self.assertTrue(worth_planning("spiegami la fotosintesi", "x" * 80))
        self.assertFalse(worth_planning("spiegami", "ok"))

    def test_long_answers_are_planned_anyway(self):
        self.assertTrue(worth_planning("parlami di roma", "x" * 400))


class FakeImages:
    def __init__(self, asset=None, delay=0.0, fail=False):
        self.asset, self.delay, self.fail, self.queries = asset, delay, fail, []

    async def find(self, query, cutout_requested):
        self.queries.append((query, cutout_requested))
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("down")
        return self.asset


class FakeModels:
    def __init__(self):
        self.subjects = []

    def request(self, subject):
        self.subjects.append(subject)


class PlannerTest(unittest.IsolatedAsyncioTestCase):
    def planner(self, replies, images=None, models=None):
        calls = []

        async def complete(system, user):
            calls.append(user)
            reply = replies[min(len(calls) - 1, len(replies) - 1)]
            if isinstance(reply, Exception):
                raise reply
            return reply

        return PresentationPlanner(complete, images or FakeImages(), models or FakeModels()), calls

    async def test_full_lesson_resolves_images_and_requests_the_model(self):
        images, models = FakeImages(ImageAsset("/i.png", "A", "CC0")), FakeModels()
        planner, _ = self.planner([LESSON], images, models)
        result = await planner.compose("spiegami il diodo", "Un diodo è un componente.")
        self.assertEqual([p["type"] for p in result.ui["panels"]], ["text", "image", "steps"])
        self.assertEqual((images.queries, models.subjects), ([("diode symbol", False)], ["diodo"]))
        self.assertIn("diodo", result.speech)

    async def test_invalid_plans_are_sent_back_with_the_reason_then_accepted(self):
        planner, calls = self.planner([{"mode": "focus", "speech": "x", "blocks": []}, LESSON])
        result = await planner.compose("q", "r")
        self.assertIsNotNone(result)
        self.assertEqual(len(calls), 2)
        self.assertIn("invalido", calls[1])
        self.assertIn("block", calls[1])

    async def test_non_json_answers_count_as_a_failed_attempt(self):
        planner, calls = self.planner([ValueError("no json"), LESSON])
        self.assertIsNotNone(await planner.compose("q", "r"))
        self.assertEqual(len(calls), 2)

    async def test_gives_up_quietly_when_nothing_valid_arrives(self):
        planner, calls = self.planner([{"mode": "focus"}])
        self.assertIsNone(await planner.compose("q", "r"))
        self.assertEqual(len(calls), 2)

    async def test_unavailable_brain_returns_none_without_retrying(self):
        planner, calls = self.planner([RuntimeError("no model")])
        self.assertIsNone(await planner.compose("q", "r"))
        self.assertEqual(len(calls), 1)

    async def test_failing_or_slow_image_sources_do_not_break_the_page(self):
        for images in (FakeImages(fail=True), FakeImages(None)):
            planner, _ = self.planner([LESSON], images)
            result = await planner.compose("q", "r")
            self.assertEqual([p["type"] for p in result.ui["panels"]], ["text", "steps"])

    async def test_slow_images_are_cut_off(self):
        from features.presentation.application import planner as module
        original = module.IMAGE_TIMEOUT_SECONDS
        module.IMAGE_TIMEOUT_SECONDS = 0.05
        try:
            planner, _ = self.planner([LESSON], FakeImages(ImageAsset("/i.png"), delay=1.0))
            started = time.monotonic()
            result = await planner.compose("q", "r")
        finally:
            module.IMAGE_TIMEOUT_SECONDS = original
        self.assertLess(time.monotonic() - started, 0.9)
        self.assertEqual([p["type"] for p in result.ui["panels"]], ["text", "steps"])


class WikimediaTest(unittest.TestCase):
    def page(self, index, title, license_name, mime="image/jpeg", width=1200, thumb="https://upload.wikimedia.org/x.jpg"):
        return {"index": index, "title": f"File:{title}", "imageinfo": [{
            "mime": mime, "width": width, "thumburl": thumb, "thumbwidth": 900, "thumbheight": 600,
            "descriptionshorturl": f"https://commons.wikimedia.org/w/index.php?curid={index}",
            "extmetadata": {"LicenseShortName": {"value": license_name}, "Artist": {"value": '<a href="x">Mario <b>Rossi</b></a>'}}}]}

    def test_only_free_licences_and_sane_files_survive_in_ranking_order(self):
        payload = {"query": {"pages": {
            "1": self.page(3, "c.jpg", "CC BY-SA 4.0"),
            "2": self.page(1, "a.jpg", "CC BY-NC 4.0"),
            "3": self.page(2, "b.jpg", "Public domain"),
            "4": self.page(4, "d.pdf", "CC0", mime="application/pdf"),
            "5": self.page(5, "e.jpg", "CC0", width=100),
            "6": self.page(6, "f.jpg", "CC0", thumb="https://evil.example/x.jpg"),
            "7": self.page(7, "g.jpg", "CC BY-ND 2.0"),
            "8": self.page(8, "h.jpg", "All rights reserved"),
        }}}
        found = wikimedia.candidates(payload)
        self.assertEqual([c.title for c in found], ["b.jpg", "c.jpg"])
        self.assertEqual(found[0].author, "Mario Rossi")

    def test_licence_names(self):
        for name in ("CC0", "Public domain", "CC BY 4.0", "CC BY-SA 3.0", "PD-old-70"):
            self.assertTrue(wikimedia.is_free(name), name)
        for name in ("CC BY-NC 4.0", "CC BY-ND 4.0", "Fair use", "", "GFDL-only NC"):
            self.assertFalse(wikimedia.is_free(name), name)

    def test_empty_or_malformed_payloads(self):
        for payload in ({}, {"query": {}}, {"query": {"pages": {}}}):
            self.assertEqual(wikimedia.candidates(payload), [])

    def test_search_asks_for_images_only(self):
        params = wikimedia.search_params("diode")
        self.assertIn("filetype:bitmap", params["gsrsearch"])
        self.assertEqual(params["gsrnamespace"], "6")


class ImageStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ImageStore(Path(self.temp.name) / "img")

    def test_round_trip_and_deduplication(self):
        name = self.store.save(b"png-bytes")
        self.assertEqual(self.store.save(b"png-bytes"), name)
        self.assertEqual(self.store.path(name).read_bytes(), b"png-bytes")

    def test_only_generated_names_can_be_read(self):
        self.store.save(b"x")
        for name in ("../secret.png", "..%2f..%2fetc", "a.png", "", None, "0" * 24 + ".jpg", "0" * 24 + ".png"):
            self.assertIsNone(self.store.path(name), name)

    def test_old_files_are_pruned(self):
        from features.presentation.infrastructure import image_store
        original = image_store.MAX_FILES
        image_store.MAX_FILES = 3
        try:
            names = [self.store.save(bytes([i]) * 8) for i in range(6)]
        finally:
            image_store.MAX_FILES = original
        self.assertLessEqual(len(list((Path(self.temp.name) / "img").glob("*.png"))), 3)
        self.assertIsNotNone(self.store.path(names[-1]))


@unittest.skipUnless(IMAGING, "OpenCV/numpy non utilizzabili in questo ambiente")
class CutoutTest(unittest.TestCase):
    @staticmethod
    def png(image):
        return cv2.imencode(".png", image)[1].tobytes()

    @staticmethod
    def alpha_of(data):
        return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)

    def object_on_white(self):
        image = np.full((200, 300, 3), 255, np.uint8)
        cv2.rectangle(image, (100, 60), (200, 140), (30, 30, 200), -1)
        return image

    def test_flat_background_becomes_transparent_and_the_object_is_cropped(self):
        out = self.alpha_of(cutout.cut_out(self.png(self.object_on_white())))
        self.assertEqual(out.shape[2], 4)
        self.assertEqual(out[0, 0, 3], 0)
        self.assertEqual(out[out.shape[0] // 2, out.shape[1] // 2, 3], 255)
        self.assertLess(out.shape[1], 300)
        self.assertLess(out.shape[0], 200)

    def test_busy_photos_are_left_alone(self):
        rng = np.random.default_rng(1)
        photo = rng.integers(0, 255, (120, 160, 3), dtype=np.uint8)
        out = self.alpha_of(cutout.cut_out(self.png(photo)))
        self.assertEqual(out.shape[:2], (120, 160))
        self.assertTrue((out[:, :, 3] == 255).all())

    def test_enclosed_background_inside_the_object_is_kept(self):
        image = self.object_on_white()
        cv2.rectangle(image, (130, 90), (170, 110), (255, 255, 255), -1)
        out = self.alpha_of(cutout.cut_out(self.png(image)))
        self.assertTrue((out[:, :, 3] == 255).sum() > 0)
        self.assertEqual(out[out.shape[0] // 2, out.shape[1] // 2, 3], 255)

    def test_normalise_downsizes_and_rejects_garbage(self):
        big = np.full((1800, 1200, 3), 120, np.uint8)
        out = self.alpha_of(cutout.normalise(self.png(big)))
        self.assertEqual(max(out.shape[:2]), cutout.MAX_SIDE)
        self.assertIsNone(cutout.normalise(b"definitely not an image"))
        self.assertIsNone(cutout.cut_out(b""))


@unittest.skipUnless(IMAGING, "OpenCV/numpy non utilizzabili in questo ambiente")
class CommonsImagesTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ImageStore(Path(self.temp.name))
        self.image = cv2.imencode(".png", np.full((400, 500, 3), 90, np.uint8))[1].tobytes()
        self.payload = {"query": {"pages": {"1": WikimediaTest.page(WikimediaTest(), 1, "a.jpg", "CC BY 4.0")}}}

    async def test_downloads_stores_and_credits(self):
        finder = CommonsImages(AsyncMock(return_value=self.payload), AsyncMock(return_value=self.image), self.store, "/api/presentation/image/")
        asset = await finder.find("diode", False)
        self.assertTrue(asset.src.startswith("/api/presentation/image/"))
        self.assertEqual((asset.credit, asset.license), ("Mario Rossi", "CC BY 4.0"))
        self.assertIsNotNone(self.store.path(asset.src.rsplit("/", 1)[1]))

    async def test_broken_downloads_fall_through_to_none(self):
        finder = CommonsImages(AsyncMock(return_value=self.payload), AsyncMock(return_value=b"junk"), self.store, "/x")
        self.assertIsNone(await finder.find("diode", False))

    async def test_search_errors_are_not_fatal(self):
        import httpx
        finder = CommonsImages(AsyncMock(side_effect=httpx.ConnectError("down")), AsyncMock(), self.store, "/x")
        self.assertIsNone(await finder.find("diode", False))


class CompositionTest(unittest.IsolatedAsyncioTestCase):
    async def test_short_answers_never_reach_the_planner(self):
        from features.presentation import composition
        original = composition.planner.compose
        composition.planner.compose = AsyncMock(side_effect=AssertionError("should not run"))
        try:
            self.assertIsNone(await composition.compose("ciao", "Salve."))
        finally:
            composition.planner.compose = original

    async def test_face_plans_keep_the_original_answer_as_speech(self):
        from features.presentation import composition
        from features.presentation.application.planner import Presentation
        original = composition.planner.compose
        composition.planner.compose = AsyncMock(return_value=Presentation("riassunto", {"mode": "face"}))
        try:
            result = await composition.compose("spiegami questo", "Risposta completa " * 10)
        finally:
            composition.planner.compose = original
        self.assertEqual(result[1], {"mode": "face"})
        self.assertTrue(result[0].startswith("Risposta completa"))

    async def test_a_hanging_planner_is_abandoned(self):
        from features.presentation import composition
        original, budget = composition.planner.compose, composition.BUDGET_SECONDS

        async def hang(question, reply):
            await asyncio.sleep(5)

        composition.planner.compose, composition.BUDGET_SECONDS = hang, 0.05
        try:
            self.assertIsNone(await composition.compose("spiegami questo", "x" * 400))
        finally:
            composition.planner.compose, composition.BUDGET_SECONDS = original, budget


if __name__ == "__main__":
    unittest.main()
