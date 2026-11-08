"""Deterministic walkthrough of the orchestration layer, for the hackathon video.

Run from the plugin root:  python demo/demo_flow.py
Uses only fictional inputs. No network, no files written, no credentials.
"""
import json
import os
import sys
import types
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if not os.path.exists(os.path.join(ROOT, "models.py")):  # demo-only stand-in
    stub = types.ModuleType("models")
    stub.choose_model = lambda task_type="ceo", budget="free": {
        "recommended": f"(model chosen by models.py: {budget})", "rule": "CEO seat gets the orchestration model."}
    sys.modules["models"] = stub

import orchestration as o  # noqa: E402

TODAY = date(2026, 11, 4)


def show(title, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, indent=2))


print("CEO PACK — orchestration demo")
print("Flow:", " -> ".join(o.FLOW))

plan = o.plan_tool_calls("Q4 closeout for Example Co")
print("\n[1] PLAN")
for s in plan["steps"]:
    gate = "OWNER APPROVAL" if s["approval_required"] else "proceeds"
    print(f"  {s['step']}. {s['tool']:<22} {s['seat']:<26} {gate}")

show("[2] GOOD CALL — Type 2, reversible, assigned and validated",
     o.make_tool_call("ceo_assign",
                      {"task": "Reconcile books", "seat": "Hermes", "due_date": "2026-11-15"}, today=TODAY))

show("[3] TYPE 1 — external + priced stops for the owner",
     o.make_tool_call("ceo_brief", {"goal": "Send quote to client"}, risk={"external": True, "priced": True}))

show("[4] GUESSED TOOL — refused, not guessed",
     o.make_tool_call("ceo_send_money", {"amount": 100}))

show("[5] SECRET IN ARGUMENTS — refused, value never echoed",
     o.make_tool_call("ceo_brief", {"notes": "use sb_secret_FAKE123 to fix it"}))

show("[6] MISSING DUE DATE — error, not a silent default",
     o.make_tool_call("ceo_assign", {"task": "File report", "seat": "CLO"}, today=TODAY))

show("[7] VERIFY — an envelope is not a completed call",
     o.verify_result("ceo_assign", o.make_tool_call("ceo_assign",
                     {"task": "x", "seat": "CFO", "due_date": "2026-11-20"}, today=TODAY)))

show("[8] RETRY RULES — a failed write never retries blindly",
     {"read_tool_first_error": o.next_action("ceo_brief", "error", 0),
      "write_tool_error": o.next_action("ceo_assign", "error", 0),
      "gated": o.next_action("ceo_decision_log", "needs_approval")})
