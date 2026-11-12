"""v0.4.0 regression + fuzz tests. Every test pins a bug reproduced on the v0.3.0 base (806e71ae)."""

import json
import random
import string
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import orchestration as o  # noqa: E402
import tools  # noqa: E402

FAKE_SK = "sk-" + "abcdefghijklmnop1234567890"  # fake, assembled so no scanner flags this file


def call(fn, **args):
    out = json.loads(fn(args))
    assert isinstance(out, dict)
    return out


class VerifyHookOnRealOutput(unittest.TestCase):
    """v0.3.0 bug: every real, successful ceo_* result verified as 'unknown' and escalated."""

    def test_real_results_verify_cleanly(self):
        cases = {
            "ceo_brief": call(tools.ceo_brief, goal="Grow newsletter"),
            "ceo_assign": call(tools.ceo_assign, task="Reconcile books", seat="CFO", due_date="2030-01-01"),
            "ceo_route": call(tools.ceo_route, task="Reconcile books"),
            "q4_closeout_checklist": call(tools.q4_closeout_checklist, year=2026),
            "ceo_orchestrate": call(tools.ceo_orchestrate, goal="Grow newsletter"),
            "ceo_choose_model": call(tools.ceo_choose_model),
            "ceo_decision_log": call(tools.ceo_decision_log, decision="d", chosen="c", needs_approval=False),
        }
        for name, result in cases.items():
            v = o.verify_result(name, result)
            self.assertTrue(v["verified"], (name, v))
            self.assertEqual(v["expect_source"], "default", name)

    def test_gated_decision_stops_for_owner(self):
        v = o.verify_result("ceo_decision_log", call(tools.ceo_decision_log, decision="d", chosen="c"))
        self.assertFalse(v["verified"])
        self.assertEqual(v["next"]["action"], "stop_and_wait_for_owner")

    def test_missing_expected_field_is_not_verified(self):
        v = o.verify_result("ceo_assign", {"status": "success", "owner": "CFO"})
        self.assertFalse(v["verified"])
        self.assertEqual(sorted(v["missing_fields"]), ["due_date", "task"])

    def test_empty_list_counts_as_missing(self):
        v = o.verify_result("ceo_brief", {"status": "success", "goal": "g", "workstreams": []})
        self.assertFalse(v["verified"])

    def test_expect_string_is_one_field_not_characters(self):
        v = o.verify_result("ceo_assign", {"status": "success", "owner": "CFO"}, expect="owner")
        self.assertEqual(v["missing_fields"], [])
        self.assertEqual(v["expect_source"], "caller")

    def test_bad_retries_used_assumes_budget_spent(self):
        v = o.verify_result("ceo_assign", {"status": "error", "error": "x"}, retries_used="1")
        self.assertEqual(v["next"]["action"], "escalate")

    def test_unknown_stays_unknown(self):
        self.assertFalse(o.verify_result("ceo_brief", {"foo": 1})["verified"])
        self.assertEqual(o.verify_result("ceo_brief", "not json")["status"], "unknown")


class HandlersNeverRaise(unittest.TestCase):
    """v0.3.0 bug: non-string input raised AttributeError despite the 'never raise' contract."""

    HANDLERS = [tools.ceo_brief, tools.ceo_assign, tools.ceo_decision_log, tools.ceo_route,
                tools.q4_closeout_checklist, tools.ceo_orchestrate, tools.ceo_choose_model,
                tools.ceo_tool_call, tools.ceo_verify]
    WEIRD = [None, 5, 5.5, True, [], {}, "hi", ["x"], {"a": {"b": [1, None]}}, "{", "{}", "[]", 10**30, float("inf")]

    def test_weird_args_return_json_dict(self):
        for h in self.HANDLERS:
            for w in self.WEIRD:
                out = json.loads(h(w))
                self.assertIsInstance(out, dict, (h.__name__, w))

    def test_weird_field_values_return_json_dict(self):
        fields = ["goal", "task", "seat", "due_date", "decision", "chosen", "reason", "options",
                  "year", "domain", "tool_name", "arguments", "result", "expect", "retries_used",
                  "needs_approval", "business_name", "entity_type", "model_key", "budget", "task_type", "risk"]
        for h in self.HANDLERS:
            for f in fields:
                for w in self.WEIRD:
                    out = json.loads(h({f: w}))
                    self.assertIsInstance(out, dict, (h.__name__, f, w))

    def test_random_fuzz_never_raises(self):
        rng = random.Random(4040)  # seeded: deterministic

        def junk(depth=0):
            kind = rng.choice(["s", "i", "n", "l", "d", "b"] if depth < 3 else ["s", "i", "n", "b"])
            if kind == "s":
                return "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 40)))
            if kind == "i":
                return rng.randint(-5, 10**6)
            if kind == "n":
                return None
            if kind == "b":
                return rng.choice([True, False])
            if kind == "l":
                return [junk(depth + 1) for _ in range(rng.randint(0, 3))]
            return {rng.choice(["goal", "task", "seat", "tool_name", "arguments", "result", "risk", "x"]): junk(depth + 1)
                    for _ in range(rng.randint(0, 4))}

        for _ in range(400):
            for h in self.HANDLERS:
                json.loads(h(junk()))

    def test_missing_goal_message_kept(self):
        self.assertIn("No goal provided", call(tools.ceo_brief)["error"])
        self.assertIn("No task provided", call(tools.ceo_route)["error"])


class SecretGuard(unittest.TestCase):
    def test_every_handler_refuses_secrets_without_echo(self):
        payloads = [{"goal": f"use {FAKE_SK} now"}, {"task": "x", "api_key": "abc"},
                    {"decision": "d", "chosen": "c", "reason": f"key {FAKE_SK}"}]
        for h in (tools.ceo_brief, tools.ceo_assign, tools.ceo_decision_log, tools.ceo_route,
                  tools.ceo_orchestrate, tools.ceo_verify, tools.q4_closeout_checklist, tools.ceo_choose_model):
            for p in payloads:
                text = h(p)
                self.assertNotIn("abcdefghijklmnop1234567890", text, h.__name__)
                self.assertEqual(json.loads(text)["status"], "error", (h.__name__, p))

    def test_fail_closed_beyond_depth_limit(self):
        deep = {"v": FAKE_SK}
        for _ in range(30):
            deep = {"n": deep}
        self.assertTrue(o.find_secret_paths(deep))

    def test_stringified_json_scanned(self):
        self.assertTrue(o.find_secret_paths({"payload": json.dumps({"api_key": "abc123"})}))

    def test_zero_width_and_fullwidth_key_variants(self):
        self.assertTrue(o.find_secret_paths({"api\u200b_key": "v"}))
        self.assertTrue(o.find_secret_paths({"\uff50\uff41\uff53\uff53\uff57\uff4f\uff52\uff44": "v"}))
        self.assertTrue(o.find_secret_paths({"API-KEY": "v"}))
        self.assertTrue(o.find_secret_paths({"access key": "v"}))

    def test_more_credential_shapes(self):
        shapes = ["sk_live_" + "a" * 20, "Bearer " + "a1b2c3d4e5" * 3, "AIza" + "a" * 35, "hf_" + "a" * 25,
                  "npm_" + "a" * 36, "SG." + "a" * 20 + "." + "b" * 20,
                  "postgres://admin:hunter22@db.example.com/x", "password: hunter22", "token=abcdef123456"]
        for s in shapes:
            self.assertTrue(o.find_secret_paths({"x": s}), s[:12])

    def test_secret_as_dict_key_is_redacted_in_path(self):
        hits = o.find_secret_paths({FAKE_SK: "v"})
        self.assertTrue(hits)
        self.assertNotIn("abcdefghijklmnop", str(hits))

    def test_no_false_positives_on_normal_planning_text(self):
        clean = [{"goal": "Raise the token budget discussion with the team", "max_tokens": 1000},
                 {"task": "Review the password policy document", "token_count": 5},
                 {"task": "Write the weekly update", "notes": "Keep it under 200 words"}]
        for c in clean:
            self.assertEqual(o.find_secret_paths(c), [], c)


class GatingFromContent(unittest.TestCase):
    def test_misspelled_risk_flag_refused(self):
        env = o.make_tool_call("ceo_assign", {"task": "Reconcile books", "seat": "CFO", "due_date": "2030-01-01"},
                               risk={"extrenal": True})
        self.assertFalse(env["valid"])
        self.assertIn("extrenal", env["error"])

    def test_non_dict_risk_refused(self):
        env = o.make_tool_call("ceo_brief", {"goal": "g"}, risk="none")
        self.assertFalse(env["valid"])

    def test_handler_does_not_drop_bad_risk(self):
        self.assertFalse(call(tools.ceo_tool_call, tool_name="ceo_brief", arguments={"goal": "g"}, risk="none")["valid"])

    def test_wording_raises_to_type_1(self):
        for task in ["Pay the vendor invoice", "Send the pricing email to the client", "Delete the old customer database",
                     "Fire the contractor", "File our 2026 taxes", "Wire funds to the supplier", "Publish the announcement",
                     "Rotate the production password", "Set the new pricing for Q1"]:
            env = o.make_tool_call("ceo_assign", {"task": task, "seat": "CFO", "due_date": "2030-01-01"})
            self.assertTrue(env["approval_required"], task)
            self.assertEqual(env["decision"]["type"], "Type 1", task)
            self.assertTrue(env["inferred_risk"], task)

    def test_ordinary_work_stays_type_2(self):
        for task in ["Reconcile the books for October", "Draft the weekly status update", "Summarize last week's metrics",
                     "Organize the shared drive", "Prepare an agenda for Monday", "Research three CRM options",
                     "Pay attention to the cash flow trend", "Review the proposal for the new laptops"]:
            env = o.make_tool_call("ceo_assign", {"task": task, "seat": "COO", "due_date": "2030-01-01"})
            self.assertFalse(env["approval_required"], task)
            self.assertEqual(env["decision"]["type"], "Type 2", task)

    def test_content_cannot_lower_explicit_flags(self):
        env = o.make_tool_call("ceo_assign", {"task": "Draft notes", "seat": "CFO", "due_date": "2030-01-01"},
                               risk={"external": True})
        self.assertEqual(env["decision"]["type"], "Type 1")

    def test_decision_log_cannot_be_ungated_for_type_1_wording(self):
        out = call(tools.ceo_decision_log, decision="Vendor payment", chosen="Wire funds to the vendor today",
                   needs_approval=False)
        self.assertTrue(out["needs_approval"])
        self.assertEqual(out["status"], "needs_approval")
        self.assertIn("gate_note", out)

    def test_decision_log_ordinary_can_be_recorded(self):
        out = call(tools.ceo_decision_log, decision="Meeting day", chosen="Mondays", needs_approval=False)
        self.assertFalse(out["needs_approval"])
        self.assertEqual(out["status"], "success")

    def test_assign_approval_matches_envelope(self):
        for seat in ("CEO", "CFO"):
            args = {"task": "Draft notes", "seat": seat, "due_date": "2030-01-01"}
            self.assertEqual(call(tools.ceo_assign, **args)["approval_required"],
                             o.make_tool_call("ceo_assign", args)["approval_required"], seat)

    def test_plan_marks_call_step_for_risky_goal(self):
        plan = call(tools.ceo_orchestrate, goal="Send the price list to every customer")
        self.assertTrue(plan["steps"][3]["approval_required"])
        calm = call(tools.ceo_orchestrate, goal="Summarize last week's metrics")
        self.assertFalse(calm["steps"][3]["approval_required"])
        self.assertEqual(plan["run_id"], call(tools.ceo_orchestrate, goal="Send the price list to every customer")["run_id"])


class Routing(unittest.TestCase):
    def test_whole_words_only(self):
        self.assertNotEqual(call(tools.ceo_route, task="Review the proposal for new laptops")["routed_to"], "COO (Hermes)")

    def test_legal_wins_over_marketing_with_consult(self):
        out = call(tools.ceo_route, task="Legal review of the marketing contract")
        self.assertEqual(out["routed_to"], "CLO")
        self.assertIn("CMO", out["also_consult"])

    def test_taxes_route_to_cfo(self):
        self.assertEqual(call(tools.ceo_route, task="Prepare our 2026 taxes")["routed_to"], "CFO")

    def test_no_match_goes_to_ceo_low_confidence(self):
        out = call(tools.ceo_route, task="Think about the long horizon")
        self.assertEqual((out["routed_to"], out["confidence"]), ("CEO", "low"))

    def test_explicit_domain_wins(self):
        self.assertEqual(call(tools.ceo_route, task="x", domain="Finance")["routed_to"], "CFO")

    def test_routing_is_not_blanket_gated(self):
        self.assertFalse(call(tools.ceo_route, task="Summarize last week's metrics")["approval_required"])
        self.assertTrue(call(tools.ceo_route, task="Pay the vendor invoice")["approval_required"])


class Q4Trigger(unittest.TestCase):
    def test_taxes_triggers_q4_step(self):
        plan = call(tools.ceo_orchestrate, goal="File our 2026 taxes")
        self.assertEqual(len(plan["steps"]), 7)
        self.assertEqual(len(call(tools.ceo_orchestrate, goal="Plan the offsite")["steps"]), 6)

    def test_q4_year_validation(self):
        self.assertEqual(call(tools.q4_closeout_checklist, year="2026")["year"], 2026)
        for bad in (0, "abc", 1850, 3000, True, 2026.5):
            self.assertEqual(call(tools.q4_closeout_checklist, year=bad)["status"], "error", bad)


class EnvelopeStaysNotCompleted(unittest.TestCase):
    def test_valid_envelope_is_not_a_completion(self):
        env = call(tools.ceo_tool_call, tool_name="ceo_brief", arguments={"goal": "g"})
        self.assertTrue(env["valid"])
        self.assertNotEqual(o.verify_result("ceo_tool_call", env)["status"], "success")

    def test_hook_on_real_package(self):
        import importlib.util
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("ceo_pack_under_test", root / "__init__.py",
                                                      submodule_search_locations=[str(root)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules["ceo_pack_under_test"] = pkg
        spec.loader.exec_module(pkg)
        real = tools.ceo_assign({"task": "Reconcile books", "seat": "CFO", "due_date": "2030-01-01"})
        with self.assertLogs("ceo_pack_under_test", level="INFO") as cm:
            pkg._on_post_tool_call("ceo_assign", {}, real, "t1")
            pkg._on_post_tool_call("ceo_tool_call", {}, real, "t1")
            pkg._on_post_tool_call("ceo_verify", {}, "not json", "t1")
            pkg._on_post_tool_call("ceo_assign", {}, "garbage", "t1")
            pkg._on_post_tool_call("ceo_assign", {}, None, "t1")
        text = "\n".join(cm.output)
        self.assertIn("verified=True", text)
        self.assertEqual(text.count("meta tool"), 2)
        self.assertIn("verified=False", text)


class AliasesAndHeadSeat(unittest.TestCase):
    def test_alias_resolves_to_canonical(self):
        ok, err = o.set_seat_aliases({"Poseidon": "COO", "Billy": "CEO"})
        self.assertTrue(ok, err)
        try:
            self.assertEqual(o.normalize_seat("Poseidon"), "COO")
            self.assertEqual(o.normalize_seat("billy"), "CEO")
            self.assertEqual(o.display_seat("COO"), "Poseidon (COO)")
            self.assertEqual(call(tools.ceo_assign, task="Draft notes", seat="Poseidon", due_date="2030-01-01")["owner"], "COO (Hermes)")
        finally:
            o.set_seat_aliases({})

    def test_duplicate_alias_refused(self):
        ok, err = o.set_seat_aliases({"Poseidon": "COO", "Poseidon2": "COO"})
        self.assertFalse(ok)
        self.assertIn("COO", err)
        o.set_seat_aliases({})

    def test_unknown_alias_refused(self):
        self.assertIsNone(o.normalize_seat("Wizard"))

    def test_head_seat_config(self):
        ok, err = o.set_head_seat("CFO")
        self.assertTrue(ok, err)
        try:
            plan = o.plan_tool_calls("Grow newsletter")
            self.assertEqual(plan["head_seat"], "CFO")
            self.assertEqual(plan["steps"][0]["seat"], "CFO")
        finally:
            o.set_head_seat("CEO")


class CapabilityCheck(unittest.TestCase):
    def test_missing_listed_and_install_gated(self):
        res = o.check_capabilities("CFO", ["read numbers and summaries"])
        self.assertFalse(res["complete"])
        self.assertIn("reconcile books", res["missing"])
        self.assertEqual(res["binding"], "name-only")
        plan = o.propose_capability_install("CFO", res["missing"])
        self.assertEqual(plan["status"], "needs_approval")
        approved = o.propose_capability_install("CFO", res["missing"], owner_approved=True)
        self.assertEqual(approved["status"], "success")
        full = o.check_capabilities("CFO", o.CAPABILITY_CHECKLISTS["CFO"])
        self.assertTrue(full["complete"])

    def test_unknown_seat_refused(self):
        self.assertFalse(o.check_capabilities("Wizard", [])["valid"])

    def test_install_all_is_default_per_item_available(self):
        res = o.check_capabilities("CFO", ["read numbers and summaries"])
        missing = res["missing"]
        plan = o.propose_capability_install("CFO", missing)
        self.assertEqual(plan["install_mode"], "all")
        self.assertEqual(plan["default_option"], "install_all")
        self.assertEqual(plan["install"], missing)
        picked = o.propose_capability_install("CFO", missing, mode="selected",
                                              selected=[missing[0]], owner_approved=True)
        self.assertEqual(picked["install"], [missing[0]])
        self.assertFalse(o.propose_capability_install("CFO", missing, mode="selected",
                                                      selected=["not a capability"])["valid"])


class OptInBusinessData(unittest.TestCase):
    def test_opt_in_lifecycle(self):
        created = o.create_business_data_opt_in(["Harbor & Pine Q4 sales"], "Q4 closeout brief", expires_minutes=60)
        self.assertTrue(created["valid"])
        token = created["opt_in"]["token"]
        self.assertTrue(o.check_business_data_opt_in(token, "Harbor & Pine Q4 sales"))
        self.assertFalse(o.check_business_data_opt_in(token, "Other business bank statements"))
        o.audit_business_data_read(token, "Harbor & Pine Q4 sales", True)
        self.assertTrue(any(e.get("event") == "business_data_read" for e in o.OPTIN_AUDIT_LOG))
        revoked = o.revoke_business_data_opt_in(token)
        self.assertTrue(revoked["valid"])
        self.assertFalse(o.check_business_data_opt_in(token, "Harbor & Pine Q4 sales"))

    def test_opt_in_requires_fields_and_purpose(self):
        self.assertFalse(o.create_business_data_opt_in([], "x")["valid"])
        self.assertFalse(o.create_business_data_opt_in(["a"], "")["valid"])


class LingFix(unittest.TestCase):
    def test_bare_ling_not_listed_as_free(self):
        from models import get_model
        worker2 = get_model("free_worker_2")
        self.assertEqual(worker2["openrouter_id"], "inclusionai/ling-3.1-flash:free")
        self.assertNotIn("zero-priced, no :free suffix", worker2["cost"])


class SlashCommandsRegistered(unittest.TestCase):
    def test_twentyone_commands_registered(self):
        import importlib.util
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("ceo_pack_cmd_test", root / "__init__.py",
                                                      submodule_search_locations=[str(root)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules["ceo_pack_cmd_test"] = pkg
        spec.loader.exec_module(pkg)

        seen = []

        class Ctx:
            def register_tool(self, **kw):
                pass

            def register_hook(self, *a, **kw):
                pass

            def register_skill(self, *a, **kw):
                pass

            def register_command(self, name, fn, description=""):
                seen.append(name)

        pkg.register(Ctx())
        for name in ["ceo", "q4", "orchestrate", "brief", "assign", "verify", "log",
                     "decision", "route", "models", "weekly-pulse", "closeout",
                     "q1", "q2", "q3", "monthly-closeout", "daily-checks", "eod-checks",
                     "performance-checks", "status-check", "roster"]:
            self.assertIn(name, seen, name)
        self.assertEqual(len(seen), 21)


if __name__ == "__main__":
    unittest.main()


class CloseoutsAndChecks(unittest.TestCase):
    """v0.4.0 Q6: Q1-Q3 + monthly closeouts, daily/EOD, performance, status, roster."""

    def test_closeout_quarters_and_monthly(self):
        for q in ("Q1", "Q2", "Q3", "Q4", "monthly"):
            out = call(tools.ceo_closeout_checklist, quarter=q, year=2026)
            self.assertEqual(out["quarter"], q, q)
            self.assertTrue(out["checklist"], q)
            self.assertTrue(o.verify_result("ceo_closeout_checklist", out)["verified"], q)
        self.assertEqual(call(tools.ceo_closeout_checklist, quarter="q1", year=2026)["quarter"], "Q1")
        self.assertEqual(call(tools.ceo_closeout_checklist, quarter="Q5", year=2026)["status"], "error")

    def test_q4_delegates_to_generalized_closeout(self):
        old = call(tools.q4_closeout_checklist, year=2026)
        new = call(tools.ceo_closeout_checklist, quarter="Q4", year=2026)
        self.assertEqual(old["checklist"], new["checklist"])
        self.assertEqual(old["year"], new["year"])

    def test_daily_and_eod_checks(self):
        d = call(tools.ceo_daily_check, period="daily")
        self.assertEqual(d["period"], "daily")
        self.assertTrue(d["checklist"])
        e = call(tools.ceo_daily_check, period="eod")
        self.assertEqual(e["period"], "eod")
        self.assertNotEqual(d["checklist"], e["checklist"])
        self.assertEqual(call(tools.ceo_daily_check, period="weekly")["status"], "error")
        self.assertTrue(o.verify_result("ceo_daily_check", d)["verified"])

    def test_performance_check_is_gated(self):
        out = call(tools.ceo_performance_check, subject="Rosa the bookkeeper")
        self.assertTrue(out["approval_required"])
        self.assertEqual(out["inferred_risk"], ["people"])
        self.assertTrue(out["review"])
        self.assertTrue(o.verify_result("ceo_performance_check", out)["verified"])

    def test_status_check_needs_an_item(self):
        unknown = call(tools.ceo_status_check, item_type="assignment", reference="run-abc123")
        self.assertEqual(unknown["status"], "unknown")
        real = json.loads(tools.ceo_assign({"task": "Reconcile books", "seat": "CFO", "due_date": "2030-01-01"}))
        checked = call(tools.ceo_status_check, item_type="assignment", reference="run-abc123",
                       tool_name="ceo_assign", result=real)
        self.assertEqual(checked["status"], "success")
        self.assertTrue(checked["verified"])
        self.assertEqual(call(tools.ceo_status_check, item_type="vibes")["status"], "error")

    def test_roster_view_and_display_config_all_three(self):
        ok, err = o.set_seat_display("COO", display_name="Poseidon", avatar="poseidon.png", soul="Calm, steady operator who keeps the cadence.")
        self.assertTrue(ok, err)
        ok, err = o.set_seat_binding("COO", profile="hermes-coo", provided=["coordinate across seats", "track due dates", "escalate blocked steps"])
        self.assertTrue(ok, err)
        try:
            view = call(tools.ceo_roster)
            self.assertEqual(len(view["seats"]), 8)
            coo = [s for s in view["seats"] if s["seat"] == "COO"][0]
            self.assertEqual(coo["display_name"], "Poseidon")
            self.assertEqual(coo["avatar"], "poseidon.png")
            self.assertIn("Calm", coo["soul"])
            self.assertEqual(coo["profile"], "hermes-coo")
            self.assertEqual(coo["binding"], "full")
            self.assertEqual(coo["missing"], [])
            self.assertTrue(o.verify_result("ceo_roster", view)["verified"])
        finally:
            o.set_seat_binding("COO", profile=None)
            o.set_seat_display("COO", display_name="", avatar="", soul="")
        revoked = call(tools.ceo_roster)
        coo2 = [s for s in revoked["seats"] if s["seat"] == "COO"][0]
        self.assertFalse(coo2["bound"])
        self.assertEqual(coo2["binding"], "reference")
