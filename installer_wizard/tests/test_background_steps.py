import asyncio
import unittest

from orchestrator import orch
from state import store
from steps import STEP_BY_ID, STEPS, run_pipeline


class BackgroundStepsTest(unittest.TestCase):
    def test_heavy_optional_steps_are_background(self):
        heavy = {s.id for s in STEPS if s.background}
        self.assertTrue({"office", "convert3d", "soup"} <= heavy)
        self.assertFalse(any(STEP_BY_ID[i].critical for i in heavy))

    def test_boot_pipeline_skips_background_steps(self):
        for s in STEPS:
            store.steps.pop(s.id, None)
        self.assertTrue(asyncio.run(run_pipeline()))
        self.assertEqual(store.steps["office"]["status"], "background")
        self.assertEqual(store.steps["models"]["status"], "done")

    def test_on_demand_install(self):
        store.steps.pop("office", None)
        self.assertTrue(asyncio.run(orch.ensure(["office"], "prova")))
        self.assertEqual(store.steps["office"]["status"], "done")


if __name__ == "__main__":
    unittest.main()
