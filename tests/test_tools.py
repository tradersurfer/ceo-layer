"""Standalone test for CEO Pack tools. Run: python3 tests/test_tools.py"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools


def check(name, out, key=None):
    data = json.loads(out)
    assert "error" not in data, f"{name} failed: {data}"
    if key:
        assert data.get(key), f"{name} missing {key}: {data}"
    print(f"ok: {name} -> {data}")


check("ceo_brief", tools.ceo_brief({"goal": "Close the year cleanly"}), "workstreams")
check("ceo_assign", tools.ceo_assign({"task": "Reconcile books", "seat": "CFO", "due_date": "2026-11-15"}), "owner")
check("ceo_decision_log", tools.ceo_decision_log({"decision": "Closeout order", "chosen": "Books first"}), "chosen")
check("ceo_route", tools.ceo_route({"task": "Review contracts", "domain": "legal"}), "routed_to")
check("q4_closeout", tools.q4_closeout_checklist({"year": 2026}), "checklist")
print("All CEO Pack tool tests passed.")
# v0.3.0: plan is 6 steps for a non-Q4 goal, 7 with the Q4 checklist for a Q4 goal
plan = json.loads(tools.ceo_orchestrate({"goal": "Launch the weekly review"}))
assert [s["tool"] for s in plan["steps"]] == ["ceo_brief", "ceo_route", "ceo_assign", "ceo_tool_call", "ceo_verify", "ceo_decision_log"], plan["steps"]
print("ok: ceo_orchestrate non-Q4 plan is 6 steps with Verify")
plan_q4 = json.loads(tools.ceo_orchestrate({"goal": "Q4 closeout for the business"}))
assert plan_q4["steps"][-1]["tool"] == "q4_closeout_checklist", plan_q4["steps"]
print("ok: ceo_orchestrate Q4 plan adds the checklist as step 7")
check("ceo_orchestrate", tools.ceo_orchestrate({"goal": "Close Q4 cleanly"}), "steps")
check("ceo_choose_model", tools.ceo_choose_model({"task_type": "ceo", "budget": "free"}), "recommended")
check("ceo_tool_call", tools.ceo_tool_call({"tool_name": "ceo_assign", "arguments": {"task": "Reconcile books", "seat": "CFO", "due_date": "2026-11-15"}}), "valid")
check("ceo_verify", tools.ceo_verify({"tool_name": "ceo_brief", "result": {"status": "success", "brief": "x"}, "expect": ["brief"]}), "verified")
# v0.3.0: Type 2 assign is NOT blanket-gated; Type 1 via risk IS gated
t2 = json.loads(tools.ceo_tool_call({"tool_name": "ceo_assign", "arguments": {"task": "Reconcile books", "seat": "CFO", "due_date": "2026-11-15"}}))
assert t2["approval_required"] is False, t2
t1 = json.loads(tools.ceo_tool_call({"tool_name": "ceo_brief", "arguments": {"goal": "Send quote"}, "risk": {"external": True, "priced": True}}))
assert t1["approval_required"] is True and t1["decision"]["type"] == "Type 1", t1
print("ok: Type 2 proceeds, Type 1 gates")
# v0.3.0: nested secret values are refused and never echoed
nested = json.loads(tools.ceo_tool_call({"tool_name": "ceo_brief", "arguments": {"meta": {"notes": "use sb_secret_FAKE123"}}}))
assert nested["valid"] is False and "sb_secret_FAKE123" not in str(nested), nested
print("ok: nested secret value refused, value never echoed")
# v0.3.0: ceo_assign handler itself validates date and seat
assert "error" in json.loads(tools.ceo_assign({"task": "x", "seat": "CFO", "due_date": "11/15/2026"}))
assert "error" in json.loads(tools.ceo_assign({"task": "x", "seat": "Intern", "due_date": "2026-11-15"}))
print("ok: ceo_assign handler validates ISO date and known seat")
# Rejected tool calls must fail closed, not guess
bad = json.loads(tools.ceo_tool_call({"tool_name": "shell_exec", "arguments": {}}))
assert bad["valid"] is False, f"unknown tool should be refused: {bad}"
print("ok: ceo_tool_call rejects unknown tools")
bad2 = json.loads(tools.ceo_tool_call({"tool_name": "ceo_assign", "arguments": {"api_key": "x"}}))
assert bad2["valid"] is False, f"credential keys should be refused: {bad2}"
print("ok: ceo_tool_call rejects credential keys")
print("All CEO Pack orchestration tests passed.")
