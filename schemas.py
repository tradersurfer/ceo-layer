"""Tool schemas — what the LLM sees. CEO Pack, generic template.

No business data is shipped in this plugin. The user supplies their
business name, owner name, and tasks at runtime.
"""

CEO_BRIEF = {
    "name": "ceo_brief",
    "description": (
        "Create a one-page CEO brief for a goal: the decision needed, "
        "the owner for each workstream, and what needs owner approval. "
        "Use this at the start of a business task, not for a single factual question."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "The goal in one sentence."},
            "business_name": {"type": "string", "description": "Business name supplied by the user, if known."},
        },
        "required": ["goal"],
    },
}

CEO_ASSIGN = {
    "name": "ceo_assign",
    "description": (
        "Assign a task to exactly one seat: CEO, CFO, COO (Hermes), CTO, "
        "CMO, CLO, Chief of Staff, or CRO. Every assignment needs one owner "
        "and one due date. Use this to delegate, not to do the work itself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string"},
            "seat": {
                "type": "string",
                "description": "One of: CEO, CFO, COO, CTO, CMO, CLO, Chief of Staff, CRO.",
            },
            "due_date": {"type": "string", "description": "Due date, e.g. 2026-11-15."},
        },
        "required": ["task", "seat", "due_date"],
    },
}

CEO_DECISION_LOG = {
    "name": "ceo_decision_log",
    "description": (
        "Record a decision with its options, the chosen option, the reason, "
        "and whether it needs owner approval. External, priced, or shipped "
        "items always need approval."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "decision": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            "chosen": {"type": "string"},
            "reason": {"type": "string"},
            "needs_approval": {"type": "boolean"},
        },
        "required": ["decision", "chosen"],
    },
}

CEO_ROUTE = {
    "name": "ceo_route",
    "description": (
        "Route a task to the right seat by domain, following the task-router "
        "rules in docs/TASK_ROUTER.md. Returns the seat, why, and whether "
        "the owner must approve before execution."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string"},
            "domain": {
                "type": "string",
                "description": "e.g. finance, operations, technology, marketing, legal, people, strategy.",
            },
        },
        "required": ["task"],
    },
}

Q4_CLOSEOUT_CHECKLIST = {
    "name": "q4_closeout_checklist",
    "description": (
        "Return a generic year-end closeout checklist: taxes, annual filings, "
        "entity cleanup, and annual reporting. This is a checklist only, not "
        "tax or legal advice. Confirm items with a qualified professional."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "The tax/reporting year, e.g. 2026."},
            "entity_type": {"type": "string", "description": "Optional, e.g. LLC, corporation, sole proprietorship."},
        },
        "required": ["year"],
    },
}

CEO_ORCHESTRATE = {
    "name": "ceo_orchestrate",
    "description": (
        "Build an ordered orchestration plan for a goal: brief, route, "
        "assign, tool calls, decision log, and verification. Use this when "
        "a task needs more than one seat or more than one tool call."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {"type": "string"},
            "model_key": {
                "type": "string",
                "description": "Optional model choice key: free_default, free_fallback, free_worker, paid_value, paid_flagship.",
            },
        },
        "required": ["goal"],
    },
}

CEO_CHOOSE_MODEL = {
    "name": "ceo_choose_model",
    "description": (
        "Choose a model by job and budget: CEO orchestration, worker, or "
        "high-stakes. Returns the recommended model, fallbacks, and limits. "
        "Free default is Nemotron 3 Ultra free; paid flagship is an override only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task_type": {"type": "string", "description": "ceo, worker, or high_stakes."},
            "budget": {"type": "string", "description": "free, paid_value, or paid_flagship."},
            "provider": {"type": "string", "description": "openrouter, zen, nous, or auto."},
        },
        "required": [],
    },
}

CEO_TOOL_CALL = {
    "name": "ceo_tool_call",
    "description": (
        "Validate a tool-call envelope before dispatch: exact tool name, "
        "JSON arguments, no credential keys or values (nested included), "
        "required fields, and an approval flag. This validates the call; "
        "it does not execute an external tool by itself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "arguments": {"type": "object"},
            "seat": {"type": "string"},
            "risk": {
                "type": "object",
                "description": "Optional Type 1 flags for this call: external, priced, irreversible, legal_or_financial, security, people, regulatory, reputation, outside_authority.",
            },
        },
        "required": ["tool_name", "arguments"],
    },
}

CEO_VERIFY = {
    "name": "ceo_verify",
    "description": (
        "Verify a tool result before reporting the step as done: read its "
        "status (success, error, blocked, needs_approval, unknown), check "
        "expected fields, and return the next action (verify, retry once, "
        "stop and wait for the owner, or escalate). Unknown is never success, "
        "and a validated envelope is not a completed call."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "result": {
                "type": ["object", "string"],
                "description": "The tool's returned dict, or its JSON string.",
            },
            "expect": {"type": "array", "items": {"type": "string"}, "description": "Field names that must be present for the step to count as complete."},
            "retries_used": {"type": "integer", "description": "How many retries have already been used (max 1)."},
        },
        "required": ["tool_name", "result"],
    },
}

CEO_CLOSEOUT_CHECKLIST = {
    "name": "ceo_closeout_checklist",
    "description": (
        "Return a closeout checklist for a quarter (Q1, Q2, Q3, Q4) or monthly, "
        "for bookkeeping and accounting: books, tax items, filings, entity "
        "cleanup, and reporting. Checklist only, not tax or legal advice."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "quarter": {"type": "string", "description": "Q1, Q2, Q3, Q4, or monthly. Default Q4."},
            "year": {"type": "integer", "description": "The tax/reporting year, e.g. 2026."},
            "entity_type": {"type": "string", "description": "Optional, e.g. LLC, corporation, sole proprietorship."},
        },
        "required": ["year"],
    },
}

CEO_DAILY_CHECK = {
    "name": "ceo_daily_check",
    "description": (
        "Daily check or end-of-day check: what shipped, what earned, what is "
        "stuck, what needs a decision. A report, not an action."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "period": {"type": "string", "description": "daily or eod. Default daily."},
            "date": {"type": "string", "description": "Optional ISO date YYYY-MM-DD."},
        },
        "required": ["period"],
    },
}

CEO_PERFORMANCE_CHECK = {
    "name": "ceo_performance_check",
    "description": (
        "Employee performance check: goals, wins, gaps, next steps. Template "
        "only — the plugin holds no employee data. People decisions are "
        "Type 1 and need owner approval."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "The person or seat being reviewed."},
            "period": {"type": "string", "description": "Optional period, e.g. quarter. Default quarter."},
            "metrics": {"type": "array", "items": {"type": "string"}, "description": "Optional metrics supplied by the owner."},
        },
        "required": ["subject"],
    },
}

CEO_STATUS_CHECK = {
    "name": "ceo_status_check",
    "description": (
        "Status of a briefing, assignment, task, log, plan, or run. The plugin "
        "keeps no state, so pass the item's result (and tool_name to verify "
        "it); without an item the status is honestly unknown."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "item_type": {"type": "string", "description": "brief, assignment, task, log, plan, or run."},
            "reference": {"type": "string", "description": "Optional run_id or description of the item."},
            "tool_name": {"type": "string", "description": "Optional tool that produced the result, to verify it."},
            "result": {"type": ["object", "string"], "description": "The item's result to check."},
        },
        "required": ["item_type"],
    },
}

CEO_ROSTER = {
    "name": "ceo_roster",
    "description": (
        "C-Suite roster view: seat, display name, bound profile, capabilities "
        "and gaps for every seat. The data for the install flow and the "
        "pinned CEO Dashboard."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}
