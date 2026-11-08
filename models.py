"""Model catalog for CEO Pack.

Free lineup turns over fast, and free rate limits are real, so this file
is a *choice list with a default*, not a promise that a slug will stay
free forever. Verify the live provider list before shipping a demo.

Sources for the picks below: the author's Nov 4, 2026 model check for
CEO work (long context, multi-turn delegation, tool calling, approval
gate) and the #009 CTO free-tier note. Paid prices are from that same
check and will change; treat them as guidance, not a quote.
"""

MODELS = [
    {
        "key": "free_default",
        "label": "Free default — CEO",
        "openrouter_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "zen_id": "nemotron-3-ultra-free",
        "size": "550B",
        "context": "1M tokens",
        "cost": "free",
        "best_for": "CEO orchestration: long sessions, handoffs, tool history, delegation",
        "tool_calling": "Supported. Size and orchestration are the reason to pick it, not tool support alone.",
        "limits": "OpenRouter free: 20 requests/min, plus 50 requests/day until $10 of credits are bought, then 1,000/day. A CEO task uses many requests — one per tool round-trip — so plan around that. Data caution (live check Nov 5, 2026): the NVIDIA free host is listed as 'May train' / prompts logged — do not send client books through the free route.",
    },
    {
        "key": "free_fallback",
        "label": "Free fallback — fast daily CEO",
        "openrouter_id": None,
        "zen_id": "glm-5.3-flash-free",
        "size": "Flash-class",
        "context": "Check live provider page",
        "cost": "free",
        "best_for": "Faster, lighter CEO work when the 550B default is slow or rate-limited",
        "tool_calling": "Supported. Reported in the Nov 4 check as zero-retention / no-training on Zen, alongside DeepSeek V4.1 Flash Free — verify live before handling sensitive books.",
        "limits": "Free-model retention and training policies differ by provider. Verify before sending client books.",
    },
    {
        "key": "free_worker",
        "label": "Free workers — narrow jobs",
        "openrouter_id": "nvidia/nemotron-3.5-lightning:free",
        "zen_id": "nemotron-3.5-lightning-free",
        "size": "Lightning-class",
        "context": "1,000,000 tokens (free endpoint)",
        "cost": "free",
        "best_for": "Fast, narrow worker jobs: one tool, one answer, one check",
        "tool_calling": "Supported. Also in the #009 free-tier set, with inclusionai/ling-3.1-flash as a second worker option. Live check Nov 5, 2026: answered all test calls on Nov 3 and 7/7 daily checks; NVIDIA host 'May train'.",
        "limits": "Do not put a small fast worker in the CEO seat. Workers execute; the CEO orchestrates. Slug corrected Nov 5, 2026: the bare 'nemotron-3.5-lightning' in the earlier draft is not a valid OpenRouter ID — it needs the nvidia/ prefix and :free suffix.",
    },
    {
        "key": "free_worker_2",
        "label": "Free worker 2",
        "openrouter_id": "inclusionai/ling-3.1-flash",
        "zen_id": None,
        "size": "Flash-class",
        "context": "262,144 tokens",
        "cost": "free (zero-priced, no :free suffix)",
        "best_for": "Fast, narrow worker jobs",
        "tool_calling": "Supported, from the #009 free-tier set. CORRECTED Nov 5, 2026: the earlier draft listed inclusionai/ling-3.0-flash as free — it is NOT free on OpenRouter (listed $0.021 in / $0.063 out per 1M tokens, Nov 2, 2026). Ling 3.1 Flash was the zero-priced Novita-hosted variant in the Oct 5 catalog (zero retention); re-verify live before use, free slugs turn over fast.",
        "limits": "Worker only, not a CEO default. Zero-priced without the :free suffix — do not append :free to this ID.",
    },
    {
        "key": "free_random",
        "label": "Free random (OpenRouter)",
        "openrouter_id": "openrouter/free",
        "zen_id": None,
        "size": "Varies",
        "context": "Varies",
        "cost": "free",
        "best_for": "Fallback when a named free model is unavailable; picks a free model and filters for tool calling",
        "tool_calling": "Filtered for tool calling by the provider.",
        "limits": "Non-deterministic — do not use for a graded demo unless the named default fails.",
    },
    {
        "key": "paid_flagship",
        "label": "Paid override — high stakes only",
        "openrouter_id": "claude-opus-5.5",
        "zen_id": None,
        "size": "Flagship",
        "context": "Check live provider page",
        "cost": "About $4 in / $20 out per 1M tokens (Nov 4 check, will change)",
        "best_for": "High-stakes work where failure is expensive: money, legal, irreversible decisions",
        "tool_calling": "Top-ranked in the Nov 4 check across tool-use, reasoning, and agent benchmarks.",
        "limits": "Paid. Use only when the free default fails or the stakes justify it.",
    },
    {
        "key": "paid_value",
        "label": "Paid value — everyday frontier",
        "openrouter_id": "claude-sonnet-5.5",
        "zen_id": None,
        "size": "Flagship-class, lighter",
        "context": "Check live provider page",
        "cost": "About $2 in / $10 out per 1M tokens (Nov 4 check, will change)",
        "best_for": "Everyday frontier CEO work when free limits bite",
        "tool_calling": "Strong multi-turn tool use in the Nov 4 check.",
        "limits": "Paid. The other value pick in that check was GPT-6.1 Sol at the same price band.",
    },
]

DEFAULT_MODEL_KEY = "free_default"


def get_model(key):
    for model in MODELS:
        if model["key"] == key:
            return model
    return None


def choose_model(task_type="ceo", budget="free"):
    """Pick a model by job, not by hype.

    task_type: ceo, worker, high_stakes
    budget: free, paid_value, paid_flagship
    """
    task_type = (task_type or "ceo").lower()
    budget = (budget or "free").lower()
    if task_type == "high_stakes" or budget == "paid_flagship":
        key = "paid_flagship"
    elif budget == "paid_value":
        key = "paid_value"
    elif task_type == "worker":
        key = "free_worker"
    else:
        key = "free_default"
    model = get_model(key)
    fallbacks = ["free_fallback", "free_random"] if key.startswith("free") else ["free_default", "free_fallback"]
    return {
        "recommended": model,
        "fallbacks": [get_model(k) for k in fallbacks],
        "rule": "CEO seat gets the largest orchestration model you can afford. Workers get fast, narrow models. Paid flagship is an override, not a default.",
        "warning": "Verify the live provider list and rate limits before a demo. Free lineups change month to month.",
    }
