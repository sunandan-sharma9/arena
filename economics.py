"""Cost model for the naive-vs-optimized demo.

Pricing is $/MTok, first-party Claude API list rates as of Aug 2026.
Claude Sonnet 5 is running its introductory rate through 2026-08-31 —
after that it reverts to $3.00 / $15.00 and these numbers will read a
little pessimistic-to-optimistic; swap PRICING["claude-sonnet-5"] then.
"""

from __future__ import annotations

PRICING = {
    # model_id: (input $/MTok, output $/MTok)
    "claude-sonnet-5": (2.00, 10.00),   # intro pricing through 2026-08-31
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-5": (5.00, 25.00),
}

CACHE_WRITE_MULTIPLIER = 1.25  # 5-minute TTL write premium
CACHE_READ_MULTIPLIER = 0.10


def cost_for_call(model: str, usage: dict) -> float:
    """usage: dict with input_tokens, output_tokens, cache_creation_input_tokens,
    cache_read_input_tokens (any may be absent/zero)."""
    in_rate, out_rate = PRICING[model]
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cache_write = usage.get("cache_creation_input_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)

    cost = (
        input_tokens * in_rate
        + cache_write * in_rate * CACHE_WRITE_MULTIPLIER
        + cache_read * in_rate * CACHE_READ_MULTIPLIER
    ) / 1_000_000
    cost += (output_tokens * out_rate) / 1_000_000
    return cost


def summarize_metrics(metrics_log: list[dict]) -> dict:
    """Aggregate a list of per-call metric dicts (see agent.py CallMetrics) into totals."""
    if not metrics_log:
        return {
            "calls": 0, "total_cost": 0.0, "total_latency": 0.0,
            "avg_ttft": 0.0, "p50_latency": 0.0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0,
        }
    latencies = sorted(m["latency_s"] for m in metrics_log)
    n = len(latencies)
    p50 = latencies[n // 2] if n % 2 else (latencies[n // 2 - 1] + latencies[n // 2]) / 2
    ttfts = [m["ttft_s"] for m in metrics_log if m.get("ttft_s") is not None]
    return {
        "calls": n,
        "total_cost": sum(m["cost_usd"] for m in metrics_log),
        "total_latency": sum(m["latency_s"] for m in metrics_log),
        "avg_ttft": (sum(ttfts) / len(ttfts)) if ttfts else None,
        "p50_latency": p50,
        "input_tokens": sum(m["usage"].get("input_tokens", 0) for m in metrics_log),
        "output_tokens": sum(m["usage"].get("output_tokens", 0) for m in metrics_log),
        "cache_read_tokens": sum(m["usage"].get("cache_read_input_tokens", 0) for m in metrics_log),
        "cache_write_tokens": sum(m["usage"].get("cache_creation_input_tokens", 0) for m in metrics_log),
    }


def monthly_projection(cost_per_request: float, requests_per_day: int) -> float:
    return cost_per_request * requests_per_day * 30
