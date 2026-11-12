# CEO Pack — hackathon submission pack

Prepared Nov 5, 2026. NOT submitted. Nothing here pushes to GitHub or opens a PR.
Still gated: the owner's live Hermes Mobile verification (doctor / validate / tests /
demo + model check) must come back and be reviewed first. Only then: approve,
push, test 20x back-to-back, report back.

## The hackathon

- Hermes Agent Plugin Hackathon, posted by @NousResearch Nov 4, 2026.
  Original post: https://x.com/NousResearch/status/2118094256438936062
- Runs 7 days — treat Nov 11 as approximate, not a guaranteed cutoff.
  No prize breakdown, categories, or exact closing time were stated.
- $20,000 in cash prizes and more. Judging on usefulness, reliability,
  polish, creativity, reviewed on a rolling basis every few days.
  Submit early; do not wait for day 7.
- After close, every entry gets a thread in the Nous Research Discord.

## Submit in this order

1. Public repo (owned by tradersurfer93 — catalog entries can only
   be submitted by the owner or a major contributor) containing this folder.
2. Catalog PR to the `hermes-agent` repo, per the catalog submission guide:
   https://hermes-agent.nousresearch.com/docs/developer-guide/plugins/catalog-submission
   Every entry pins a full 40-character commit SHA — branches, tags, and
   short SHAs are rejected. A SHA-bump is a new PR, so keep changes small
   after opening it.
3. Demo video on X, tagging @NousResearch (script below, 60–90 seconds).
4. Typeform with both links (catalog PR + demo video):
   https://form.typeform.com/to/FwJLvOln
   The form can be submitted as soon as the PR is open, before maintainers
   run the catalog checks. Questions go to the Nous Discord.
5. If the GitHub App route will not open a PR upstream, open the catalog PR
   manually from the fork's compare page in GitHub web.

## Pre-submit checklist

- [ ] Hermes verification pasted back and reviewed satisfactory
      (doctor --ci, validate --install-deps, unittest discover, demo_flow.py,
      plugin.yaml v0.3.0 / author tradersurfer93 / 9 tools)
- [ ] Model IDs re-verified live (see "Live model check, Nov 5" below)
- [ ] Push to public repo, note the full 40-char SHA
- [ ] Test 20x back-to-back after the push, report results
- [ ] Film demo, post on X tagging @NousResearch
- [ ] Open catalog PR, submit Typeform with PR + video links
- [ ] Release graphic (held for live): workspace/imagine_media/media-generation-ceo-pack-release-graphic-patched.webp
      — patched version: Sonnet 5.5 / Opus 5.5 named, orchestration sentence
      fixed, NOW LIVE kept for use only once it is actually live.

## Demo video script (60–90 seconds, one real task, no test-meta)

Film the exact path in `demo/demo_flow.py` (runs clean locally, stdlib-only,
fictional inputs, no network, no credentials):

- 0:00–0:10 — Install the plugin by name. Ask the CEO agent for a Q4 closeout brief.
- 0:10–0:35 — Watch it delegate: ATLAS/CFO on books and tax prep,
  JUSTICE/CLO on entity and filings, HERMES/COO on coordination.
  Show the plan: Brief -> Route -> Plan -> Assign -> Call -> Verify -> Log.
- 0:35–0:55 — Show one decision log with one owner and one due date per task.
  Show `ceo_verify` checking a result before the step counts as done, and
  a guessed tool (`ceo_send_money`) refused, not guessed.
- 0:55–1:15 — Show the approval gate: a Type 1 step (external + priced)
  stops for owner approval. End on the gate, not on a shipment.
- On screen, no stress-test footer, no ban-list phrases, no private data.

## Live model check, Nov 5, 2026 (web, not a live API call)

Checked this morning against OpenRouter / OpenCode Zen listings and
Nov 3 test-call reports. Free lineups turn over fast — re-check on the
day of submission.

- Nemotron 3 Ultra free — CONFIRMED. `nvidia/nemotron-3-ultra-550b-a55b:free`,
  $0, 1M context, tool calling, answered all test calls Nov 3 (94% uptime
  last day). Caution: NVIDIA free host is listed "May train" / prompts
  logged — do not send client books through the free route.
- GLM-5.3-Flash Free (Zen) — CONFIRMED. `glm-5.3-flash-free`, zero retention
  / no training, free for a limited time, 200K context inside OpenCode.
- Nemotron 3.5 Lightning — SLUG CORRECTED in `models.py` + `docs/MODELS.md`
  + README. Was `nemotron-3.5-lightning` (not a valid OpenRouter ID).
  Correct: `nvidia/nemotron-3.5-lightning:free`, $0, 1M, answered Nov 3
  and 7/7 daily checks. Zen: `nemotron-3.5-lightning-free`.
- Ling — SLUG CORRECTED. `inclusionai/ling-3.0-flash` is PAID on OpenRouter
  ($0.021 in / $0.063 out per 1M tokens, Nov 2 listing), not free.
  Worker 2 is now `inclusionai/ling-3.1-flash` — zero-priced, no `:free`
  suffix, Novita-hosted, zero retention in the Oct 5 catalog. Re-verify
  live before use; the free Sante variant is no longer listed.
- Rate limits (confirmed): OpenRouter free 20 req/min, 50 req/day,
  1,000/day after $10 of credits bought. A CEO task uses many requests.

## What is in v0.3.0

- `plugin.yaml` v0.3.0, author tradersurfer93, 9 tools: ceo_brief,
  ceo_assign, ceo_decision_log, ceo_route, q4_closeout_checklist,
  ceo_orchestrate, ceo_choose_model, ceo_tool_call, ceo_verify.
- Orchestration: Brief -> Route -> Plan -> Assign -> Call -> Verify -> Log.
  Type 1 stops for owner approval; Type 2 proceeds fast.
- No business data, prices, locations, client data, personal
  names, portraits, credentials, or logs in the build (see PRIVACY.md).
