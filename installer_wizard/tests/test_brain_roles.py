import unittest
from unittest.mock import patch

from features.brain import brains as module
from features.brain.roles import FALLBACK_ROLE, ROLES, split_order


def config_with(env):
    with patch.object(module, "read_env", return_value=env):
        return module.Brains.config()


class RoleRegistryTest(unittest.TestCase):
    def test_identifiers_and_env_keys_are_unique(self):
        self.assertEqual(len({r.id for r in ROLES}), len(ROLES))
        self.assertEqual(len({r.env_key for r in ROLES}), len(ROLES))

    def test_fallback_role_is_registered(self):
        self.assertIn(FALLBACK_ROLE, {r.id for r in ROLES})

    def test_split_order_strips_and_skips_blanks(self):
        self.assertEqual(split_order(" a:1, ,b ,"), ["a:1", "b"])
        self.assertEqual(split_order(""), [])


class RoleConfigTest(unittest.TestCase):
    def test_every_role_has_list_and_custom_flag(self):
        cfg = config_with({})
        for role in ROLES:
            self.assertIn(role.id, cfg)
            self.assertIn(f"{role.id}_custom", cfg)
            self.assertFalse(cfg[f"{role.id}_custom"])

    def test_specialists_follow_deep_list_when_empty(self):
        cfg = config_with({"JARVIS_LLM_DEEP_ORDER": "qwen2.5:7b,qwen2.5:3b"})
        for role in ROLES:
            if role.id not in ("chat", "deep"):
                self.assertEqual(cfg[role.id], cfg["deep"])

    def test_custom_specialist_overrides_and_dedupes(self):
        cfg = config_with({"JARVIS_LLM_RICERCATORE_ORDER": "gemma2:9b,gemma2:9b,llama3.1:8b"})
        self.assertEqual(cfg["ricercatore"], ["gemma2:9b", "llama3.1:8b"])
        self.assertTrue(cfg["ricercatore_custom"])
        self.assertFalse(cfg["domotico_custom"])

    def test_chat_and_deep_defaults_follow_hardware_models(self):
        cfg = config_with({"JARVIS_LLM_MODEL": "big", "JARVIS_LLM_FAST_MODEL": "small"})
        self.assertEqual(cfg["chat"], ["small", "big"])
        self.assertEqual(cfg["deep"], ["big", "small"])

    def test_invalid_routing_falls_back_to_auto(self):
        self.assertEqual(config_with({"JARVIS_LLM_ROUTING": "x"})["routing"], "auto")
        self.assertEqual(config_with({"JARVIS_LLM_ROUTING": "1"})["routing"], "1")

    def test_max_tokens_cover_all_roles(self):
        self.assertEqual(set(module.MAX_TOKENS), {r.id for r in ROLES})


if __name__ == "__main__":
    unittest.main()
