import unittest

from features.automations.expr import ExprError, evaluate, render


class ExprTest(unittest.TestCase):
    def test_arithmetic_and_logic(self):
        self.assertEqual(evaluate("2 + 3 * 4", {}), 14)
        self.assertTrue(evaluate("x > 3 and y == 'a'", {"x": 5, "y": "a"}))
        self.assertEqual(evaluate("'sì' if x else 'no'", {"x": 0}), "no")
        self.assertTrue(evaluate("'26' > 25", {}))

    def test_unknown_names_are_empty(self):
        self.assertIsNone(evaluate("mai_impostata", {}))

    def test_templates(self):
        names = {"t": 28.0, "upper": str.upper}
        self.assertEqual(render("Ci sono {{ t }} gradi", names), "Ci sono 28 gradi")
        self.assertEqual(render("{{ 2 + 3 }} e {{ upper('ok') }}", names), "5 e OK")
        self.assertEqual(render("{{ t }}", names), 28.0)
        self.assertEqual(render({"a": ["{{ 1 + 1 }}"]}, {}), {"a": [2]})

    def test_forbidden_constructs(self):
        for bad in ("__import__('os')", "(lambda: 1)()", "x.__class__", "[i for i in range(3)]", "open('f')"):
            with self.subTest(bad=bad):
                with self.assertRaises(ExprError):
                    evaluate(bad, {"x": 1})

    def test_limits(self):
        with self.assertRaises(ExprError):
            evaluate("1 + " * 300 + "1", {})
        self.assertLess(evaluate("2 ** 1000", {}), 2 ** 65)


if __name__ == "__main__":
    unittest.main()
