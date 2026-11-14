"""Orchestration layer — the core of CEO Pack (v0.4.0).

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

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

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
    "ceo_closeout_checklist",  # v0.4.0: Q1-Q4 + monthly closeout
    "ceo_daily_check",  # v0.4.0: daily / EOD checks
    "ceo_performance_check",  # v0.4.0: employee performance
    "ceo_status_check",  # v0.4.0: status of a briefing / assignment / task / log
    "ceo_roster",  # v0.4.0: C-Suite roster view for install flow + CEO Dashboard pin
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
    "ceo_closeout_checklist": ["year"],
    "ceo_daily_check": ["period"],
    "ceo_performance_check": ["subject"],
    "ceo_status_check": ["item_type"],
    "ceo_roster": [],
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

# Key hints are compared in squashed form (lowercase, letters and digits only),
# so api_key, API-KEY, "api key", and zero-width-split variants all match.
_BANNED_KEY_PARTS = (
    "apikey", "password", "passwd", "passphrase", "pwd", "token", "secret",
    "credential", "privatekey", "authorization", "bearer", "accesskey",
    "cookie", "sshkey",
)
_SAFE_KEYS = {"maxtokens", "tokenbudget", "tokencount", "tokensused"}

_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)

_SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bsb_secret_[A-Za-z0-9_\-]+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"\bwhsec_[A-Za-z0-9]{16,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}"),
    re.compile(r"\bnpm_[A-Za-z0-9]{30,}"),
    re.compile(r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-~+/]{20,}=*"),
    re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s@/]+@"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|pwd|token)\b\s*[:=]\s*[\"']?[^\s\"',;]{6,}"),
]

# Text fields scanned for Type 1 cues. Content can only RAISE a call to Type 1.
_RISK_TEXT_FIELDS = ("task", "goal", "decision", "chosen", "reason", "notes", "options")

_RISK_CUES = {
    "legal_or_financial": re.compile(
        r"\b(pay(?:ing|ment|ments)?\b(?!\s+attention)|wire|wiring|transfer funds?|refund(?:s|ing)?|"
        r"payroll|sign(?:ing)?\s+(?:the|a|an|our|this)?\s*(?:contract|agreement|nda|lease|offer)|"
        r"countersign|loan|borrow|invest(?:ing|ment)?|buy\s+(?:crypto|bitcoin|stock|shares))\b", re.I),
    "external": re.compile(
        r"\b(?:send|email|post|publish|announce|submit|tweet|reply|notify|message)\b"
        r"[^.]{0,60}\b(?:client|customer|vendor|investor|press|public|prospect|partner|board|regulator|irs|"
        r"audience|followers|subscribers|everyone)s?\b|\b(?:publish|announce|go live)\b", re.I),
    "irreversible": re.compile(
        r"\b(?:delete|wipe|destroy|purge|drop\s+(?:table|database)|shut\s?down|decommission|"
        r"cancel\s+(?:the\s+)?(?:account|subscription|contract))\b", re.I),
    "people": re.compile(
        r"\b(?:hire|hiring|fire|firing|terminate|layoff|lay\s?off|promote|demote|discipline|"
        r"salary|compensation|raise\s+for)\b", re.I),
    "regulatory": re.compile(
        r"\b(?:irs|sec\s+filing|tax\s+(?:return|filing)|file\s+(?:the\s+|our\s+|a\s+|my\s+)?(?:\d{4}\s+)?(?:tax(?:es)?|returns?)|"
        r"1099|w-?2|license\s+renewal|regulator\w*\s+filing|annual\s+report\s+filing)\b", re.I),
    "priced": re.compile(
        r"\b(?:set|change|raise|lower|cut|increase|reduce)\b[^.]{0,30}\b(?:price|prices|pricing|rates?)\b", re.I),
    "security": re.compile(
        r"\b(?:rotate|reset|grant|revoke|disable|share)\b[^.]{0,25}\b(?:password|credentials?|keys?|access|permissions?|2fa|mfa)\b", re.I),
    "reputation": re.compile(
        r"\b(?:press\s+release|public\s+statement|apolog(?:y|ize)|respond\s+to\s+(?:the\s+)?(?:press|media|review))\b", re.I),
}

_MAX_DEPTH = 20
_MAX_JSON_STRING = 100_000

EXPECTED_FIELDS = {
    "ceo_brief": ["goal", "workstreams"],
    "ceo_assign": ["task", "owner", "due_date"],
    "ceo_decision_log": ["decision", "chosen"],
    "ceo_route": ["task", "routed_to"],
    "q4_closeout_checklist": ["year", "checklist"],
    "ceo_orchestrate": ["goal", "steps"],
    "ceo_choose_model": ["recommended"],
    "ceo_closeout_checklist": ["quarter", "year", "checklist"],
    "ceo_daily_check": ["period", "checklist"],
    "ceo_performance_check": ["subject", "review"],
    "ceo_status_check": ["item_type", "status"],
    "ceo_roster": ["seats"],
}

# These return validation / verification metadata, not a completed business action.
META_TOOLS = {"ceo_tool_call", "ceo_verify"}

# --- Seat aliases + head CEO (v0.4.0, design note SS1/SS6) ---
# Canonical seats never change. Aliases are display names from install config.
SEAT_ALIASES = {}
HEAD_SEAT = "CEO"


def set_seat_aliases(mapping):
    """Set alias -> canonical seat from install config. Returns (ok, error)."""
    global SEAT_ALIASES
    if mapping is None:
        mapping = {}
    if not isinstance(mapping, dict):
        return False, "seat aliases must be an object mapping a display name to a canonical seat."
    cleaned = {}
    seen_targets = {}
    for alias, target in mapping.items():
        if not isinstance(alias, str) or not alias.strip():
            return False, "seat alias names must be non-empty text."
        if not isinstance(target, str):
            return False, "seat alias target for %r must be a canonical seat name." % alias
        canon = normalize_seat(target)
        if canon is None:
            return False, "Unknown seat %r for alias %r. Valid seats: %s." % (target, alias, ", ".join(SEATS))
        key = alias.strip().upper()
        if key in cleaned and cleaned[key] != canon:
            return False, "Alias %r maps to two seats." % alias
        if canon in seen_targets and seen_targets[canon] != key:
            return False, "Two aliases map to %s; one display name per seat." % canon
        cleaned[key] = canon
        seen_targets[canon] = key
    SEAT_ALIASES = cleaned
    return True, None


def get_seat_aliases():
    return dict(SEAT_ALIASES)


def display_seat(canonical):
    """Show 'Alias (Canonical)' when an alias exists, else the canonical name."""
    for alias, canon in SEAT_ALIASES.items():
        if canon == canonical:
            return "%s (%s)" % (alias.title(), canonical)
    return canonical


def set_head_seat(seat):
    global HEAD_SEAT
    canon = normalize_seat(seat) if isinstance(seat, str) else None
    if canon is None:
        return False, "Unknown head seat %r. Valid seats: %s." % (seat, ", ".join(SEATS))
    HEAD_SEAT = canon
    return True, None


def get_head_seat():
    return HEAD_SEAT


# --- Seat display config + bindings + roster view (v0.4.0, design note SS2/SS4/SS8-Q7) ---
# A binding carries display-only personalization: name + avatar reference +
# SOUL / personality note. All three, per the 2026-11-12 design decision. Display-only:
# nothing here changes routing, gating, or validation, which run on the
# canonical seat. Bindings are config, optional, revocable, per seat.
SEAT_DISPLAY = {}
SEAT_BINDINGS = {}


def set_seat_display(seat, display_name=None, avatar=None, soul=None):
    """Set display config for a seat. All three fields are display-only."""
    canon = normalize_seat(seat) if isinstance(seat, str) else None
    if canon is None:
        return False, "Unknown seat %r. Valid seats: %s." % (seat, ", ".join(SEATS))
    for label, value in (("display_name", display_name), ("avatar", avatar), ("soul", soul)):
        if value is not None and not isinstance(value, str):
            return False, "%s must be text." % label
    entry = dict(SEAT_DISPLAY.get(canon, {}))
    if display_name is not None:
        entry["display_name"] = display_name.strip() or None
    if avatar is not None:
        entry["avatar"] = avatar.strip() or None
    if soul is not None:
        entry["soul"] = soul.strip() or None
    SEAT_DISPLAY[canon] = {k: v for k, v in entry.items() if v}
    return True, None


def get_seat_display(seat):
    canon = normalize_seat(seat) if isinstance(seat, str) else None
    if canon is None:
        return {}
    return dict(SEAT_DISPLAY.get(canon, {}))


def set_seat_binding(seat, profile=None, provided=None):
    """Bind a Hermes profile to a seat. profile: id/name or None to unbind.

    provided: capability strings the profile actually has (for the roster
    view + capability check). Unbinding returns the seat to the reference
    agent; the decision log keeps the canonical seat either way.
    """
    canon = normalize_seat(seat) if isinstance(seat, str) else None
    if canon is None:
        return False, "Unknown seat %r. Valid seats: %s." % (seat, ", ".join(SEATS))
    if profile is None:
        SEAT_BINDINGS.pop(canon, None)
        return True, None
    if not isinstance(profile, str) or not profile.strip():
        return False, "profile must be non-empty text, or None to unbind."
    if provided is not None and (not isinstance(provided, (list, tuple))
                                 or not all(isinstance(x, str) for x in provided)):
        return False, "provided must be a list of capability names."
    SEAT_BINDINGS[canon] = {"profile": profile.strip(),
                            "provided": list(provided or [])}
    return True, None


def get_roster_view():
    """The C-Suite roster: one entry per seat for the install flow and the
    pinned CEO Dashboard. Shows seat, display name, bound profile,
    capabilities and gaps. A seat with no binding uses the reference agent;
    a seat whose profile is missing capabilities is a name-only binding.
    """
    seats = []
    for canon in SEATS:
        disp = get_seat_display(canon)
        binding = SEAT_BINDINGS.get(canon, {})
        provided = binding.get("provided", [])
        check = check_capabilities(canon, provided) if binding else None
        seats.append({
            "seat": canon,
            "display_name": disp.get("display_name") or display_seat(canon).split(" (")[0],
            "display": display_seat(canon),
            "avatar": disp.get("avatar"),
            "soul": disp.get("soul"),
            "profile": binding.get("profile"),
            "bound": bool(binding),
            "capabilities": CAPABILITY_CHECKLISTS.get(canon, []),
            "provided": provided,
            "missing": check["missing"] if check else CAPABILITY_CHECKLISTS.get(canon, []),
            "binding": check["binding"] if check else "reference",
        })
    return {"status": "success", "head_seat": HEAD_SEAT, "seats": seats,
            "note": "Install flow + CEO Dashboard view. Pinning is host behaviour; this is the data to pin."}


# --- Capability checklists (v0.4.0, design note SS3) ---
CAPABILITY_CHECKLISTS = {
    "CEO": ["hold priorities", "make and log decisions", "approve Type 1 items with the human owner as final gate"],
    "CFO": ["read numbers and summaries", "reconcile books", "prepare tax items", "flag budget overruns"],
    "COO": ["coordinate across seats", "track due dates", "escalate blocked steps"],
    "CTO": ["review technical tasks", "check systems and security items", "estimate technical work"],
    "CMO": ["draft campaign plans", "review brand and customer message", "track marketing work"],
    "CLO": ["review contracts", "track filings and deadlines", "flag legal and compliance risk"],
    "Chief of Staff": ["coordinate people tasks", "track hiring and onboarding", "hold team cadence"],
    "CRO": ["track revenue pipeline", "review pricing and quotes", "track prospects and leads"],
}


def check_capabilities(seat, provided):
    """Compare a bound profile's capabilities against the seat checklist.

    provided: list of capability strings the profile actually has.
    Returns a dict with missing items. Never claims a capability exists.
    """
    canon = normalize_seat(seat) if isinstance(seat, str) else None
    if canon is None:
        return {"valid": False, "error": "Unknown seat %r. Valid seats: %s." % (seat, ", ".join(SEATS))}
    if not isinstance(provided, (list, tuple)):
        return {"valid": False, "error": "provided capabilities must be a list of text items."}
    have = {str(x).strip().lower() for x in provided if isinstance(x, str)}
    wanted = CAPABILITY_CHECKLISTS.get(canon, [])
    missing = [c for c in wanted if c.lower() not in have]
    return {"valid": True, "seat": canon, "display_seat": display_seat(canon),
            "provided": sorted(have), "missing": missing,
            "complete": not missing,
            "binding": "full" if not missing else "name-only"}


def propose_capability_install(seat, missing, owner_approved=False, mode="all", selected=None):
    """Return an install plan for missing capabilities. Nothing installs here.

    The plugin has no network and no installer: this returns the exact list
    for the host to install, gated on owner approval. Without approval it
    returns blocked, and the seat stays a name-only binding.
    mode "all" (default): install every missing capability under one approval.
    mode "selected": install only the items in `selected`, each approved
    separately by the user; anything not selected stays missing.
    """
    canon = normalize_seat(seat) if isinstance(seat, str) else None
    if canon is None:
        return {"valid": False, "error": "Unknown seat %r." % (seat,)}
    if not isinstance(missing, (list, tuple)) or not all(isinstance(m, str) for m in missing):
        return {"valid": False, "error": "missing must be a list of capability names."}
    if mode not in ("all", "selected"):
        return {"valid": False, "error": "mode must be 'all' or 'selected'."}
    if mode == "selected":
        if not isinstance(selected, (list, tuple)) or not selected:
            return {"valid": False, "error": "mode 'selected' needs a non-empty list of capabilities to install."}
        unknown = [m for m in selected if m not in missing]
        if unknown:
            return {"valid": False, "error": "Not missing for this seat, cannot install: %s." % unknown}
        install = list(selected)
    else:
        install = list(missing)
    if not install:
        return {"valid": True, "seat": canon, "install": [], "install_mode": mode,
                "default_option": "install_all", "approval_required": False,
                "status": "success", "note": "No missing capabilities; nothing to install."}
    if not owner_approved:
        return {"valid": True, "seat": canon, "install": install, "install_mode": mode,
                "default_option": "install_all",
                "approval_required": True, "status": "needs_approval",
                "gate": "STOP: owner approval required before installing any capability.",
                "note": "Default is install-all under one approval; the user may instead approve each capability separately (mode 'selected'). Name-only binding until the owner approves."}
    return {"valid": True, "seat": canon, "install": install, "install_mode": mode,
            "default_option": "install_all",
            "approval_required": False, "status": "success",
            "note": "Owner approved. Host installs exactly these items, then re-run check_capabilities to confirm."}


# --- Opt-in business-data reading (v0.4.0, design note SS8 / Grok X5) ---
# Ephemeral, in-memory only. No file writes, no standing permission.
# A read is allowed only with a live opt-in naming the exact fields, a
# purpose, and an expiry. Every read is audited; revoke is instant.
OPTIN_AUDIT_LOG = []
_OPTIN_STORE = {}


def create_business_data_opt_in(fields, purpose, expires_minutes=60):
    """Create a chat-scoped opt-in. fields: explicit list. purpose: why."""
    if not isinstance(fields, (list, tuple)) or not fields or not all(isinstance(f, str) and f.strip() for f in fields):
        return {"valid": False, "error": "fields must be a non-empty list of named fields or documents."}
    if not isinstance(purpose, str) or not purpose.strip():
        return {"valid": False, "error": "purpose is required: say what the read is for."}
    try:
        minutes = int(expires_minutes)
    except (TypeError, ValueError):
        return {"valid": False, "error": "expires_minutes must be a number."}
    if minutes <= 0 or minutes > 60 * 24:
        return {"valid": False, "error": "expires_minutes must be between 1 and 1440."}
    now = datetime.now(timezone.utc)
    token = "optin-" + hashlib.sha1(("%s|%s|%s" % (sorted(fields), purpose.strip(), now.isoformat())).encode()).hexdigest()[:12]
    record = {"token": token, "fields": sorted({f.strip() for f in fields}),
              "purpose": purpose.strip(), "created_at": now.isoformat(),
              "expires_at": (now + timedelta(minutes=minutes)).isoformat(),
              "revoked": False}
    _OPTIN_STORE[token] = record
    OPTIN_AUDIT_LOG.append({"event": "opt_in_created", "token": token,
                            "fields": record["fields"], "purpose": record["purpose"],
                            "expires_at": record["expires_at"]})
    return {"valid": True, "status": "success", "opt_in": record,
            "note": "Ephemeral and chat-scoped. A fresh opt-in is required for any future read."}


def check_business_data_opt_in(token, field):
    """True only if a live opt-in covers this exact field right now."""
    rec = _OPTIN_STORE.get(token) if isinstance(token, str) else None
    if not rec or rec.get("revoked"):
        return False
    try:
        if datetime.now(timezone.utc) >= datetime.fromisoformat(rec["expires_at"]):
            return False
    except ValueError:
        return False
    return field in rec.get("fields", [])


def revoke_business_data_opt_in(token):
    rec = _OPTIN_STORE.get(token) if isinstance(token, str) else None
    if not rec:
        return {"valid": False, "error": "Unknown opt-in token."}
    rec["revoked"] = True
    OPTIN_AUDIT_LOG.append({"event": "opt_in_revoked", "token": token})
    return {"valid": True, "status": "success", "token": token, "note": "Revoked. The seat returns to no-read immediately."}


def audit_business_data_read(token, field, allowed):
    OPTIN_AUDIT_LOG.append({"event": "business_data_read", "token": token, "field": field,
                            "allowed": bool(allowed), "at": datetime.now(timezone.utc).isoformat()})
    return {"token": token, "field": field, "allowed": bool(allowed)}


_Q4_GOAL = re.compile(r"\b(q4|year[- ]?end|close[- ]?out|closeout|tax(?:es|ation)?|annual filing)\b", re.I)


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
    head = HEAD_SEAT
    steps = [
        _step(1, "ceo_brief", head, "Brief states goal, decision needed, and approval gate."),
        _step(2, "ceo_route", head, "Each workstream has one named seat."),
        _step(3, "ceo_assign", head, "Each task has one owner and one due date."),
        _step(4, "ceo_tool_call", "Assigned seat",
              "Envelope validated, tool called once, JSON result returned."),
        _step(5, "ceo_verify", head,
              "Result status is success AND expected fields are present. Started is not completed."),
        _step(6, "ceo_decision_log", head,
              "Decision, options, chosen option, and reason are recorded.", approval_required=True),
    ]
    if _Q4_GOAL.search(goal):
        steps.append(_step(7, "q4_closeout_checklist", "CFO / CLO / COO (Hermes)",
                           "Checklist is complete, and no external filing goes out without owner approval.",
                           approval_required=True))
    inferred = infer_risk({"goal": goal})
    if inferred:
        steps[3]["approval_required"] = True
    return {
        "status": "success",
        "run_id": "run-" + hashlib.sha1(goal.strip().encode("utf-8")).hexdigest()[:8],
        "inferred_risk": inferred,
        "head_seat": head,
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

def normalize_seat(seat, aliases=None):
    """Map a seat string to a canonical seat, or None. 'Hermes' is the COO.

    aliases: optional mapping of display name (upper) -> canonical seat.
    Defaults to the module-level SEAT_ALIASES set from install config.
    """
    if not isinstance(seat, str):
        return None
    s = re.sub(r"\(.*?\)", "", seat)
    s = re.sub(r"\s+", " ", s).strip().upper()
    if s == "HERMES":
        return "COO"
    if s == "COS":
        return "Chief of Staff"
    amap = aliases if isinstance(aliases, dict) else SEAT_ALIASES
    if s in amap:
        return amap[s]
    for canonical in SEATS:
        if canonical.upper() == s:
            return canonical
    return None


def _norm(text):
    """NFKC-normalize and strip zero-width characters so lookalikes cannot slip past."""
    return unicodedata.normalize("NFKC", str(text)).translate(_ZERO_WIDTH)


def _value_is_secret(text):
    t = _norm(text)
    return any(pat.search(t) for pat in _SECRET_VALUE_PATTERNS)


def _is_secret_key(key):
    squashed = re.sub(r"[^a-z0-9]", "", _norm(key).lower())
    if squashed in _SAFE_KEYS:
        return False
    return any(part in squashed for part in _BANNED_KEY_PARTS)


def find_secret_paths(obj, path="arguments", _depth=0):
    """Return the PATHS (never the values) of anything credential-like, nested included.

    Fails closed: anything nested too deep to inspect is reported as a hit.
    Strings that hold JSON are parsed and scanned. A key that is itself a
    secret value is reported as <redacted-key>, never echoed.
    """
    hits = []
    if _depth > _MAX_DEPTH:
        return [f"{path} (nested too deep to inspect)"]
    if isinstance(obj, dict):
        for key, value in obj.items():
            label = "<redacted-key>" if _value_is_secret(key) else str(key)
            here = f"{path}.{label}"
            if label == "<redacted-key>" or _is_secret_key(key):
                hits.append(here)
            hits.extend(find_secret_paths(value, here, _depth + 1))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            hits.extend(find_secret_paths(value, f"{path}[{i}]", _depth + 1))
    elif isinstance(obj, str):
        if _value_is_secret(obj):
            hits.append(path)
        stripped = obj.strip()
        if stripped[:1] in ("{", "[") and len(stripped) <= _MAX_JSON_STRING:
            try:
                inner = json.loads(stripped)
            except ValueError:
                inner = None
            if isinstance(inner, (dict, list)):
                hits.extend(find_secret_paths(inner, f"{path}(json)", _depth + 1))
    seen, ordered = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            ordered.append(h)
    return ordered


def infer_risk(arguments):
    """Content cues that raise a call to Type 1. Returns a sorted list of flag names.

    Reads only the plain-text planning fields (task, goal, decision, chosen,
    reason, notes, options). Cues can raise a call to Type 1, never lower it.
    A missed cue is not proof of Type 2: explicit risk flags still apply.
    """
    if not isinstance(arguments, dict):
        return []
    texts = []
    for field in _RISK_TEXT_FIELDS:
        value = arguments.get(field)
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, (list, tuple)):
            texts.extend(v for v in value if isinstance(v, str))
    blob = " . ".join(t[:2000] for t in texts[:40])
    return sorted(flag for flag, pattern in _RISK_CUES.items() if pattern.search(blob))


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

    if risk is not None and not isinstance(risk, dict):
        return _fail(tool_name, "risk must be an object of Type 1 flags, e.g. {\"external\": true}.")
    unknown_flags = [k for k in (risk or {}) if k not in RISK_FLAGS]
    if unknown_flags:
        return _fail(tool_name,
                     f"Unknown risk flags: {unknown_flags}. Valid flags: {', '.join(RISK_FLAGS)}. "
                     "A misspelled flag would silently classify the call as Type 2, so it is refused.")
    flags = {k: bool(v) for k, v in (risk or {}).items()}
    inferred = infer_risk(arguments)
    for flag in inferred:
        flags[flag] = True
    decision = classify_decision(**flags)
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
    if inferred:
        envelope["inferred_risk"] = inferred
        envelope["risk_note"] = "Raised to Type 1 from wording in the arguments. Content can raise a call, never lower it."
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
             A single string is treated as one field name. When omitted, the
             plugin's own tools use EXPECTED_FIELDS; unknown tools get a
             success-only check, reported as expect_source "none".
    """
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            result = None
    if isinstance(expect, str):
        expect = [expect]
    elif expect is not None and not isinstance(expect, (list, tuple)):
        expect = None
    expect_source = "caller" if expect else "default"
    if not expect:
        expect = EXPECTED_FIELDS.get(tool_name)
        if not expect:
            expect_source = "none"
    if not isinstance(retries_used, int) or isinstance(retries_used, bool) or retries_used < 0:
        retries_used = MAX_RETRIES
    status = _status_of(result)
    missing = []
    if status == "success" and expect:
        missing = [f for f in expect if f not in result or result[f] in (None, "", [], {})]
    verified = status == "success" and not missing
    executed = result.get("executed") if isinstance(result, dict) else None
    nxt = next_action(tool_name, "error" if (status == "success" and missing) else status,
                      retries_used=retries_used, executed=executed)
    return {
        "tool": tool_name,
        "status": status,
        "verified": verified,
        "missing_fields": missing,
        "expect_source": expect_source,
        "next": nxt,
    }
