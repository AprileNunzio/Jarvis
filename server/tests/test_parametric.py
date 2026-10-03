import json
import os
import tempfile
import unittest
import yaml
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from server.core.agent_registry.interfaces import AgentTaskRequest
from server.core.kernel.domain.node import NodeKind, NodeSpec
from server.core.kernel.domain.outcome import NodeResult
from server.core.kernel.validators.model3d_formats import check_autolisp, check_dxf, check_obj
from server.core.kernel.validators.model3d_validator import Model3DArtifactValidator
from server.features.llm_gateway.contracts import SYNTHETIC_MODEL, LLMResponse
from server.features.parametric.application.designer import ParametricDesigner
from server.features.parametric.application.translator import SpecTranslationError, SpecTranslator
from server.features.parametric.designer_agent import ParametricDesignerAgent
from server.features.parametric.domain.geometry import build_part
from server.features.parametric.domain.renderer import render
from server.features.parametric.domain.schema import BoxPart, ModelSpec

HOUSE = {
    "name": "casa-moderna",
    "units": "m",
    "parts": [
        {"name": "base", "shape": "box", "size": [10, 8, 0.3], "layer": "struttura"},
        {"name": "muro-nord", "shape": "box", "size": [10, 0.3, 3], "position": [0, 3.85, 0.3], "layer": "muri"},
        {"name": "muro-sud", "shape": "box", "size": [10, 0.3, 3], "position": [0, -3.85, 0.3], "layer": "muri"},
        {"name": "tetto", "shape": "gable_roof", "width": 10.4, "depth": 8.4, "height": 2, "position": [0, 0, 3.3]},
        {"name": "colonna", "shape": "cylinder", "radius": 0.2, "height": 3, "position": [5, 4, 0.3], "segments": 12},
        {"name": "camino", "shape": "cone", "radius": 0.4, "height": 1, "position": [3, 0, 5.3], "rotation_deg": [0, 0, 45]},
        {"name": "lampada", "shape": "sphere", "radius": 0.3, "anchor": "center", "position": [0, 0, 2], "segments": 8},
    ],
}


class SchemaTest(unittest.TestCase):
    def test_valid_house_is_accepted(self):
        spec = ModelSpec.model_validate(HOUSE)
        self.assertEqual(len(spec.parts), 7)

    def test_rejections(self):
        def part(**overrides):
            return {**HOUSE, "parts": [{"name": "a", "shape": "box", "size": [1, 1, 1], **overrides}]}

        cases = {
            "unknown field": part(colour="red"),
            "negative size": part(size=[1, -1, 1]),
            "zero size": part(size=[0, 1, 1]),
            "huge position": part(position=[1e9, 0, 0]),
            "nan": part(position=[float("nan"), 0, 0]),
            "bad name": part(name="../etc/passwd"),
            "bad layer": part(layer="a b"),
            "unknown shape": part(shape="teapot"),
            "wrong arity": part(size=[1, 1]),
            "empty parts": {**HOUSE, "parts": []},
            "bad units": {**HOUSE, "units": "inch"},
            "duplicate names": {**HOUSE, "parts": [HOUSE["parts"][0], HOUSE["parts"][0]]},
            "too many segments": {**HOUSE, "parts": [{"name": "c", "shape": "cylinder", "radius": 1, "height": 1, "segments": 5000}]},
            "extra top-level": {**HOUSE, "script": "rm -rf /"},
        }
        for label, data in cases.items():
            with self.subTest(label=label), self.assertRaises(ValidationError):
                ModelSpec.model_validate(data)

    def test_specs_are_immutable(self):
        spec = ModelSpec.model_validate(HOUSE)
        with self.assertRaises(ValidationError):
            spec.name = "altro"


class GeometryTest(unittest.TestCase):
    def test_box_dimensions_and_anchor(self):
        base = BoxPart(name="b", shape="box", size=(2, 4, 6), position=(10, 20, 30))
        xs, ys, zs = zip(*build_part(base).vertices)
        self.assertEqual((min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)), (9, 11, 18, 22, 30, 36))
        centred = BoxPart(name="b", shape="box", size=(2, 4, 6), position=(10, 20, 30), anchor="center")
        zs = [v[2] for v in build_part(centred).vertices]
        self.assertEqual((min(zs), max(zs)), (27, 33))

    def test_rotation_about_z_swaps_extents(self):
        part = BoxPart(name="b", shape="box", size=(4, 2, 1), rotation_deg=(0, 0, 90))
        xs, ys, _ = zip(*build_part(part).vertices)
        self.assertAlmostEqual(max(xs) - min(xs), 2)
        self.assertAlmostEqual(max(ys) - min(ys), 4)

    def test_every_face_references_valid_vertices(self):
        for part in ModelSpec.model_validate(HOUSE).parts:
            mesh = build_part(part)
            for face in mesh.faces:
                self.assertGreaterEqual(len(face), 3, part.name)
                self.assertTrue(all(0 <= i < len(mesh.vertices) for i in face), part.name)

    def test_sphere_height_and_radius(self):
        part = ModelSpec.model_validate({"name": "s", "parts": [{"name": "s", "shape": "sphere", "radius": 2, "segments": 12}]}).parts[0]
        vertices = build_part(part).vertices
        self.assertAlmostEqual(min(v[2] for v in vertices), 0)
        self.assertAlmostEqual(max(v[2] for v in vertices), 4)
        self.assertAlmostEqual(max(v[0] for v in vertices), 2, places=5)


class RendererTest(unittest.TestCase):
    def setUp(self):
        self.rendered = render(ModelSpec.model_validate(HOUSE))

    def test_outputs_pass_the_independent_validators(self):
        obj, dxf, lsp = (self.rendered.files[f"casa-moderna.{e}"] for e in ("obj", "dxf", "lsp"))
        self.assertTrue(check_obj(obj).valid, check_obj(obj).problems)
        self.assertTrue(check_dxf(dxf).valid, check_dxf(dxf).problems)
        self.assertTrue(check_autolisp(lsp).valid, check_autolisp(lsp).problems)
        self.assertEqual(check_obj(obj).vertices, self.rendered.vertices)
        self.assertEqual(check_obj(obj).faces, self.rendered.faces)

    def test_rendering_is_deterministic(self):
        again = render(ModelSpec.model_validate(HOUSE))
        self.assertEqual(again.files, self.rendered.files)

    def test_bounds_match_the_design(self):
        lower, upper = self.rendered.bounds
        self.assertAlmostEqual(lower[0], -5.2, places=5)
        self.assertAlmostEqual(upper[0], 5.2, places=5)
        self.assertAlmostEqual(lower[2], 0)
        self.assertAlmostEqual(upper[2], 6.3, places=5)

    def test_obj_uses_y_up_and_dxf_keeps_z_up(self):
        spec = ModelSpec.model_validate({"name": "t", "parts": [{"name": "t", "shape": "box", "size": [1, 2, 3]}]})
        files = render(spec).files
        obj_ys = [float(line.split()[2]) for line in files["t.obj"].splitlines() if line.startswith("v ")]
        self.assertEqual((min(obj_ys), max(obj_ys)), (0.0, 3.0))
        self.assertIn("\n38\n", files["t.dxf"]) if False else self.assertIn("3DFACE", files["t.dxf"])

    def test_autolisp_has_one_command_per_primitive_and_rotation(self):
        lsp = self.rendered.files["casa-moderna.lsp"]
        self.assertIn('"_.BOX"', lsp)
        self.assertIn('"_.CYLINDER"', lsp)
        self.assertIn('"_.CONE"', lsp)
        self.assertIn('"_.SPHERE"', lsp)
        self.assertIn('"_.ROTATE3D"', lsp)
        self.assertIn('"_LA" "muri"', lsp)
        self.assertTrue(lsp.rstrip().endswith("(c:build-casa-moderna)"))

    def test_llm_text_can_never_reach_the_files(self):
        spec = ModelSpec.model_validate({"name": "x", "parts": [{"name": "a", "shape": "box", "size": [1, 1, 1]}]})
        for content in render(spec).files.values():
            self.assertNotIn("rm -rf", content)


class FakeLlm:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    async def __call__(self, system, user):
        self.requests.append((system, user))
        return self.replies.pop(0)


class TranslatorTest(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_valid_json_wrapped_in_prose(self):
        llm = FakeLlm("Ecco:\n```json\n" + json.dumps(HOUSE) + "\n```")
        translated = await SpecTranslator(llm).translate("disegna una casa moderna")
        self.assertEqual((translated.attempts, translated.spec.name), (1, "casa-moderna"))
        self.assertIn("gable_roof", llm.requests[0][0])

    async def test_accepts_yaml_plain_or_fenced(self):
        document = yaml.safe_dump(HOUSE, sort_keys=False)
        for reply in (document, "Ecco:" + chr(10) + "```yaml" + chr(10) + document + "```" + chr(10) + "fatto"):
            with self.subTest(reply=reply[:12]):
                translated = await SpecTranslator(FakeLlm(reply)).translate("casa")
                self.assertEqual((translated.attempts, translated.spec.name), (1, "casa-moderna"))

    async def test_yaml_tags_cannot_construct_objects(self):
        hostile = "!!python/object/apply:os.system ['echo x']"
        with self.assertRaises(SpecTranslationError):
            await SpecTranslator(FakeLlm(hostile, hostile, hostile)).translate("casa")

    async def test_invalid_specs_are_reinjected_with_the_validation_errors(self):
        bad = json.dumps({**HOUSE, "parts": [{"name": "a", "shape": "box", "size": [1, -1, 1]}]})
        llm = FakeLlm("non è json", bad, json.dumps(HOUSE))
        translated = await SpecTranslator(llm).translate("casa")
        self.assertEqual(translated.attempts, 3)
        self.assertIn("invalida", llm.requests[2][1])
        self.assertIn("size", llm.requests[2][1])

    async def test_gives_up_after_the_attempt_limit(self):
        with self.assertRaises(SpecTranslationError):
            await SpecTranslator(FakeLlm("x", "y", "z"), max_attempts=3).translate("casa")

    async def test_hint_from_the_critic_reaches_the_prompt(self):
        llm = FakeLlm(json.dumps(HOUSE))
        await SpecTranslator(llm).translate("casa", "dxf: missing EOF marker")
        self.assertIn("missing EOF marker", llm.requests[0][1])


class DesignerTest(unittest.IsolatedAsyncioTestCase):
    async def test_writes_only_rendered_files_inside_the_output_root(self):
        with tempfile.TemporaryDirectory() as root:
            designer = ParametricDesigner(SpecTranslator(FakeLlm(json.dumps(HOUSE))), root)
            result = await designer.design("casa", "../../etc/evil")
            self.assertTrue(os.path.abspath(result.folder).startswith(os.path.abspath(root)))
            self.assertEqual(sorted(os.listdir(result.folder)), ["casa-moderna.dxf", "casa-moderna.lsp", "casa-moderna.obj"])
            with open(result.written["casa-moderna.obj"], encoding="utf-8") as handle:
                self.assertEqual(handle.read(), result.rendered.files["casa-moderna.obj"])

    async def test_failed_translation_writes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            designer = ParametricDesigner(SpecTranslator(FakeLlm("x", "y", "z")), root)
            with self.assertRaises(SpecTranslationError):
                await designer.design("casa", "job")
            self.assertEqual(os.listdir(root), [])


class AgentTest(unittest.IsolatedAsyncioTestCase):
    def request(self, **parameters):
        return AgentTaskRequest(task_id="t1", user_id="u", intent="3D_GENERATION", raw_query="disegna una casa", parameters=parameters)

    async def test_claims_only_3d_work(self):
        agent = ParametricDesignerAgent()
        self.assertEqual(await agent.can_handle(self.request()), 0.95)
        other = AgentTaskRequest(task_id="t", user_id="u", intent="HOME_AUTOMATION", raw_query="luci")
        self.assertEqual(await agent.can_handle(other), 0.0)
        node = AgentTaskRequest(task_id="t", user_id="u", intent="GENERAL_INTELLIGENCE", raw_query="x", parameters={"node_kind": "parametric"})
        self.assertEqual(await agent.can_handle(node), 0.95)

    async def test_end_to_end_with_the_critic(self):
        reply = LLMResponse(content=json.dumps(HOUSE), model_used="ollama/x", tokens_consumed=1, duration_ms=1)
        with tempfile.TemporaryDirectory() as root, \
                patch("server.features.parametric.composition.llm_gateway.generate_completion", AsyncMock(return_value=reply)), \
                patch("server.features.parametric.composition.settings.DATA_DIR", root):
            agent = ParametricDesignerAgent()
            response = await agent.execute(self.request())
        self.assertEqual(response.status, "SUCCESS")
        result = NodeResult("n1", {**response.result_data, "status": response.status}, response.speech_output)
        verdict = await Model3DArtifactValidator(require_model=True).judge(NodeSpec("n1", NodeKind.PARAMETRIC, "casa"), result)
        self.assertTrue(verdict.accepted, verdict.error)
        self.assertEqual(response.result_data["stats"]["parts"], 7)

    async def test_synthetic_gateway_answer_is_an_error_and_no_files(self):
        fake = LLMResponse(content="Jarvis Core acknowledges", model_used=SYNTHETIC_MODEL, tokens_consumed=1, duration_ms=1)
        with tempfile.TemporaryDirectory() as root, \
                patch("server.features.parametric.composition.llm_gateway.generate_completion", AsyncMock(return_value=fake)), \
                patch("server.features.parametric.composition.settings.DATA_DIR", root):
            response = await ParametricDesignerAgent().execute(self.request())
            self.assertEqual(os.listdir(root), [])
        self.assertEqual(response.status, "ERROR")


class FormatCheckerTest(unittest.TestCase):
    def test_dxf_problems(self):
        good = render(ModelSpec.model_validate({"name": "t", "parts": [{"name": "a", "shape": "box", "size": [1, 1, 1]}]})).files["t.dxf"]
        self.assertTrue(check_dxf(good).valid)
        self.assertFalse(check_dxf(good.replace("EOF", "")).valid)
        self.assertFalse(check_dxf(good.replace("ENTITIES", "STUFF")).valid)
        self.assertFalse(check_dxf("hello\n").valid)
        self.assertFalse(check_dxf(good.replace("\n10\n", "\n10\nabc\n", 1)).valid)

    def test_autolisp_problems(self):
        self.assertTrue(check_autolisp('(command "_.BOX" (list 0 0 0)) ; ) ignored').valid)
        self.assertFalse(check_autolisp("(command (list 1 2)").valid)
        self.assertFalse(check_autolisp("(a))").valid)
        self.assertFalse(check_autolisp('(princ "abc)').valid)
        self.assertFalse(check_autolisp("  ").valid)


if __name__ == "__main__":
    unittest.main()
