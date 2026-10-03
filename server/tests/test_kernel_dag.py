import json
import unittest

from server.core.kernel.domain.dag import MAX_NODES, ExecutionDag
from server.core.kernel.domain.errors import DagError
from server.core.kernel.domain.node import NodeKind, NodeSpec, RetryPolicy, RiskLevel
from server.core.kernel.domain.plan_codec import dag_from_plan, extract_json_array


def node(node_id, *deps, **overrides):
    values = {"node_id": node_id, "kind": NodeKind.REASONING, "description": f"do {node_id}", "depends_on": tuple(deps)}
    values.update(overrides)
    return NodeSpec(**values)


class DagStructureTest(unittest.TestCase):
    def test_waves_follow_dependencies(self):
        dag = ExecutionDag.build([node("a"), node("b", "a"), node("c", "a"), node("d", "b", "c")])
        self.assertEqual(dag.waves(), (("a",), ("b", "c"), ("d",)))

    def test_independent_nodes_share_a_wave(self):
        dag = ExecutionDag.build([node("x"), node("y"), node("z")])
        self.assertEqual(dag.waves(), (("x", "y", "z"),))

    def test_cycle_is_rejected(self):
        with self.assertRaisesRegex(DagError, "cycle"):
            ExecutionDag.build([node("a", "c"), node("b", "a"), node("c", "b")])

    def test_self_dependency_is_rejected(self):
        with self.assertRaises(DagError):
            ExecutionDag.build([node("a", "a")])

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaisesRegex(DagError, "unknown"):
            ExecutionDag.build([node("a", "ghost")])

    def test_duplicate_and_empty_inputs_are_rejected(self):
        for specs in ([], [node("a"), node("a")], [node("a", description=" ")]):
            with self.subTest(specs=specs), self.assertRaises(DagError):
                ExecutionDag.build(specs)

    def test_size_limit(self):
        with self.assertRaises(DagError):
            ExecutionDag.build([node(f"n{i}") for i in range(MAX_NODES + 1)])

    def test_dependents_are_transitive(self):
        dag = ExecutionDag.build([node("a"), node("b", "a"), node("c", "b"), node("d")])
        self.assertEqual(dag.dependents_of("a"), frozenset({"b", "c"}))
        self.assertEqual(dag.dependents_of("d"), frozenset())

    def test_max_risk_and_fingerprint_stability(self):
        dag = ExecutionDag.build([node("a"), node("b", "a", risk=RiskLevel.DESTRUCTIVE)])
        self.assertEqual(dag.max_risk(), RiskLevel.DESTRUCTIVE)
        same = ExecutionDag.build([node("b", "a", risk=RiskLevel.DESTRUCTIVE), node("a")])
        different = ExecutionDag.build([node("a"), node("b", "a")])
        self.assertEqual(dag.fingerprint(), same.fingerprint())
        self.assertNotEqual(dag.fingerprint(), different.fingerprint())

    def test_retry_policy_validation(self):
        with self.assertRaises(ValueError):
            RetryPolicy(max_attempts=0)
        with self.assertRaises(ValueError):
            RetryPolicy(deadline_seconds=0)


class PlanCodecTest(unittest.TestCase):
    def test_converts_legacy_plan_format(self):
        dag = dag_from_plan([
            {"step": 1, "description": "scrivi lo script", "depends_on": [], "estimated_intent": "AUTONOMOUS_PROGRAMMING"},
            {"step": 2, "description": "riassumi", "depends_on": [1], "estimated_intent": "GENERAL_INTELLIGENCE"},
        ])
        self.assertEqual(dag.nodes["n1"].kind, NodeKind.CODE)
        self.assertEqual(dag.nodes["n2"].kind, NodeKind.REASONING)
        self.assertEqual(dag.nodes["n2"].depends_on, ("n1",))

    def test_llm_cannot_lower_default_risk(self):
        dag = dag_from_plan([{"step": 1, "description": "rm", "estimated_intent": "SYSOPS_AUTOMATION", "risk": "READ_ONLY"}])
        self.assertEqual(dag.nodes["n1"].risk, RiskLevel.DESTRUCTIVE)

    def test_llm_can_raise_risk(self):
        dag = dag_from_plan([{"step": 1, "description": "x", "risk": "DESTRUCTIVE"}])
        self.assertEqual(dag.nodes["n1"].risk, RiskLevel.DESTRUCTIVE)

    def test_invalid_plans_raise_dag_error(self):
        for items in (
            [{"step": 1, "description": "a", "depends_on": [2]}, {"step": 2, "description": "b", "depends_on": [1]}],
            [{"step": 1, "description": "a", "kind": "wizardry"}],
            [{"step": 1, "description": "a", "depends_on": "1"}],
            [{"step": 1, "description": ""}],
        ):
            with self.subTest(items=items), self.assertRaises(DagError):
                dag_from_plan(items)

    def test_extracts_array_from_noisy_llm_output(self):
        raw = "Ecco il piano:\n```json\n" + json.dumps([{"step": 1, "description": "x"}]) + "\n```"
        self.assertEqual(extract_json_array(raw)[0]["step"], 1)

    def test_rejects_non_array_output(self):
        for raw in ("nessun json", "[1, 2]", '{"a": 1}', "[not json]"):
            with self.subTest(raw=raw), self.assertRaises(DagError):
                extract_json_array(raw)


if __name__ == "__main__":
    unittest.main()
