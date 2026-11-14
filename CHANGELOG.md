# Changelog

## 0.4.0
- FIXED router (Hermes live test P0): whole-word matching with per-seat priority, matched terms, also-consult, and confidence. "Review the supplier contract" now routes to CLO, "Fix the checkout bug" to CTO, "Close the books" / "Reconcile books" to CFO. "Review the proposal for new laptops" no longer routes to COO. Unmatched tasks go to CEO at low confidence instead of silently claiming a domain match.
- FIXED verify / assign status mismatch (Hermes live test P0): every real tool result now verifies clean with default expected fields per tool. ceo_assign, ceo_brief, ceo_route, q4_closeout_checklist, ceo_orchestrate, and ceo_choose_model all return status success; gated decision logs return needs_approval and stop for the owner. A validated envelope is still not a completion.
- FIXED Ling 3.1: bare `inclusionai/ling-3.1-flash` is PAID ($0.075 in / $0.225 out per 1M). Free worker 2 is now `inclusionai/ling-3.1-flash:free` in models.py, docs/MODELS.md, and skills/model-selection.
- Handlers never raise: non-string / null / wrong-type input returns a JSON error, never an AttributeError. Every handler now refuses credential-like input, not just ceo_tool_call.
- Secret scanner hardened: squashed-key matching (api_key, API-KEY, zero-width splits), fail-closed past depth 20, JSON-string arguments scanned, secret-as-key redacted, plus Stripe, Bearer, Google, Hugging Face, npm, SendGrid, and embedded-credential URL patterns.
- Type 1 from wording: pay, send to a client, delete, fire, file taxes, wire funds, publish, rotate a password, and set pricing raise a call to Type 1. Misspelled or non-dict risk flags are refused instead of silently staying Type 2. A decision log cannot ungate Type 1 wording. Plans mark the call step approval-required for risky goals and carry a deterministic run_id.
- Q4 trigger now catches "taxes" / "taxation" ("File our 2026 taxes" adds the checklist step). Q4 year must be a four-digit year 2000-2100.
- NEW seat aliases (config): rename any seat for display, e.g. COO to Poseidon, CEO to Billy. Canonical seats never change; logs show Alias (Canonical); duplicate aliases are refused.
- NEW head CEO config: head_seat (default CEO) and optional head_profile. The human owner is still the final Type 1 gate.
- NEW capability check (orchestration API): per-seat checklists, missing items listed, install-missing returns an owner-gated install plan (nothing installs inside the plugin), declining leaves a name-only binding flagged in plan and log.
- NEW opt-in business-data reading (orchestration API): ephemeral, chat-scoped, explicit field list plus purpose plus expiry, every read audited, instant revoke, fresh opt-in required for any future read. Fictional-data test only.
- NEW slash commands (shortcuts to existing tools, no new tools): /brief, /assign, /verify, /log, /decision, /route, /models, /weekly-pulse, /closeout. Existing /ceo, /q4, /orchestrate unchanged.
- Post-tool-call hook skips meta tools (ceo_tool_call, ceo_verify) and now also verifies q4_closeout_checklist.
- Scrubbed personal and business names from SUBMISSION.md. This version is not pushed to Nous.
- Tests: 38 new v0.4.0 regression tests in tests/test_v040.py, plus the 34 v0.3.0 tests and the demo, all passing.
- v0.4.0 additions (design answers, 2026-11-12): generalized closeout — ceo_closeout_checklist covers Q1-Q4 + monthly (q4_closeout_checklist stays as an alias); new tools ceo_daily_check (daily/EOD), ceo_performance_check (people = Type 1, owner approval), ceo_status_check (reports only what it is given, never invents a status), ceo_roster (install flow + pinned CEO Dashboard data). 14 tools, 21 slash commands. Seat bindings now carry all three display fields — name + avatar + SOUL — display-only. First industry suite after v0.4.0: SaaS.
- Research round (2026-11-14, ranked top-20 business tasks AI agent users actually ask for): router expanded from 19 domains / ~10 terms per seat to 37 domains and roughly 3x the terms. Writing/email drafting -> Chief of Staff, coding/debugging -> CTO, content/social -> CMO, deals/proposals/support -> CRO, forecasting/runway/board -> CFO, inbox/calendar/documents/monitoring -> COO, fundraising/investors -> CEO. Multi-term scoring already in place means "close the sales deal, contract attached" routes CRO (3 terms) over CLO (1), and "close the quarter" / "close Q4" route CFO via the new quarter/Q1-Q4 terms. One-liner limits are by design: closing a complex deal, final contract sign-off, and hire/no-hire still need the brief first.
- Framework catalog path fixed (2026-11-13): all 20 references to `core/frameworks/catalog.js` (a path from the separate ceo-agent project) now point at `engines/framework-catalog.js` in this repo.
- Ling price wording corrected: models.py and docs/MODELS.md no longer quote a specific paid price for the bare Ling ID (it varies by provider) — the rule stays "bare = paid, use :free".
- Tests: 15 new router regression tests in tests/test_v041_router.py (104 total), all passing, 20/20 back-to-back, Nous validator 15/15, no warnings.

## 0.3.0
- NEW `ceo_verify` tool: the Verify step of Brief -> Route -> Plan -> Assign -> Call -> Verify -> Log now exists in code. A call that started is not a call that completed.
- Secret scanning covers nested keys AND values (JWTs, `sb_secret_`, `sk-`, GitHub, AWS, Slack, private-key blocks). Errors name the path, never the value.
- `ceo_assign` is validated: required fields, ISO `YYYY-MM-DD` due date, known seat (Hermes = COO).
- Retry rule is now code (`next_action`): one retry, never blind on state-changing tools.
- Type 1 now covers security, people, regulatory, reputation, and outside-authority, matching the docs.
- Plan no longer gates every call by default (Type 1 stops, Type 2 proceeds) and only adds the Q4 checklist for Q4 / year-end goals.
- JSON-string arguments are parsed instead of rejected.
- Tests (34) and a deterministic demo script added.
