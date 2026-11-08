"""Orchestration layer — the core of CEO Pack (v0.3.0).

This is not a chat wrapper. It is a small, explicit protocol:

    Brief -> Route -> Plan -> Assign -> Call -> Verify -> Log

1. Brief  — state the goal, the decision, and the approval gate.
2. Route  — pick one seat by domain. CEO retains accountability.
3. Plan   — an ordered list of tool calls, each with a seat, a tool,
            and a way to verify it.
4. Assign — one owner, one due date per step.
5. Call   — one tool at a time. Validate the envelope first.
6. Verify — check the returned JSON. A call that started is not a call
            that completed.
7. Log    — record the decision after the outcome is verified.

Type 1 vs Type 2 (adapted from the public ceo-agent CEO prompt):
- Type 1: irreversible, difficult to unwind, high-cost, high-impact,
  outside assigned authority, or materially legal, financial, security,
  people, regulatory, or reputation-sensitive. Escalate to the owner.
- Type 2: reversible, low-cost, bounded, within assigned authority.
  Decide promptly, do not build an unnecessary approval queue.

Tool-call protocol (what a caller must do, every time):
- Name the exact tool, not a vague action. Unknown tools are refused.
- Pass arguments as a JSON object, with required fields present.
- Never pass credentials in arguments. Keys AND values are scanned,
  including nested ones. Errors name the path, never the value.
- Check the returned JSON: success, error, or blocked — never assume.
- On error: retry once with a corrected argument, then escalate.
  Never retry a write, send, payment, or deletion blindly.
- On blocked / needs_approval: stop, surface the reason, wait for the owner.

This module is pure standard library. No network, no file writes, no
credential reads. It validates and advises; it does not execute tools.
"""

import json
import re
from datetime import date

try:
    from .models import choose_model
except ImportError:  # running outside the package (tests, demo scripts)
    from models import choose_model

FLOW = ["Brief", "Route", "Plan", "Assign", "Call", "Verify", "Log"]

SEATS = ["CEO", "CFO", "COO", "CTO", "CMO", "CLO", "Chief of Staff", "CRO"]

ALLOWED_TOOLS = [
    "ceo_brief",
    "ceo_route",
    "ceo_assign",
    "ceo_decision_log",
    "ceo_orchestrate",
    "ceo_choose_model",
    "ceo_tool_call",
    "ceo_verify",  # NEW in 0.3.0 — must be registered in __init__.py
    "q4_closeout_checklist",
]

# Tools whose result always needs an owner decision. A log entry is NOT approval.
APPROVAL_TOOLS = {"ceo_decision_log", "q4_closeout_checklist"}

# Tools treated as state-changing. Never retried blindly.
# ceo_assign only: ceo_decision_log only returns JSON in this plugin
# (no file/memory write), so a failed decision-log call may retry once safely.
SIDE_EFFECT_TOOLS = {"ceo_assign"}

# Required argument fields per tool, synced with schemas.py.
# ceo_choose_model has no required fields, so it is intentionally absent.
REQUIRED_ARGS = {
    "ceo_brief": ["goal"],
    "ceo_assign": ["task", "seat", "due_date"],
    "ceo_decision_log": ["decision", "chosen"],
    "ceo_route": ["task"],
    "q4_closeout_checklist": ["year"],
    "ceo_orchestrate": ["goal"],
    "ceo_tool_call": ["tool_name", "arguments"],
    "ceo_verify": ["tool_name", "result"],
}

MAX_RETRIES = 1

RISK_FLAGS = (
    "external",
    "priced",
    "irreversible",
    "legal_or_financial",
    "security",
    "people",
    "regulatory",
    "reputation",
    "outside_authority",
)

_BANNED_KEY_PARTS = (
    "api_key", "apikey", "password", "passwd", "token", "secret",
    "credential", "private_key", "authorization", "bearer",
)
_SAFE_KEYS = {"max_tokens", "token_budget", "token_count", "tokens_used"}

_SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),                       # generic sk- keys
    re.compile(r"\bsb_secret_[A-Za-z0-9_\-]+"),                    # Supabase secret keys
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),                   # GitHub tokens
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                           # AWS access key IDs
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),                # Slack tokens
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),  # JWTs
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

_Q4_GOAL = re.compile(r"\b(q4|year[- ]?end|close[- ]?out|closeout|tax|annual filing)\b", re.I)


# --------------------------------------------------------------------------
# Decisions
# --------------------------------------------------------------------------

def classify_decision(
    external=False,
    priced=False,
    irreversible=False,
    legal_or_financial=False,
    security=False,
    people=False,
    regulatory=False,
    reputation=False,
    outside_authority=False,
):
    """Return Type 1 or Type 2, with the reason and the flags that triggered it."""
    flags = {
        "external": external,
        "priced": priced,
        "irreversible": irreversible,
        "legal_or_financial": legal_or_financial,
        "security": security,
        "people": people,
        "regulatory": regulatory,
        "reputation": reputation,
        "outside_authority": outside_authority,
    }
    triggers = [name for name, on in flags.items() if on]
    if triggers:
        return {
            "type": "Type 1",
            "action": "escalate_to_owner",
            "reason": "External, priced, irreversible, or materially legal/financial — outside unilateral authority.",
            "triggers": triggers,
        }
    return {
        "type": "Type 2",
        "action": "decide_and_act",
        "reason": "Reversible, low-cost, bounded, within assigned authority.",
        "triggers": [],
    }


# --------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------

def _step(n, tool, seat, verify_by, approval_required=False):
    return {
        "step": n,
        "tool": tool,
        "seat": seat,
        "approval_required": approval_required,
        "verify_by": verify_by,
    }


def _pick_model(model_key):
    """Resolve the model choice without crashing the plan on a bad key."""
    try:
        if model_key:
            try:
                from .models import get_model
            except ImportError:
                from models import get_model
            exact = get_model(model_key)
            if exact is not None:
                return {
                    "recommended": exact,
                    "rule": "Model chosen by install config. CEO seat gets the orchestration model; workers get fast, narrow models.",
                    "fallbacks": [],
                }
        if not model_key or model_key == "free_default":
            return choose_model(task_type="ceo")
        budget = model_key if str(model_key).startswith("paid") else "free"
        return choose_model(task_type="ceo", budget=budget)
    except Exception:  # unknown key -> fall back to the safe default
        return choose_model(task_type="ceo")


def plan_tool_calls(goal, model_key="free_default"):
    """Return an ordered orchestration plan for a goal."""
    if not isinstance(goal, str) or not goal.strip():
        return {"valid": False, "error": "A non-empty goal is required to plan.", "status": "error"}

    model = _pick_model(model_key)
    steps = [
        _step(1, "ceo_brief", "CEO", "Brief states goal, decision needed, and approval gate."),
        _step(2, "ceo_route", "CEO", "Each workstream has one named seat."),
        _step(3, "ceo_assign", "CEO", "Each task has one owner and one due date."),
        _step(4, "ceo_tool_call", "Assigned seat",
              "Envelope validated, tool called once, JSON result returned."),
        _step(5, "ceo_verify", "CEO",
              "Result status is success AND expected fields are present. Started is not completed."),
        _step(6, "ceo_decision_log", "CEO",
              "Decision, options, chosen option, and reason are recorded.", approval_required=True),
    ]
    if _Q4_GOAL.search(goal):
        steps.append(_step(7, "q4_closeout_checklist", "CFO / CLO / COO (Hermes)",
                           "Checklist is complete, and no external filing goes out without owner approval.",
                           approval_required=True))
    return {
        "goal": goal.strip(),
        "model": model["recommended"],
        "model_rule": model["rule"],
        "flow": " -> ".join(FLOW),
        "steps": steps,
        "approval_gate": "Type 1 steps and any step marked approval_required stop on blocked / needs_approval. "
                         "No auto-approval, no YOLO bypass.",
        "approval_rule": "Classify every call. Type 1 (external, priced, irreversible, legal/financial, "
                         "security, people, regulatory, reputation) stops for the owner. Type 2 proceeds.",
        "retry_rule": "Retry a failed tool call once with corrected arguments, then escalate. "
                      "Never retry a write/send/payment blindly.",
        "retry_policy": {"max_retries": MAX_RETRIES, "side_effect_tools": sorted(SIDE_EFFECT_TOOLS)},
    }


# --------------------------------------------------------------------------
# Tool-call envelope
# --------------------------------------------------------------------------

def normalize_seat(seat):
    """Map a seat string to a canonical seat, or None. 'Hermes' is the COO."""
    if not isinstance(seat, str):
        return None
    s = re.sub(r"\(.*?\)", "", seat)
    s = re.sub(r"\s+", " ", s).strip().upper()
    if s == "HERMES":
        return "COO"
    if s == "COS":
        return "Chief of Staff"
    for canonical in SEATS:
        if canonical.upper() == s:
            return canonical
    return None


def _is_secret_key(key):
    k = key.lower()
    if k in _SAFE_KEYS:
        return False
    return any(part in k for part in _BANNED_KEY_PARTS)


def find_secret_paths(obj, path="arguments", _depth=0):
    """Return the PATHS (never the values) of anything credential-like, nested included."""
    hits = []
    if _depth > 20:
        return hits
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}"
            if _is_secret_key(str(key)):
                hits.append(here)
            hits.extend(find_secret_paths(value, here, _depth + 1))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            hits.extend(find_secret_paths(value, f"{path}[{i}]", _depth + 1))
    elif isinstance(obj, str):
        if any(p.search(obj) for p in _SECRET_VALUE_PATTERNS):
            hits.append(path)
    seen, ordered = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            ordered.append(h)
    return ordered


def _fail(tool_name, message, retryable=True):
    return {
        "valid": False,
        "status": "error",
        "error": message,
        "tool": tool_name,
        "executed": False,   # rejected before anything ran, so a corrected retry is safe
        "retryable": retryable,
    }


def _check_due_date(value, today=None):
    """Return (ok, warning_or_error)."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False, "due_date must be ISO format YYYY-MM-DD."
    try:
        due = date.fromisoformat(value)
    except ValueError:
        return False, "due_date is not a real calendar date."
    if due < (today or date.today()):
        return True, "due_date is in the past."
    return True, None


def make_tool_call(tool_name, arguments, seat="CEO", risk=None, today=None):
    """Validate a tool call envelope. This does not execute an external tool.

    risk  — optional dict of Type 1 flags (see RISK_FLAGS) for this specific call.
    today — injectable date, for tests.
    """
    if tool_name not in ALLOWED_TOOLS:
        return _fail(tool_name,
                     f"Unknown tool: {tool_name}. Allowed: {', '.join(ALLOWED_TOOLS)}. Not guessing.",
                     retryable=False)

    warnings = []
    if isinstance(arguments, str):  # models often send a JSON string; accept it if it parses
        try:
            arguments = json.loads(arguments)
            warnings.append("arguments arrived as a JSON string and were parsed.")
        except ValueError:
            return _fail(tool_name, "Arguments string is not valid JSON.")
    if not isinstance(arguments, dict):
        return _fail(tool_name, "Arguments must be a JSON object")

    leaked = find_secret_paths(arguments)
    if leaked:
        return _fail(tool_name,
                     f"Refused: credential-like content at {leaked}. "
                     "Pass secrets through Hermes, never in tool arguments. Values are not echoed.")

    missing = [f for f in REQUIRED_ARGS.get(tool_name, []) if arguments.get(f) in (None, "")]
    if missing:
        return _fail(tool_name, f"Missing required fields: {missing}")

    if tool_name == "ceo_assign":
        assignee = normalize_seat(arguments["seat"])
        if assignee is None:
            return _fail(tool_name, f"Unknown seat. Valid seats: {', '.join(SEATS)} (Hermes = COO).")
        seat = assignee
        ok, note = _check_due_date(arguments["due_date"], today)
        if not ok:
            return _fail(tool_name, note)
        if note:
            warnings.append(note)
    else:
        resolved = normalize_seat(seat)
        if resolved is None:
            return _fail(tool_name, f"Unknown seat. Valid seats: {', '.join(SEATS)} (Hermes = COO).")
        seat = resolved

    decision = classify_decision(**{k: bool(v) for k, v in (risk or {}).items() if k in RISK_FLAGS})
    needs_owner = tool_name in APPROVAL_TOOLS or decision["type"] == "Type 1"

    envelope = {
        "valid": True,
        "tool": tool_name,
        "seat": seat,
        "arguments": arguments,
        "dispatch": "Call this tool once, check its JSON result with ceo_verify, then move to the next step or escalate.",
        "approval_required": needs_owner,
        "decision": decision,
        "side_effect": tool_name in SIDE_EFFECT_TOOLS,
        "retry_policy": {"max_retries": MAX_RETRIES, "blind_retry": False},
    }
    if needs_owner:
        envelope["gate"] = "STOP: owner approval required for this item before dispatch."
    if warnings:
        envelope["warnings"] = warnings
    return envelope


# --------------------------------------------------------------------------
# Verify + retry
# --------------------------------------------------------------------------

def _status_of(result):
    """Read a tool result and return success | error | blocked | needs_approval | unknown."""
    if not isinstance(result, dict):
        return "unknown"
    explicit = result.get("status")
    if isinstance(explicit, str) and explicit in ("success", "error", "blocked", "needs_approval"):
        return explicit
    if result.get("error") or result.get("valid") is False:
        return "error"
    if result.get("blocked"):
        return "blocked"
    if result.get("needs_approval"):
        return "needs_approval"
    if result.get("success") is True:
        return "success"
    return "unknown"


def next_action(tool_name, status, retries_used=0, executed=None):
    """Decide what the caller does next. Never assumes success.

    executed — False when the call was rejected before running (validation),
               True/None when a side effect may have landed.
    """
    if status == "success":
        return {"action": "verify", "reason": "Success reported. Check expected fields before claiming done."}
    if status in ("blocked", "needs_approval"):
        return {"action": "stop_and_wait_for_owner", "reason": "Gated. Surface the reason; do not retry or route around it."}
    if status == "error":
        if retries_used >= MAX_RETRIES:
            return {"action": "escalate", "reason": "Retry budget spent. Escalate to the owner with the error."}
        if tool_name in SIDE_EFFECT_TOOLS and executed is not False:
            return {"action": "escalate",
                    "reason": "State-changing tool failed and may have partly run. Check current state; never retry blindly."}
        return {"action": "retry_once_with_corrected_arguments", "reason": "Fix the argument that caused the error, then call once more."}
    return {"action": "escalate", "reason": "Unrecognized result. Not treating it as success."}


def verify_result(tool_name, result, expect=None, retries_used=0):
    """Check a tool result before anyone reports the step as done.

    result — dict or JSON string returned by the tool.
    expect — field names that must be present for the step to count as complete.
    """
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            result = None
    status = _status_of(result)
    missing = []
    if status == "success" and expect:
        missing = [f for f in expect if f not in result or result[f] in (None, "")]
    verified = status == "success" and not missing
    executed = result.get("executed") if isinstance(result, dict) else None
    nxt = next_action(tool_name, "error" if (status == "success" and missing) else status,
                      retries_used=retries_used, executed=executed)
    return {
        "tool": tool_name,
        "status": status,
        "verified": verified,
        "missing_fields": missing,
        "next": nxt,
    }
