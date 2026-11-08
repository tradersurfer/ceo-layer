# Model choices — free default, top-ranked options

Default: **Nemotron 3 Ultra free** — `nvidia/nemotron-3-ultra-550b-a55b:free` (OpenRouter), `nemotron-3-ultra-free` (Zen). 550B, 1M context, picked in the Nov 4, 2026 check for CEO orchestration: long sessions, handoffs, tool history, delegation.

| Choice | ID / provider | Use for |
|---|---|---|
| free_default | nvidia/nemotron-3-ultra-550b-a55b:free | CEO, default |
| free_fallback | glm-5.3-flash-free (Zen) | Fast daily CEO when default is slow/rate-limited |
| free_worker | nvidia/nemotron-3.5-lightning:free | Narrow worker jobs |
| free_worker_2 | inclusionai/ling-3.1-flash (zero-priced, no :free suffix) | Narrow worker jobs — re-verify live; ling-3.0-flash is paid, not free |
| free_random | openrouter/free | Fallback, random free with tool-calling filter |
| paid_value | claude-sonnet-5.5 | Everyday frontier, when free limits bite |
| paid_flagship | claude-opus-5.5 | High stakes only, override not default |

Caveats, from that same check, that users must see:
- Live re-check Nov 5, 2026: Nemotron 3 Ultra free slug confirmed still $0 / 1M / tool-calling and answering test calls Nov 3; GLM-5.3-Flash Free still listed on Zen (zero retention, 200K context in OpenCode, free for a limited time); Lightning slug corrected to `nvidia/nemotron-3.5-lightning:free`; `inclusionai/ling-3.0-flash` is paid, not free — worker 2 is now `inclusionai/ling-3.1-flash`, re-verify live.
- NVIDIA free hosts are listed 'May train' / prompts logged — do not send client books through a free NVIDIA route.
- OpenRouter free: 20 req/min, 50 req/day until $10 of credits, then 1,000/day. A CEO task is many requests.
- Free lineups turn over fast — models free in July were not free by October, and Nous Portal rotates monthly. Verify live before a demo.
- Retention/training policies differ by provider and by free tier. Verify before sending sensitive books to a free model.
- Prices in `models.py` are Nov 4 guidance, not quotes.
