# Model Selection

Use `ceo_choose_model` before picking a brain for a job.

- CEO seat: largest orchestration model you can afford. Default is free: Nemotron 3 Ultra free (`nvidia/nemotron-3-ultra-550b-a55b:free` on OpenRouter, `nemotron-3-ultra-free` on Zen), 550B, 1M context.
- Fallback free: GLM Flash free on Zen, faster and lighter when the default is slow or rate-limited.
- Workers: fast, narrow frees — Nemotron 3.5 Lightning, Ling 3.0 Flash, or `openrouter/free` as a random free with tool-calling filter. Never put a small fast worker in the CEO seat.
- Paid override, high stakes only: Claude Opus 5.5. Paid value: Claude Sonnet 5.5 or GPT-6.1 Sol, same price band in the Nov 4 check.
- Free limits to plan around: OpenRouter free is 20 requests/min, plus 50 requests/day until $10 of credits, then 1,000/day. A CEO task uses many requests — one per tool round-trip.
- Free lineups turn over fast. Verify the live provider list before a demo, and never hard-depend on one free slug forever.
