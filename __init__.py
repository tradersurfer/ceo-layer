"""CEO Pack — Hermes plugin registration.

Registers 14 tools, 6 bundled skills, and 21 slash commands. (v0.4.0)
Orchestration first: brief -> route -> assign -> tool call -> verify
-> decision log. No network calls, no credential reads, no file writes
outside the plugin's own state. All external actions are flagged for
owner approval by the tools themselves; this plugin does not
auto-approve anything.

Seat naming, answered from the v0.3.0 handoff: ceo_route returns
"COO (Hermes)" for display, and normalize_seat in orchestration.py
accepts "COO", "COO (Hermes)", and "Hermes" and canonicalizes to "COO".
"""

import json
import logging
from pathlib import Path

from . import schemas, tools

logger = logging.getLogger(__name__)

_SKILLS = [
    "ceo-brief",
    "ceo-decision-log",
    "ceo-assign",
    "q4-closeout",
    "orchestration",
    "model-selection",
]


def _on_post_tool_call(tool_name, args, result, task_id, **kwargs):
    """Wire verification into the post_tool_call hook (v0.3.0 step 5).

    For every ceo_* result, run verify_result and log whether it is
    verified. The hook never raises and never blocks the host — it
    closes the advisory gap by making verification visible on every
    call, while ceo_verify remains the tool a caller uses explicitly.
    """
    logger.debug("CEO Pack: tool called: %s (session %s)", tool_name, task_id)
    if not tool_name.startswith("ceo_") and tool_name != "q4_closeout_checklist":
        return
    try:
        from .orchestration import META_TOOLS, verify_result

        if tool_name in META_TOOLS:
            # An envelope or a verdict is not a completed business action, so there is nothing to verify.
            logger.info("CEO Pack verify: %s is a meta tool (validation/verdict), not a completion.", tool_name)
            return

        parsed = result
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except ValueError:
                parsed = None
        verdict = verify_result(tool_name, parsed)
        logger.info(
            "CEO Pack verify: %s status=%s verified=%s next=%s",
            tool_name,
            verdict.get("status"),
            verdict.get("verified"),
            verdict.get("next", {}).get("action"),
        )
    except Exception:
        logger.exception("CEO Pack: post_tool_call verification failed for %s", tool_name)


def _ceo_command(raw_args):
    return (
        "CEO Pack: use ceo_brief for a goal, ceo_route to pick a seat, "
        "ceo_assign for one owner + one due date, and ceo_decision_log "
        "to record the decision. External actions need owner approval. "
        f"Input was: {raw_args}"
    )


def _q4_command(raw_args):
    return (
        "CEO Pack Q4 closeout: use q4_closeout_checklist with the year, "
        "then assign CFO (books/tax prep), CLO (entity/filings), "
        "COO/Hermes (coordination), and CRO (potential-client pipeline). "
        "Checklist only, not tax or legal advice. "
        f"Input was: {raw_args}"
    )


def _apply_install_config(ctx):
    """Read seat aliases + head seat from install config, if the host exposes it."""
    try:
        from . import orchestration
    except ImportError:
        import orchestration
    cfg = {}
    for attr in ("config", "settings", "plugin_config"):
        cfg = getattr(ctx, attr, None) or {}
        if isinstance(cfg, dict) and cfg:
            break
    if not isinstance(cfg, dict):
        return
    aliases = {}
    for seat in orchestration.SEATS:
        key = "alias_" + seat.lower().replace(" ", "_")
        val = cfg.get(key)
        if isinstance(val, str) and val.strip():
            aliases[val.strip()] = seat
    named = cfg.get("seat_names")
    if isinstance(named, dict):
        for alias, seat in named.items():
            if isinstance(alias, str) and isinstance(seat, str):
                aliases[alias.strip()] = seat
    if aliases:
        ok, err = orchestration.set_seat_aliases(aliases)
        if not ok:
            logger.warning("CEO Pack: seat aliases refused: %s", err)
    head = cfg.get("head_seat")
    if isinstance(head, str) and head.strip():
        ok, err = orchestration.set_head_seat(head)
        if not ok:
            logger.warning("CEO Pack: head seat refused: %s", err)


def register(ctx):
    _apply_install_config(ctx)
    ctx.register_tool(
        name="ceo_brief", toolset="ceo-pack",
        schema=schemas.CEO_BRIEF, handler=tools.ceo_brief,
    )
    ctx.register_tool(
        name="ceo_assign", toolset="ceo-pack",
        schema=schemas.CEO_ASSIGN, handler=tools.ceo_assign,
    )
    ctx.register_tool(
        name="ceo_decision_log", toolset="ceo-pack",
        schema=schemas.CEO_DECISION_LOG, handler=tools.ceo_decision_log,
    )
    ctx.register_tool(
        name="ceo_route", toolset="ceo-pack",
        schema=schemas.CEO_ROUTE, handler=tools.ceo_route,
    )
    ctx.register_tool(
        name="q4_closeout_checklist", toolset="ceo-pack",
        schema=schemas.Q4_CLOSEOUT_CHECKLIST, handler=tools.q4_closeout_checklist,
    )
    ctx.register_tool(
        name="ceo_orchestrate", toolset="ceo-pack",
        schema=schemas.CEO_ORCHESTRATE, handler=tools.ceo_orchestrate,
    )
    ctx.register_tool(
        name="ceo_choose_model", toolset="ceo-pack",
        schema=schemas.CEO_CHOOSE_MODEL, handler=tools.ceo_choose_model,
    )
    ctx.register_tool(
        name="ceo_tool_call", toolset="ceo-pack",
        schema=schemas.CEO_TOOL_CALL, handler=tools.ceo_tool_call,
    )
    ctx.register_tool(
        name="ceo_verify", toolset="ceo-pack",
        schema=schemas.CEO_VERIFY, handler=tools.ceo_verify,
    )
    ctx.register_tool(
        name="ceo_closeout_checklist", toolset="ceo-pack",
        schema=schemas.CEO_CLOSEOUT_CHECKLIST, handler=tools.ceo_closeout_checklist,
    )
    ctx.register_tool(
        name="ceo_daily_check", toolset="ceo-pack",
        schema=schemas.CEO_DAILY_CHECK, handler=tools.ceo_daily_check,
    )
    ctx.register_tool(
        name="ceo_performance_check", toolset="ceo-pack",
        schema=schemas.CEO_PERFORMANCE_CHECK, handler=tools.ceo_performance_check,
    )
    ctx.register_tool(
        name="ceo_status_check", toolset="ceo-pack",
        schema=schemas.CEO_STATUS_CHECK, handler=tools.ceo_status_check,
    )
    ctx.register_tool(
        name="ceo_roster", toolset="ceo-pack",
        schema=schemas.CEO_ROSTER, handler=tools.ceo_roster,
    )
    ctx.register_hook("post_tool_call", _on_post_tool_call)

    skills_dir = Path(__file__).parent / "skills"
    for name in _SKILLS:
        skill_md = skills_dir / name / "SKILL.md"
        if skill_md.exists():
            ctx.register_skill(name, skill_md)

    ctx.register_command("ceo", _ceo_command, description="CEO Pack brief and assignment help")
    ctx.register_command("q4", _q4_command, description="CEO Pack year-end closeout checklist")
    ctx.register_command(
        "orchestrate",
        lambda raw: "CEO Pack orchestration: use ceo_orchestrate with a goal. "
        f"Input was: {raw}",
        description="CEO Pack orchestration plan for a goal",
    )
    # v0.4.0: shortcuts to the existing ceo_* tools. No new tools.
    _shortcuts = [
        ("brief", "ceo_brief", "Start a CEO brief for a goal"),
        ("assign", "ceo_assign", "Assign one owner and one due date"),
        ("verify", "ceo_verify", "Verify a step before it counts done"),
        ("log", "ceo_decision_log", "Log a decision"),
        ("decision", "ceo_decision_log", "Log a decision, decision-first"),
        ("route", "ceo_route", "Route a task to a seat"),
        ("models", "ceo_choose_model", "Pick or check the model"),
        ("weekly-pulse", "ceo_orchestrate", "Weekly pulse: orchestrate the week in one flow"),
        ("closeout", "q4_closeout_checklist", "Year-end closeout checklist"),
        ("q1", "ceo_closeout_checklist", "Q1 closeout checklist"),
        ("q2", "ceo_closeout_checklist", "Q2 closeout checklist"),
        ("q3", "ceo_closeout_checklist", "Q3 closeout checklist"),
        ("monthly-closeout", "ceo_closeout_checklist", "Monthly closeout checklist"),
        ("daily-checks", "ceo_daily_check", "Daily checks: shipped, earned, stuck, decisions"),
        ("eod-checks", "ceo_daily_check", "End-of-day checks and handoff"),
        ("performance-checks", "ceo_performance_check", "Employee performance check"),
        ("status-check", "ceo_status_check", "Status of a briefing, assignment, task, or log"),
        ("roster", "ceo_roster", "C-Suite roster view (CEO Dashboard)"),
    ]
    for _name, _tool, _desc in _shortcuts:
        ctx.register_command(
            _name,
            (lambda tool: (lambda raw: f"CEO Pack: use {tool}. Input was: {raw}"))(_tool),
            description=_desc,
        )
