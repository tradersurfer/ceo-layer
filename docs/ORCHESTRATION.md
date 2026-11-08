# Orchestration layer

CEO Pack's job is orchestration, not chatting. The layer is:

**Brief -> Route -> Plan -> Assign -> Call -> Verify -> Log**

## Tool-call envelope

```json
{
  "tool": "ceo_assign",
  "seat": "CFO",
  "arguments": {"task": "Reconcile books", "seat": "CFO", "due_date": "2026-11-15"},
  "approval_required": false
}
```

## Rules, enforced by `ceo_tool_call` (`make_tool_call`)

| Rule | Behavior |
|---|---|
| Exact tool name | Unknown tools are refused, not guessed. Not retryable. |
| JSON arguments | Object required. A JSON string that parses is accepted with a warning. |
| Required fields | Missing fields are an error. `ceo_assign` needs `task`, `seat`, `due_date`. |
| Due date | ISO `YYYY-MM-DD`. A past date warns. |
| Seats | CEO, CFO, COO, CTO, CMO, CLO, Chief of Staff, CRO. Hermes is the COO. |
| Credentials | Keys and values are scanned, nested included. The error names the path and never echoes the value. |
| Approval | `ceo_decision_log` and `q4_closeout_checklist` are always flagged. Any Type 1 flag also gates. A log entry is not approval. |

## Result statuses

Every result is read as one of: `success`, `error`, `blocked`, `needs_approval`, or `unknown`. **Unknown is never treated as success.** A validated envelope is not a completed call.

## Retry (`next_action`)

| Situation | Action |
|---|---|
| success | verify expected fields |
| blocked / needs_approval | stop, wait for the owner |
| error, read-only tool, first failure | retry once with corrected arguments |
| error, second failure | escalate |
| error, state-changing tool (`ceo_assign`, `ceo_decision_log`) | escalate unless it was rejected before running |
| unrecognized result | escalate |

## Decision types

- **Type 1** — irreversible, difficult to unwind, high-cost, high-impact, outside assigned authority, or materially legal, financial, security, people, regulatory, or reputation-sensitive. Escalate.
- **Type 2** — reversible, low-cost, bounded, within assigned authority. Decide promptly.

## Model layer

See `models.py` and the model-selection skill. The CEO seat gets the orchestration model, workers get fast narrow models, and the paid flagship is an override. The plugin does not call a model. It returns the choice, IDs, fallbacks, and limits so the host (Hermes / OpenRouter / Zen / Nous Portal) can wire it. That keeps it stdlib-only and catalog-safe: no network calls, no credential reads, no bundled keys.

## What is enforced vs advisory

Enforced inside the plugin: validation, secret refusal, required fields, approval flags, retry decisions. Advisory: the plugin cannot force the host to route calls through `ceo_tool_call` or to run `ceo_verify`. Wire the `post_tool_call` hook to close that gap.
