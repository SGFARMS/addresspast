"""Shared settings for the pipeline. Mirrors the AI block in site.config.ts."""
import os

MODEL_FAST = os.environ.get("AP_MODEL_FAST", "claude-haiku-5-5")
MODEL_SMART = os.environ.get("AP_MODEL_SMART", "claude-sonnet-5-5")

# USD per million tokens (keep in sync with site.config.ts → ai.pricing)
PRICING = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.10},
}

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Pilot counties (lowercase)
PILOT_COUNTIES = {"bernalillo", "valencia", "sandoval"}

# Daily spend guardrail for cron runs. A job stops early once its run cost passes this.
MAX_RUN_COST_USD = float(os.environ.get("AP_MAX_RUN_COST_USD", "5"))


def cost_usd(model: str, usage, batched: bool = False) -> float:
    p = PRICING.get(model)
    if not p or usage is None:
        return 0.0
    g = lambda k: getattr(usage, k, 0) or 0  # noqa: E731
    total = (
        g("input_tokens") * p["input"]
        + g("output_tokens") * p["output"]
        + g("cache_read_input_tokens") * p["cache_read"]
        + g("cache_creation_input_tokens") * p["cache_write"]
    ) / 1_000_000
    return total * (0.5 if batched else 1.0)
