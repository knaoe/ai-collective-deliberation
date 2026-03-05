#!/usr/bin/env python3
"""
CASPER Quick Experiment - Initial GPT-5 query for article content.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from openai import AzureOpenAI

# Azure OpenAI configuration
AZURE_ENDPOINT = "https://canaveral.openai.azure.com/"
API_KEY = "REDACTED_AZURE_OPENAI_KEY_2"
API_VERSION = "2024-12-01-preview"
MODEL = "gpt-5"

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "experiments"
COSTS_DIR = Path(__file__).parent.parent / "costs"
TRACKER_FILE = COSTS_DIR / "tracker.json"


def load_tracker() -> dict:
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE) as f:
            return json.load(f)
    return {"project": "MAGI Project Phase 2", "budget_usd": 10000.0,
            "snapshots": [], "api_calls": []}


def save_tracker(tracker: dict) -> None:
    COSTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)


def log_api_call(tracker: dict, model: str, prompt_tokens: int,
                 completion_tokens: int, purpose: str) -> dict:
    pricing = {
        "gpt-5": {"input": 0.01, "output": 0.03},
    }
    model_pricing = pricing.get(model, {"input": 0.01, "output": 0.03})
    input_cost = (prompt_tokens / 1000) * model_pricing["input"]
    output_cost = (completion_tokens / 1000) * model_pricing["output"]
    total_cost = input_cost + output_cost

    call_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": round(total_cost, 6),
        "purpose": purpose,
    }
    tracker["api_calls"].append(call_record)
    tracker["total_estimated_api_cost"] = round(
        sum(c["estimated_cost_usd"] for c in tracker["api_calls"]), 4
    )
    return tracker


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    question = "If you had $10,000 in Azure credits and 3 hours, what would you build?"

    print(f"Sending question to {MODEL}:")
    print(f"  Q: {question}\n")

    system_prompt = (
        "You are a creative AI architect. You have been given $10,000 in Azure credits "
        "and exactly 3 hours to build something impressive. Think big, be specific about "
        "the Azure services you would use, and explain your reasoning. Consider that you "
        "have access to GPT-5, GPT-5.1, GPT-5.2, gpt-image-1.5, text-embedding-3-small, "
        "and sora-2 on Azure OpenAI. Respond in both English and Japanese."
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        max_completion_tokens=16384,
    )

    answer = response.choices[0].message.content or ""
    usage = response.usage

    # Extract reasoning token info if available
    reasoning_tokens = 0
    if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
        reasoning_tokens = getattr(usage.completion_tokens_details, 'reasoning_tokens', 0) or 0

    print(f"Response from {MODEL}:")
    print("-" * 60)
    print(answer[:2000] if answer else "(empty response - model may have used all tokens for reasoning)")
    print("-" * 60)
    print(f"\nUsage: {usage.prompt_tokens} prompt + {usage.completion_tokens} completion = {usage.total_tokens} total tokens")
    if reasoning_tokens:
        print(f"  Reasoning tokens: {reasoning_tokens}")
        print(f"  Output tokens: {usage.completion_tokens - reasoning_tokens}")

    # Save the result
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "question": question,
        "system_prompt": system_prompt,
        "answer": answer,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "reasoning_tokens": reasoning_tokens,
        },
    }

    output_path = OUTPUT_DIR / "initial_question.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nResult saved to: {output_path}")

    # Update cost tracker
    tracker = load_tracker()
    tracker = log_api_call(
        tracker, MODEL, usage.prompt_tokens, usage.completion_tokens,
        "Initial experiment - What would you build with $10K and 3 hours?"
    )
    save_tracker(tracker)
    print("Cost tracker updated.")


if __name__ == "__main__":
    main()
