"""Run: python -m unittest discover -s tests -v   (from the plugin root)"""
import os
import sys
import types
import unittest
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

if not os.path.exists(os.path.join(ROOT, "models.py")):  # test-only stand-in
    stub = types.ModuleType("models")
    stub.choose_model = lambda task_type="ceo", budget="free": {
        "recommended": f"stub-{budget}", "rule": f"stub rule for {task_type}"}
    sys.modules["models"] = stub

import orchestration as o  # noqa: E402

TODAY = date(2026, 11, 4)
GOOD_ASSIGN = {"task": "Reconcile books", "seat": "CFO", "due_date": "2026-11-15"}


class TestDecisions(unittest.TestCase):
    def test_type2_default(self):
        self.assertEqual(o.classify_decision()["type"], "Type 2")

    def test_type1_original_flags(self):
        for flag in ("external", "priced", "irreversible", "legal_or_financial"):
            self.assertEqual(o.classify_decision(**{flag: True})["type"], "Type 1", flag)

    def test_type1_new_flags_match_the_docs(self):
        for flag in ("security", "people", "regulatory", "reputation", "outside_authority"):
            d = o.classify_decision(**{flag: True})
            self.assertEqual(d["type"], "Type 1", flag)
            self.assertEqual(d["triggers"], [flag])

    def test_positional_compat(self):
        self.assertEqual(o.classify_decision(True)["type"], "Type 1")


class TestToolCall(unittest.TestCase):
    def test_unknown_tool_refused_and_not_retryable(self):
        r = o.make_tool_call("ceo_nuke_everything", {})
        self.assertFalse(r["valid"])
        self.assertFalse(r["retryable"])

    def test_arguments_must_be_object(self):
        self.assertFalse(o.make_tool_call("ceo_brief", ["a"])["valid"])

    def test_json_string_arguments_parse(self):
        r = o.make_tool_call("ceo_brief", '{"goal": "x"}')
        self.assertTrue(r["valid"])
        self.assertIn("warnings", r)

    def test_bad_json_string(self):
        self.assertFalse(o.make_tool_call("ceo_brief", "{not json")["valid"])

    def test_credential_key_refused(self):
        r = o.make_tool_call("ceo_brief", {"api_key": "x"})
        self.assertFalse(r["valid"])

    def test_nested_credential_key_refused(self):
        r = o.make_tool_call("ceo_brief", {"meta": {"auth": {"password": "x"}}})
        self.assertFalse(r["valid"])

    def test_secret_value_refused_and_never_echoed(self):
        fake = "sb_secret_FAKE123"
        r = o.make_tool_call("ceo_brief", {"notes": f"use {fake} for the fix"})
        self.assertFalse(r["valid"])
        self.assertNotIn(fake, str(r))
        self.assertIn("arguments.notes", r["error"])

    def test_secret_in_list_refused(self):
        r = o.make_tool_call("ceo_brief", {"steps": ["ok", "ghp_" + "a" * 24]})
        self.assertFalse(r["valid"])

    def test_safe_token_keys_allowed(self):
        # Synced to schemas.py: ceo_brief requires goal, so pass it with max_tokens.
        self.assertTrue(o.make_tool_call("ceo_brief", {"goal": "x", "max_tokens": 500})["valid"])

    def test_assign_requires_all_fields(self):
        for field in ("task", "seat", "due_date"):
            args = {k: v for k, v in GOOD_ASSIGN.items() if k != field}
            r = o.make_tool_call("ceo_assign", args, today=TODAY)
            self.assertFalse(r["valid"], field)

    def test_assign_bad_date_and_seat(self):
        self.assertFalse(o.make_tool_call("ceo_assign", {**GOOD_ASSIGN, "due_date": "11/15/2026"}, today=TODAY)["valid"])
        self.assertFalse(o.make_tool_call("ceo_assign", {**GOOD_ASSIGN, "due_date": "2026-02-31"}, today=TODAY)["valid"])
        self.assertFalse(o.make_tool_call("ceo_assign", {**GOOD_ASSIGN, "seat": "Intern"}, today=TODAY)["valid"])

    def test_assign_ok_is_type2_side_effect_no_gate(self):
        r = o.make_tool_call("ceo_assign", GOOD_ASSIGN, today=TODAY)
        self.assertTrue(r["valid"])
        self.assertEqual(r["seat"], "CFO")
        self.assertTrue(r["side_effect"])
        self.assertFalse(r["approval_required"])

    def test_hermes_is_coo(self):
        r = o.make_tool_call("ceo_assign", {**GOOD_ASSIGN, "seat": "Hermes"}, today=TODAY)
        self.assertEqual(r["seat"], "COO")
        self.assertEqual(o.normalize_seat("COO (Hermes)"), "COO")

    def test_past_due_date_warns_not_fails(self):
        r = o.make_tool_call("ceo_assign", {**GOOD_ASSIGN, "due_date": "2026-01-01"}, today=TODAY)
        self.assertTrue(r["valid"])
        self.assertIn("due_date is in the past.", r["warnings"])

    def test_approval_tools_gated(self):
        # Synced to schemas.py: pass the real required fields, not {}.
        cases = {
            "ceo_decision_log": {"decision": "x", "chosen": "y"},
            "q4_closeout_checklist": {"year": 2026},
        }
        for tool, args in cases.items():
            r = o.make_tool_call(tool, args)
            self.assertTrue(r["approval_required"], tool)
            self.assertIn("gate", r)

    def test_risk_flag_forces_owner_gate(self):
        r = o.make_tool_call("ceo_brief", {"goal": "send offer"}, risk={"external": True, "priced": True})
        self.assertTrue(r["approval_required"])
        self.assertEqual(r["decision"]["type"], "Type 1")


class TestPlan(unittest.TestCase):
    def test_flow_and_verify_step(self):
        p = o.plan_tool_calls("Launch the weekly review")
        tools = [s["tool"] for s in p["steps"]]
        self.assertEqual(tools[:6], ["ceo_brief", "ceo_route", "ceo_assign",
                                     "ceo_tool_call", "ceo_verify", "ceo_decision_log"])
        self.assertNotIn("q4_closeout_checklist", tools)
        self.assertEqual(p["flow"], "Brief -> Route -> Plan -> Assign -> Call -> Verify -> Log")

    def test_q4_checklist_only_for_q4_goals(self):
        p = o.plan_tool_calls("Q4 closeout for the business")
        self.assertEqual(p["steps"][-1]["tool"], "q4_closeout_checklist")
        self.assertTrue(p["steps"][-1]["approval_required"])

    def test_empty_goal_is_an_error(self):
        self.assertFalse(o.plan_tool_calls("  ")["valid"])

    def test_bad_model_key_falls_back(self):
        self.assertIn("model", o.plan_tool_calls("x", model_key="nonsense"))


class TestRetryAndVerify(unittest.TestCase):
    def test_blocked_stops(self):
        self.assertEqual(o.next_action("ceo_assign", "blocked")["action"], "stop_and_wait_for_owner")

    def test_read_tool_error_retries_once_then_escalates(self):
        self.assertEqual(o.next_action("ceo_brief", "error", 0)["action"], "retry_once_with_corrected_arguments")
        self.assertEqual(o.next_action("ceo_brief", "error", 1)["action"], "escalate")

    def test_write_tool_error_never_blind_retry(self):
        self.assertEqual(o.next_action("ceo_assign", "error", 0, executed=None)["action"], "escalate")
        self.assertEqual(o.next_action("ceo_assign", "error", 0, executed=True)["action"], "escalate")

    def test_write_tool_rejected_before_running_may_retry(self):
        self.assertEqual(o.next_action("ceo_assign", "error", 0, executed=False)["action"],
                         "retry_once_with_corrected_arguments")

    def test_unknown_result_is_not_success(self):
        v = o.verify_result("ceo_brief", {"hello": "world"})
        self.assertFalse(v["verified"])
        self.assertEqual(v["next"]["action"], "escalate")

    def test_validated_envelope_is_not_completion(self):
        env = o.make_tool_call("ceo_assign", GOOD_ASSIGN, today=TODAY)
        self.assertFalse(o.verify_result("ceo_assign", env)["verified"])

    def test_success_with_expected_fields(self):
        v = o.verify_result("ceo_brief", '{"status": "success", "brief": "x"}', expect=["brief"])
        self.assertTrue(v["verified"])

    def test_success_missing_expected_field_not_verified(self):
        v = o.verify_result("ceo_brief", {"status": "success"}, expect=["brief"])
        self.assertFalse(v["verified"])
        self.assertEqual(v["missing_fields"], ["brief"])

    def test_blocked_result(self):
        v = o.verify_result("ceo_decision_log", {"status": "needs_approval"})
        self.assertEqual(v["next"]["action"], "stop_and_wait_for_owner")

    def test_invalid_json_result(self):
        self.assertEqual(o.verify_result("ceo_brief", "<html>500</html>")["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
