"""Tool handlers — pure, stdlib-only, no network, no file writes.

Handlers always return a JSON string, even on error, and never raise.
They do not read credentials, business data, or files outside this plugin.
Approval is a flag in the output: the host/agent must still obtain the
owner's approval before any external, priced, or shipped action.
"""

import json

SEATS = {
    "ceo": "CEO",
    "cfo": "CFO",
    "coo": "COO (Hermes)",
    "cto": "CTO",
    "cmo": "CMO",
    "clo": "CLO",
    "chief of staff": "Chief of Staff",
    "cro": "CRO",
}

DOMAIN_TO_SEAT = {
    "finance": "CFO",
    "accounting": "CFO",
    "tax": "CFO",
    "bookkeeping": "CFO",
    "operations": "COO (Hermes)",
    "ops": "COO (Hermes)",
    "technology": "CTO",
    "engineering": "CTO",
    "marketing": "CMO",
    "brand": "CMO",
    "content": "CMO",
    "legal": "CLO",
    "compliance": "CLO",
    "contracts": "CLO",
    "people": "Chief of Staff",
    "hiring": "Chief of Staff",
    "revenue": "CRO",
    "sales": "CRO",
    "strategy": "CEO",
    "research": "CEO",
}


def _ok(payload):
    return json.dumps(payload)


def _err(message):
    return json.dumps({"error": message})


def ceo_brief(args, **kwargs):
    goal = (args or {}).get("goal", "").strip()
    if not goal:
        return _err("No goal provided")
    business = (args or {}).get("business_name", "").strip()
    return _ok(
        {
            "goal": goal,
            "business_name": business or None,
            "decision_needed": "Owner to confirm the goal, the budget, and the approval gate.",
            "workstreams": [
                {"seat": "CEO", "job": "Hold priorities and the decision log."},
                {"seat": "CFO", "job": "Numbers, costs, and financial impact."},
                {"seat": "COO (Hermes)", "job": "Execution, coordination, and operating cadence."},
                {"seat": "CTO", "job": "Technology, data, and security."},
                {"seat": "CMO", "job": "Market, brand, and customer message."},
                {"seat": "CLO", "job": "Legal, contracts, and compliance."},
            ],
            "approval_required": True,
            "next_step": "Assign one owner and one due date per workstream with ceo_assign.",
        }
    )


def ceo_assign(args, **kwargs):
    """Assign with the same validation as the orchestration envelope.

    Required fields, a real ISO YYYY-MM-DD due date, and a known seat.
    Hermes and COO (Hermes) both map to COO, displayed as COO (Hermes)
    to match ceo_route. A past due date warns, it does not fail.
    """
    import re
    from datetime import date as _date

    task = (args or {}).get("task", "")
    seat_raw = (args or {}).get("seat", "")
    due = (args or {}).get("due_date", "")
    if not isinstance(task, str) or not task.strip():
        return _err("Need task, seat, and due_date")
    if not isinstance(seat_raw, str) or not seat_raw.strip():
        return _err("Need task, seat, and due_date")
    if not isinstance(due, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        return _err("due_date must be ISO format YYYY-MM-DD")
    try:
        due_parsed = _date.fromisoformat(due)
    except ValueError:
        return _err("due_date is not a real calendar date")
    seat_key = re.sub(r"\(.*?\)", "", seat_raw).strip().lower()
    if seat_key == "hermes":
        seat_key = "coo"
    if seat_key not in SEATS:
        return _err(f"Unknown seat. Valid seats: CEO, CFO, COO, CTO, CMO, CLO, Chief of Staff, CRO (Hermes = COO)")
    seat = SEATS[seat_key]
    payload = {
        "task": task.strip(),
        "owner": seat,
        "due_date": due,
        "status": "assigned",
        "approval_required": seat in ("CEO",) or "external" in task.lower(),
        "note": "Assignment only. Execution and any external action still need owner approval where flagged.",
    }
    if due_parsed < _date.today():
        payload["warning"] = "due_date is in the past."
    return _ok(payload)


def ceo_decision_log(args, **kwargs):
    decision = (args or {}).get("decision", "").strip()
    chosen = (args or {}).get("chosen", "").strip()
    if not decision or not chosen:
        return _err("Need decision and chosen")
    needs = (args or {}).get("needs_approval")
    if needs is None:
        needs = True
    return _ok(
        {
            "decision": decision,
            "options": (args or {}).get("options") or [],
            "chosen": chosen,
            "reason": (args or {}).get("reason", ""),
            "needs_approval": bool(needs),
            "status": "awaiting_owner_approval" if needs else "recorded",
        }
    )


def ceo_route(args, **kwargs):
    task = (args or {}).get("task", "").strip()
    if not task:
        return _err("No task provided")
    domain = ((args or {}).get("domain") or "").strip().lower()
    seat = DOMAIN_TO_SEAT.get(domain)
    if not seat:
        lowered = task.lower()
        seat = "CEO"
        for key, value in DOMAIN_TO_SEAT.items():
            if key in lowered:
                seat = value
                break
    return _ok(
        {
            "task": task,
            "domain": domain or None,
            "routed_to": seat,
            "why": "Domain match in the task router. CEO retains accountability for the integrated result.",
            "approval_required": True,
        }
    )


def q4_closeout_checklist(args, **kwargs):
    year = (args or {}).get("year")
    if not year:
        return _err("Need year")
    return _ok(
        {
            "year": year,
            "entity_type": (args or {}).get("entity_type"),
            "disclaimer": "Checklist only, not tax or legal advice. Confirm with a qualified professional.",
            "checklist": [
                "Reconcile books and close the year in your accounting system.",
                "Review individual, income, corporate, sales & use, payroll, and excise tax items that apply to you.",
                "Prepare year-end annual filings and confirm deadlines and jurisdictions.",
                "Review entity structure; list restructuring or cleanup items, if any.",
                "Prepare annual reporting: what shipped, what earned, what is stuck, what needs a decision.",
                "Confirm no external filing, payment, or publication goes out without owner approval.",
            ],
            "owners": {
                "CFO": "Books, numbers, and tax preparation.",
                "CLO": "Entity, filings, and compliance.",
                "COO (Hermes)": "Coordination and operating cadence.",
                "CRO": "Revenue pipeline for potential clients, if applicable.",
            },
        }
    )


# --- Orchestration + model choice (added in v0.2.0) ---

def ceo_orchestrate(args, **kwargs):
    goal = (args or {}).get("goal", "").strip()
    if not goal:
        return _err("No goal provided")
    try:
        try:
            from .orchestration import plan_tool_calls
        except ImportError:
            from orchestration import plan_tool_calls

        plan = plan_tool_calls(goal, (args or {}).get("model_key", "free_default"))
    except Exception as exc:  # pragma: no cover - fallback for direct import
        return _err(f"Orchestration unavailable: {exc}")
    return _ok(plan)


def ceo_choose_model(args, **kwargs):
    try:
        try:
            from .models import choose_model
        except ImportError:
            from models import choose_model

        result = choose_model(
            task_type=(args or {}).get("task_type", "ceo"),
            budget=(args or {}).get("budget", "free"),
        )
    except Exception as exc:
        return _err(f"Model choice unavailable: {exc}")
    result["provider_requested"] = (args or {}).get("provider", "auto")
    return _ok(result)


def ceo_tool_call(args, **kwargs):
    tool_name = (args or {}).get("tool_name", "")
    if not isinstance(tool_name, str):
        return _err("Need tool_name and arguments")
    tool_name = tool_name.strip()
    arguments = (args or {}).get("arguments")
    seat = (args or {}).get("seat", "CEO")
    risk = (args or {}).get("risk")
    if not tool_name or arguments is None:
        return _err("Need tool_name and arguments")
    try:
        try:
            from .orchestration import make_tool_call
        except ImportError:
            from orchestration import make_tool_call

        return _ok(make_tool_call(tool_name, arguments, seat, risk=risk if isinstance(risk, dict) else None))
    except Exception as exc:
        return _err(f"Tool-call validation unavailable: {exc}")


def ceo_verify(args, **kwargs):
    """Verify a tool result before anyone reports the step as done.

    Handler body per the v0.3.0 handoff: call verify_result and return
    its dict as JSON. A validated envelope is not a completed call.
    """
    tool_name = (args or {}).get("tool_name", "")
    if not isinstance(tool_name, str):
        return _err("Need tool_name and result")
    tool_name = tool_name.strip()
    result = (args or {}).get("result")
    expect = (args or {}).get("expect")
    retries_used = (args or {}).get("retries_used", 0)
    if not tool_name or result is None:
        return _err("Need tool_name and result")
    try:
        try:
            from .orchestration import verify_result
        except ImportError:
            from orchestration import verify_result

        return _ok(verify_result(tool_name, result, expect=expect, retries_used=retries_used or 0))
    except Exception as exc:
        return _err(f"Verification unavailable: {exc}")
