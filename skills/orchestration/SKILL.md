# Orchestration

This is the core of CEO Pack. Do not skip steps.

1. Brief with `ceo_brief`: goal, decision needed, approval gate.
2. Route with `ceo_route`: one seat per workstream, by domain.
3. Plan with `ceo_orchestrate`: ordered tool calls, each with seat, tool, arguments, and approval flag.
4. Assign with `ceo_assign`: one owner, one due date per task.
5. Call with `ceo_tool_call`: exact tool name, JSON arguments, no credential keys.
6. Verify the returned JSON before the next step. A started call is not a completed call.
7. Log with `ceo_decision_log`: options, chosen option, reason, approval flag.

Decision types:
- Type 1 (irreversible, priced, external, legal/financial): escalate to the owner, stop.
- Type 2 (reversible, low-cost, bounded): decide promptly, do not build an approval queue.

Retries: retry a failed call once with corrected arguments, then escalate. Never retry a write, send, payment, or deletion blindly. On blocked / needs_approval, stop and surface the reason.

CEO retains accountability for the integrated result, even when another seat does the work.
