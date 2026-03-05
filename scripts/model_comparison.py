#!/usr/bin/env python3
"""
CASPER Model Comparison - Compare gpt-4o, gpt-5, gpt-5.1, gpt-5.2 on the same question.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openai import AzureOpenAI

# Azure OpenAI configuration
AZURE_ENDPOINT = "https://canaveral.openai.azure.com/"
API_KEY = "REDACTED_AZURE_OPENAI_KEY_2"
API_VERSION = "2024-12-01-preview"

MODELS = ["gpt-4o", "gpt-5", "gpt-5.1", "gpt-5.2"]

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "experiments"
COSTS_DIR = Path(__file__).parent.parent / "costs"
TRACKER_FILE = COSTS_DIR / "tracker.json"

QUESTION = "2026年のAI技術のトレンドを3つ予測してください。各予測は100文字以内で。"

# Approximate pricing (per 1K tokens)
PRICING = {
    "gpt-5": {"input": 0.01, "output": 0.03},
    "gpt-5.1": {"input": 0.005, "output": 0.015},
    "gpt-5.2": {"input": 0.003, "output": 0.006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
}


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
    model_pricing = PRICING.get(model, {"input": 0.01, "output": 0.03})
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


def query_model(client: AzureOpenAI, model: str, question: str) -> dict:
    """Query a single model and return the result with timing and usage."""
    print(f"\n{'='*60}")
    print(f"  Querying: {model}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "あなたはAI技術の専門家です。簡潔かつ具体的に回答してください。"},
                {"role": "user", "content": question},
            ],
            max_completion_tokens=2048,
        )

        elapsed = time.time() - start_time
        answer = response.choices[0].message.content or ""
        usage = response.usage

        # Extract reasoning tokens if available
        reasoning_tokens = 0
        if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
            reasoning_tokens = getattr(usage.completion_tokens_details, 'reasoning_tokens', 0) or 0

        model_pricing = PRICING.get(model, {"input": 0.01, "output": 0.03})
        input_cost = (usage.prompt_tokens / 1000) * model_pricing["input"]
        output_cost = (usage.completion_tokens / 1000) * model_pricing["output"]
        total_cost = input_cost + output_cost

        print(f"  Answer: {answer[:200]}...")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Tokens: {usage.prompt_tokens} in / {usage.completion_tokens} out")
        if reasoning_tokens:
            print(f"  Reasoning tokens: {reasoning_tokens}")
        print(f"  Cost: ${total_cost:.6f}")

        return {
            "model": model,
            "answer": answer,
            "elapsed_seconds": round(elapsed, 2),
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "reasoning_tokens": reasoning_tokens,
            },
            "cost": {
                "input_cost_usd": round(input_cost, 6),
                "output_cost_usd": round(output_cost, 6),
                "total_cost_usd": round(total_cost, 6),
            },
            "status": "success",
        }

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  Error: {e}")
        return {
            "model": model,
            "answer": None,
            "elapsed_seconds": round(elapsed, 2),
            "usage": None,
            "cost": None,
            "status": "error",
            "error": str(e),
        }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    print("CASPER Model Comparison Experiment")
    print(f"Question: {QUESTION}")
    print(f"Models: {', '.join(MODELS)}")

    tracker = load_tracker()
    results = []

    for model in MODELS:
        result = query_model(client, model, QUESTION)
        results.append(result)

        # Log to cost tracker if successful
        if result["status"] == "success" and result["usage"]:
            tracker = log_api_call(
                tracker, model,
                result["usage"]["prompt_tokens"],
                result["usage"]["completion_tokens"],
                f"Model comparison experiment - {model}",
            )

    # Build comparison summary
    comparison = {
        "experiment": "model_comparison",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": QUESTION,
        "models_tested": MODELS,
        "results": results,
        "summary": {
            "fastest_model": None,
            "cheapest_model": None,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
        },
    }

    # Calculate summary stats
    successful = [r for r in results if r["status"] == "success"]
    if successful:
        fastest = min(successful, key=lambda r: r["elapsed_seconds"])
        cheapest = min(successful, key=lambda r: r["cost"]["total_cost_usd"])
        comparison["summary"]["fastest_model"] = fastest["model"]
        comparison["summary"]["fastest_time_seconds"] = fastest["elapsed_seconds"]
        comparison["summary"]["cheapest_model"] = cheapest["model"]
        comparison["summary"]["cheapest_cost_usd"] = cheapest["cost"]["total_cost_usd"]
        comparison["summary"]["total_cost_usd"] = round(
            sum(r["cost"]["total_cost_usd"] for r in successful), 6
        )
        comparison["summary"]["total_tokens"] = sum(
            r["usage"]["total_tokens"] for r in successful
        )

    # Save results
    output_path = OUTPUT_DIR / "model_comparison.json"
    with open(output_path, "w") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")

    # Save tracker
    save_tracker(tracker)

    # Print summary table
    print(f"\n{'='*60}")
    print("  COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Model':<12} {'Time (s)':<10} {'Tokens':<12} {'Cost ($)':<12}")
    print(f"  {'-'*46}")
    for r in results:
        if r["status"] == "success":
            print(f"  {r['model']:<12} {r['elapsed_seconds']:<10.2f} "
                  f"{r['usage']['total_tokens']:<12} {r['cost']['total_cost_usd']:<12.6f}")
        else:
            print(f"  {r['model']:<12} {'ERROR':<10} {'-':<12} {'-':<12}")
    print(f"{'='*60}")
    if comparison["summary"]["fastest_model"]:
        print(f"  Fastest: {comparison['summary']['fastest_model']} "
              f"({comparison['summary']['fastest_time_seconds']:.2f}s)")
        print(f"  Cheapest: {comparison['summary']['cheapest_model']} "
              f"(${comparison['summary']['cheapest_cost_usd']:.6f})")
        print(f"  Total cost: ${comparison['summary']['total_cost_usd']:.6f}")
    print()


if __name__ == "__main__":
    main()
