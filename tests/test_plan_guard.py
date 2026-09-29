import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("guard", Path(__file__).parents[1] / "scripts/check_plan.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PlanGuardTests(unittest.TestCase):
    def test_both_replacement_orders_and_delete_are_rejected(self):
        plan = {"resource_changes": [
            {"address": "a", "change": {"actions": ["delete", "create"]}},
            {"address": "b", "change": {"actions": ["create", "delete"]}},
            {"address": "c", "change": {"actions": ["delete"]}},
            {"address": "d", "change": {"actions": ["update"]}},
        ]}
        self.assertEqual(guard.rejected_changes(plan), ["a", "b", "c"])

    def test_create_update_noop_allowed(self):
        for action in ["create", "update", "no-op", "read"]:
            self.assertEqual(guard.rejected_changes({"resource_changes": [{"address": "a", "change": {"actions": [action]}}]}), [])
