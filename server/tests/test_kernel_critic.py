import base64
import json
import unittest
from unittest.mock import AsyncMock

from server.core.kernel.application.scheduler import DagScheduler
from server.core.kernel.application.validators import DEFAULT_VALIDATOR_ID, ValidatorCatalog
from server.core.kernel.domain.dag import ExecutionDag
from server.core.kernel.domain.node import NodeKind, NodeSpec, NodeState, RetryPolicy
from server.core.kernel.domain.outcome import NodeResult
from server.core.kernel.validators.chain import ValidatorChain
from server.core.kernel.validators.code_validator import CodeArtifactValidator
from server.core.kernel.validators.model3d_formats import check_gltf, check_obj
from server.core.kernel.validators.model3d_validator import Model3DArtifactValidator
from server.core.reasoning.self_critique import CritiqueReport, CriticGate, LanguageCritic
from server.features.sandbox.application.gateway import SandboxGateway
from server.features.sandbox.domain.errors import SandboxUnavailableError
from server.features.sandbox.domain.report import ExecutionReport

CUBE_OBJ = "# cube\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\nf 1//1 3//1 4//1\nf -4 -3 -2\n"


def node(kind=NodeKind.CODE, node_id="a", **overrides):
    return NodeSpec(node_id=node_id, kind=kind, description="task", **overrides)


def result(code=None, speech="done", files=None, status="SUCCESS"):
    output = {"status": status}
    if code is not None:
        output["code"] = code
    if files is not None:
        output["files"] = files
    return NodeResult("a", output, speech)


def sandbox_report(**overrides):
    values = dict(exit_code=0, stdout="", stderr="", timed_out=False, oom_killed=False, backend="c", strength=1)
    values.update(overrides)
    return ExecutionReport(**values)


class FakePort:
    def __init__(self, *reports):
        self.reports = list(reports)
        self.sources = []

    async def execute(self, spec):
        self.sources.append(spec.source)
        item = self.reports.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ObjFormatTest(unittest.TestCase):
    def test_valid_obj_with_all_index_styles(self):
        report = check_obj(CUBE_OBJ)
        self.assertTrue(report.valid, report.problems)
        self.assertEqual((report.vertices, report.faces), (4, 3))

    def test_detects_structural_problems(self):
        cases = {
            "no vertices": "f 1 2 3\n",
            "no faces": "v 0 0 0\n",
            "outside": "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n",
            "zero index": "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 0 1 2\n",
            "2 vertices": "v 0 0 0\nv 1 0 0\nf 1 2\n",
            "nan": "v 0 0 nan\nv 1 0 0\nv 0 1 0\nf 1 2 3\n",
            "bad vertex": "v 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n",
            "non numeric": "v 0 0 0\nv 1 0 0\nv 0 1 0\nf a b c\n",
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertFalse(check_obj(text).valid)


def gltf(**patch):
    data = bytes(36 + 6)
    doc = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(data), "uri": "data:application/octet-stream;base64," + base64.b64encode(data).decode()}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}, {"buffer": 0, "byteOffset": 36, "byteLength": 6}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
    }
    doc.update(patch)
    return json.dumps(doc)


class GltfFormatTest(unittest.TestCase):
    def test_valid_triangle(self):
        report = check_gltf(gltf())
        self.assertTrue(report.valid, report.problems)
        self.assertEqual(report.faces, 1)

    def test_detects_problems(self):
        cases = {
            "not json": "{nope",
            "root list": "[]",
            "version": gltf(asset={"version": "1.0"}),
            "no meshes": gltf(meshes=[]),
            "accessor overflow": gltf(accessors=[{"bufferView": 0, "componentType": 5126, "count": 99, "type": "VEC3"}] * 2),
            "bad view": gltf(bufferViews=[{"buffer": 5, "byteLength": 1}]),
            "view exceeds buffer": gltf(bufferViews=[{"buffer": 0, "byteOffset": 40, "byteLength": 36}, {"buffer": 0, "byteLength": 6}]),
            "missing position": gltf(meshes=[{"primitives": [{"attributes": {}}]}]),
            "buffer length": gltf(buffers=[{"byteLength": 3, "uri": "data:application/octet-stream;base64,AAAA"}]),
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                self.assertFalse(check_gltf(text).valid)


class Model3DValidatorTest(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_valid_models_and_ignores_other_files(self):
        verdict = await Model3DArtifactValidator().judge(node(NodeKind.PARAMETRIC), result(files={"a.obj": CUBE_OBJ, "n.txt": "x"}))
        self.assertTrue(verdict.accepted)

    async def test_rejects_corrupt_model_with_actionable_message(self):
        verdict = await Model3DArtifactValidator().judge(node(NodeKind.PARAMETRIC), result(files={"a.obj": "v 0 0 0\nf 1 2 3\n"}))
        self.assertFalse(verdict.accepted)
        self.assertEqual(verdict.error.kind, "model_syntax")
        self.assertIn("a.obj", verdict.error.message)

    async def test_requires_a_model_when_configured(self):
        verdict = await Model3DArtifactValidator(require_model=True).judge(node(NodeKind.PARAMETRIC), result(files={}))
        self.assertEqual(verdict.error.kind, "missing_artifact")

    async def test_rejects_non_mapping_files(self):
        verdict = await Model3DArtifactValidator().judge(node(NodeKind.PARAMETRIC), result(files=["x"]))
        self.assertFalse(verdict.accepted)


class CodeValidatorTest(unittest.IsolatedAsyncioTestCase):
    async def judge(self, code, *reports):
        port = FakePort(*reports)
        return await CodeArtifactValidator(SandboxGateway(port)).judge(node(), result(code=code)), port

    async def test_accepts_code_that_runs_cleanly(self):
        verdict, port = await self.judge("print(1)", sandbox_report())
        self.assertTrue(verdict.accepted)
        self.assertEqual(port.sources, ["print(1)"])

    async def test_syntax_error_is_caught_before_the_sandbox_with_line_number(self):
        verdict, port = await self.judge("x = (\nprint(", sandbox_report())
        self.assertEqual(verdict.error.kind, "syntax_error")
        self.assertIn("line", verdict.error.message)
        self.assertEqual(port.sources, [])

    async def test_runtime_error_returns_stderr_as_feedback(self):
        verdict, _ = await self.judge("1/0", sandbox_report(exit_code=1, stderr="ZeroDivisionError: division by zero"))
        self.assertEqual(verdict.error.kind, "runtime_error")
        self.assertIn("ZeroDivisionError", verdict.error.message)

    async def test_timeout_oom_and_unavailable_sandbox_are_rejections(self):
        verdict, _ = await self.judge("while 1: pass", sandbox_report(exit_code=137, timed_out=True))
        self.assertEqual(verdict.error.kind, "timeout")
        verdict, _ = await self.judge("x=1", sandbox_report(exit_code=137, oom_killed=True))
        self.assertEqual(verdict.error.kind, "memory")
        verdict, _ = await self.judge("x=1", SandboxUnavailableError("down"))
        self.assertEqual(verdict.error.kind, "sandbox_unavailable")

    async def test_missing_code_is_rejected(self):
        verdict = await CodeArtifactValidator(SandboxGateway(FakePort())).judge(node(), result())
        self.assertEqual(verdict.error.kind, "missing_artifact")


class CriticGateTest(unittest.IsolatedAsyncioTestCase):
    def gate(self, report=None, **deterministic):
        engine = AsyncMock()
        engine.review.return_value = report or CritiqueReport(parsed=True, score=9)
        return CriticGate(deterministic, LanguageCritic(engine)), engine

    async def test_wrong_agent_status_is_rejected_first(self):
        gate, engine = self.gate()
        verdict = await gate.judge(node(NodeKind.REASONING), result(status="PARTIAL"))
        self.assertEqual(verdict.error.kind, "agent_status")
        engine.review.assert_not_awaited()

    async def test_reasoning_goes_through_the_language_critic(self):
        gate, engine = self.gate(CritiqueReport(parsed=True, score=3, issues=["incompleto"]))
        verdict = await gate.judge(node(NodeKind.REASONING), result())
        self.assertEqual(verdict.error.kind, "quality")
        self.assertIn("incompleto", verdict.error.message)
        engine.review.assert_awaited_once()

    async def test_unparseable_critic_does_not_block_deterministically_valid_work(self):
        gate, _ = self.gate(CritiqueReport(parsed=False))
        self.assertTrue((await gate.judge(node(NodeKind.REASONING), result())).accepted)

    async def test_deterministic_validator_is_a_hard_gate_and_skips_llm(self):
        gate, engine = self.gate(**{NodeKind.PARAMETRIC: Model3DArtifactValidator()})
        verdict = await gate.judge(node(NodeKind.PARAMETRIC), result(files={"a.obj": "garbage"}))
        self.assertFalse(verdict.accepted)
        engine.review.assert_not_awaited()

    async def test_chain_stops_at_first_rejection(self):
        calls = []

        class Marker:
            def __init__(self, name, accept):
                self.name, self.accept = name, accept

            async def judge(self, spec, res):
                calls.append(self.name)
                from server.core.kernel.domain.outcome import Verdict
                return Verdict.accept() if self.accept else Verdict.reject(self.name, "no")

        verdict = await ValidatorChain([Marker("a", True), Marker("b", False), Marker("c", True)]).judge(node(), result())
        self.assertEqual((verdict.error.kind, calls), ("b", ["a", "b"]))


class ActorCriticLoopTest(unittest.IsolatedAsyncioTestCase):
    async def test_corrupt_3d_output_is_reinjected_until_valid(self):
        seen = []

        class Actor:
            async def execute(self, spec, upstream, feedback):
                seen.append(feedback.message if feedback else None)
                files = {"m.obj": "v 0 0 0\nf 1 2 3\n"} if feedback is None else {"m.obj": CUBE_OBJ}
                return NodeResult(spec.node_id, {"status": "SUCCESS", "files": files}, "modello")

        catalog = ValidatorCatalog()
        catalog.register(DEFAULT_VALIDATOR_ID, CriticGate({NodeKind.PARAMETRIC: Model3DArtifactValidator(require_model=True)}))
        dag = ExecutionDag.build([node(NodeKind.PARAMETRIC, "m", retry=RetryPolicy(max_attempts=3))])
        outcome = await DagScheduler(Actor(), catalog).run(dag)
        self.assertTrue(outcome.succeeded)
        self.assertIsNone(seen[0])
        self.assertIn("m.obj", seen[1])
        self.assertEqual(outcome.run.nodes["m"].state, NodeState.ACCEPTED)

    async def test_actor_that_never_fixes_the_model_fails_instead_of_delegating_to_the_user(self):
        class Stubborn:
            async def execute(self, spec, upstream, feedback):
                return NodeResult(spec.node_id, {"status": "SUCCESS", "files": {"m.obj": "junk"}}, "modello")

        catalog = ValidatorCatalog()
        catalog.register(DEFAULT_VALIDATOR_ID, CriticGate({NodeKind.PARAMETRIC: Model3DArtifactValidator()}))
        dag = ExecutionDag.build([node(NodeKind.PARAMETRIC, "m", retry=RetryPolicy(max_attempts=2))])
        outcome = await DagScheduler(Stubborn(), catalog).run(dag)
        self.assertEqual(outcome.run.nodes["m"].state, NodeState.FAILED)
        self.assertEqual(outcome.run.nodes["m"].attempts, 2)


if __name__ == "__main__":
    unittest.main()
