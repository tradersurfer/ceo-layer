# Engines — adapted from ceo-agent

These are the generic engine concepts from `tradersurfer/ceo-agent`, adapted for a Hermes plugin:

- Task routing: analyze first, route by domain, CEO retains accountability. See `docs/TASK_ROUTER.md`.
- Department prompts: CEO, CFO, COO (Hermes), CTO, CMO, CLO, Chief of Staff. Each folder has PROMPT, BEHAVIOR, CONTRACT, IDENTITY, and SOUL files, written with placeholders, not a specific business.
- Framework catalog: `framework-catalog.js` is an index of strategy, finance, accounting, operations, marketing, organization, people, and technology frameworks. It is reference material, not executable Hermes code.
- Memory, behavior, architecture, organization, and security docs are in `docs/`.

What was NOT ported verbatim:

- The ceo-agent JavaScript runtime (`ceo-core/*.js`, app, CLI, desktop, website). Hermes plugins run Python `register(ctx)`, so the runtime logic was re-implemented in `tools.py` / `schemas.py` / `__init__.py` in a small, stdlib-only form: brief, route, assign, decision log, and closeout checklist.
- Any business-specific dispatch registry, client lanes, or personal content from the original repo. Those are the installer's own configuration, not shipped defaults.
