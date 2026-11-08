"""CEO Pack — Hermes plugin registration.

Registers 9 tools, 6 bundled skills, and 3 slash commands.
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
    if not tool_name.startswith("ceo_"):
        return
    try:
        from .orchestration import verify_result

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


def register(ctx):
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
