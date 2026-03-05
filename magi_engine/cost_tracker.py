"""
MAGI Cost Tracker
==================
Tracks token usage and calculates costs for Azure OpenAI API calls.
"""

import time
from dataclasses import dataclass, field
from typing import Optional


# Azure OpenAI pricing (per 1K tokens) -- approximate, adjust as needed
PRICING = {
    "gpt-5": {"input": 0.01, "output": 0.03},
    "gpt-5.1": {"input": 0.01, "output": 0.03},
    "gpt-5.2": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},
}


@dataclass
class APICallRecord:
    """A single API call record."""
    persona: str
    phase: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


@dataclass
class DeliberationCost:
    """Cost summary for a single deliberation."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    calls: list[APICallRecord] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def to_dict(self) -> dict:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "num_api_calls": len(self.calls),
            "calls": [
                {
                    "persona": c.persona,
                    "phase": c.phase,
                    "model": c.model,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "cost_usd": round(c.cost_usd, 6),
                    "duration_ms": round(c.duration_ms, 1),
                }
                for c in self.calls
            ],
        }


class CostTracker:
    """Tracks cumulative costs across all deliberations."""

    def __init__(self, model: str = "gpt-5"):
        self.model = model
        self.cumulative_input_tokens: int = 0
        self.cumulative_output_tokens: int = 0
        self.cumulative_cost_usd: float = 0.0
        self.total_calls: int = 0
        self._current: Optional[DeliberationCost] = None

    def begin_deliberation(self) -> DeliberationCost:
        """Start tracking a new deliberation."""
        self._current = DeliberationCost()
        return self._current

    def record_call(
        self,
        persona: str,
        phase: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: float = 0.0,
    ) -> APICallRecord:
        """Record a single API call."""
        pricing = PRICING.get(self.model, PRICING["gpt-5"])
        cost = (input_tokens / 1000 * pricing["input"]) + (
            output_tokens / 1000 * pricing["output"]
        )

        record = APICallRecord(
            persona=persona,
            phase=phase,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            duration_ms=duration_ms,
        )

        # Update current deliberation
        if self._current is not None:
            self._current.calls.append(record)
            self._current.total_input_tokens += input_tokens
            self._current.total_output_tokens += output_tokens
            self._current.total_cost_usd += cost

        # Update cumulative
        self.cumulative_input_tokens += input_tokens
        self.cumulative_output_tokens += output_tokens
        self.cumulative_cost_usd += cost
        self.total_calls += 1

        return record

    def get_cumulative_summary(self) -> dict:
        return {
            "cumulative_input_tokens": self.cumulative_input_tokens,
            "cumulative_output_tokens": self.cumulative_output_tokens,
            "cumulative_total_tokens": self.cumulative_input_tokens + self.cumulative_output_tokens,
            "cumulative_cost_usd": round(self.cumulative_cost_usd, 6),
            "total_api_calls": self.total_calls,
            "model": self.model,
        }
