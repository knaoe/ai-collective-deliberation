#!/usr/bin/env python3
"""
MAGI Batch Deliberation Script
================================
Runs multiple deliberations and saves each result to the output/ directory.
"""

import json
import os
import sys
import time

# Ensure we can import from the project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from magi_engine.engine import MAGIEngine


# Default topics for batch deliberation
DEFAULT_TOPICS = [
    {
        "question": "Should AI be given legal personhood?",
        "output_file": "deliberation_ai_personhood.json",
    },
    {
        "question": "Is remote work better than office work?",
        "output_file": "deliberation_remote_work.json",
    },
    {
        "question": "Should we implement universal basic income?",
        "output_file": "deliberation_ubi.json",
    },
]


def print_separator(char: str = "=", width: int = 70):
    print(char * width)


def run_deliberation(engine: MAGIEngine, question: str, output_path: str) -> dict:
    """Run a single deliberation and save the result."""
    print()
    print_separator()
    print(f"  MAGI DELIBERATION")
    print(f"  Question: {question}")
    print_separator()
    print()

    start_time = time.time()

    def on_event(event_type: str, data: dict):
        if event_type == "phase_start":
            print(f"  Phase {data['phase']}: {data['name']}")
        elif event_type == "persona_thinking":
            print(f"    [{data['persona']}] Analyzing...")
        elif event_type == "persona_response":
            persona = data["persona"]
            content = data["content"]
            content_len = len(content)
            preview = content[:200] + ("..." if content_len > 200 else "")
            # Show first line of preview
            first_line = preview.split("\n")[0]
            print(f"    [{persona}] ({content_len} chars) {first_line[:80]}")
            if "vote" in data and data["vote"]:
                print(f"    [{persona}] VOTE: {data['vote']}")
        elif event_type == "deliberation_complete":
            elapsed = time.time() - start_time
            print()
            print(f"  VERDICT: {data['verdict']}")
            for persona, vote in data["votes"].items():
                print(f"    {persona}: {vote}")
            print(f"  Time: {elapsed:.1f}s")

    deliberation = engine.deliberate(question, on_event=on_event)
    elapsed = time.time() - start_time

    # Build result
    result = deliberation.to_dict()
    result["metadata"] = {
        "elapsed_seconds": round(elapsed, 2),
        "cost": deliberation.cost.to_dict() if deliberation.cost else None,
    }

    # Save
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  Saved: {output_path}")
    if deliberation.cost:
        print(f"  Tokens: {deliberation.cost.total_tokens} | Cost: ${deliberation.cost.total_cost_usd:.4f}")
    print()

    return result


def main():
    """Run batch deliberations."""
    print_separator()
    print("  MAGI SYSTEM - BATCH DELIBERATION")
    print_separator()
    print()

    # Parse optional CLI arguments for custom topics
    topics = DEFAULT_TOPICS
    if len(sys.argv) > 1:
        # Allow passing custom questions as arguments
        topics = []
        for i, q in enumerate(sys.argv[1:]):
            safe_name = q.lower().replace(" ", "_")[:40]
            topics.append({
                "question": q,
                "output_file": f"deliberation_{safe_name}.json",
            })

    output_dir = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(output_dir, exist_ok=True)

    print(f"  Topics: {len(topics)}")
    for i, t in enumerate(topics):
        print(f"    {i + 1}. {t['question']}")
    print()

    # Initialize engine
    try:
        engine = MAGIEngine()
    except Exception as e:
        print(f"  ERROR: Failed to initialize MAGI engine: {e}")
        sys.exit(1)

    print("  MELCHIOR (科学者) ... ONLINE")
    print("  BALTHASAR (母親) ... ONLINE")
    print("  CASPER (女) ....... ONLINE")
    print()

    # Run each deliberation
    total_start = time.time()
    results = []

    for i, topic in enumerate(topics):
        print(f"  [{i + 1}/{len(topics)}] Starting deliberation...")
        output_path = os.path.join(output_dir, topic["output_file"])
        result = run_deliberation(engine, topic["question"], output_path)
        results.append(result)

    total_elapsed = time.time() - total_start

    # Summary
    print()
    print_separator("=")
    print("  BATCH COMPLETE")
    print_separator("=")
    print()
    print(f"  Deliberations: {len(results)}")
    print(f"  Total time: {total_elapsed:.1f}s")

    cumulative = engine.cost_tracker.get_cumulative_summary()
    print(f"  Total tokens: {cumulative['cumulative_total_tokens']}")
    print(f"  Total cost: ${cumulative['cumulative_cost_usd']:.4f}")
    print()

    # Save cumulative summary
    summary_path = os.path.join(output_dir, "batch_summary.json")
    summary = {
        "batch_timestamp": time.time(),
        "total_deliberations": len(results),
        "total_elapsed_seconds": round(total_elapsed, 2),
        "cumulative_cost": cumulative,
        "topics": [
            {
                "question": t["question"],
                "output_file": t["output_file"],
                "verdict": r.get("final_verdict", "unknown"),
            }
            for t, r in zip(topics, results)
        ],
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  Summary saved: {summary_path}")
    print_separator("=")


if __name__ == "__main__":
    main()
