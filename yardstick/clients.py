"""LLM client wrapper: Groq calls with backoff, token accounting, and cost (spec §8.1, §13.3).

One provider (Groq), two models (8B cheap / 70B strong). Every call returns tokens,
latency, and cost computed from published list prices (configs/pricing.yaml).
Retries transient failures with exponential backoff (2s → 60s, 5 tries).
"""
from __future__ import annotations

import functools
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from yardstick.envtools import require

REPO = Path(__file__).resolve().parents[1]
PRICING_PATH = REPO / "configs" / "pricing.yaml"

BACKOFF_START_S = 2.0
BACKOFF_MAX_S = 60.0
MAX_RETRIES = 5


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    model: str


@functools.lru_cache(maxsize=1)
def _pricing() -> dict:
    return yaml.safe_load(PRICING_PATH.read_text())["models"]


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = _pricing().get(model)
    if p is None:
        return 0.0
    return input_tokens / 1e6 * p["input_per_mtok"] + output_tokens / 1e6 * p["output_per_mtok"]


@functools.lru_cache(maxsize=1)
def _groq():
    from groq import Groq
    return Groq(api_key=require("GROQ_API_KEY"))


def _is_retryable(exc: Exception) -> bool:
    import groq
    if isinstance(exc, groq.RateLimitError):
        # A per-DAY token cap (TPD) won't clear within our backoff window (hours away),
        # so fail fast: the batch logs the failure and moves on, resuming after the daily
        # reset. A per-MINUTE cap (TPM) clears in seconds, so keep retrying that.
        msg = str(getattr(exc, "message", "") or exc).lower()
        return "per day" not in msg and "tpd" not in msg
    return isinstance(exc, (groq.APIConnectionError, groq.InternalServerError))


def generate(model: str, messages: list[dict], temperature: float = 0.0,
             max_tokens: int = 500) -> Completion:
    """Call Groq chat completions with ret/backoff. Raises on non-retryable errors
    and after exhausting retries (caller logs the failure to runs)."""
    client = _groq()
    delay = BACKOFF_START_S
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            latency_ms = int((time.perf_counter() - start) * 1000)
            usage = resp.usage
            in_tok = usage.prompt_tokens
            out_tok = usage.completion_tokens
            return Completion(
                text=resp.choices[0].message.content or "",
                input_tokens=in_tok, output_tokens=out_tok,
                cost_usd=cost_usd(model, in_tok, out_tok),
                latency_ms=latency_ms, model=model,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < MAX_RETRIES and _is_retryable(exc):
                time.sleep(delay)
                delay = min(delay * 2, BACKOFF_MAX_S)
                continue
            raise
    raise last_exc  # unreachable
