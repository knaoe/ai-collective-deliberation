#!/usr/bin/env python3
"""
MAGI System Test Script
========================
Runs a deliberation and saves the result.
"""

import json
import os
import sys
import time

# Ensure we can import from the project
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from magi_engine.engine import MAGIEngine


def print_separator(char: str = "=", width: int = 70):
    print(char * width)


def print_phase_header(phase_num: int, name: str):
    print()
    print_separator("=")
    print(f"  PHASE {phase_num}: {name}")
    print_separator("=")
    print()


def main():
    question = "Should humanity colonize Mars?"

    print_separator()
    print("  MAGI SYSTEM - DELIBERATION TEST")
    print_separator()
    print()
    print(f"  Question: {question}")
    print()
    print("  Initializing MAGI system...")

    try:
        engine = MAGIEngine()
    except Exception as e:
        print(f"  ERROR: Failed to initialize MAGI engine: {e}")
        sys.exit(1)

    print("  MELCHIOR (科学者) ... ONLINE")
    print("  BALTHASAR (母親) ... ONLINE")
    print("  CASPER (女) ....... ONLINE")
    print()
    print("  Beginning deliberation...")
    print()

    start_time = time.time()

    def on_event(event_type: str, data: dict):
        if event_type == "phase_start":
            print_phase_header(data["phase"], data["name"])
        elif event_type == "persona_thinking":
            print(f"  [{data['persona']}] Analyzing...")
        elif event_type == "persona_response":
            persona = data["persona"]
            phase = data["phase"]
            content = data["content"]
            print(f"\n  --- {persona} ---")
            # Print first 500 chars as preview
            preview = content[:500] + ("..." if len(content) > 500 else "")
            for line in preview.split("\n"):
                print(f"  {line}")
            if "vote" in data:
                print(f"\n  VOTE: {data['vote']}")
            print()
        elif event_type == "deliberation_complete":
            elapsed = time.time() - start_time
            print()
            print_separator("=")
            print("  MAGI VERDICT")
            print_separator("=")
            print()
            print(f"  Verdict: {data['verdict']}")
            print()
            for persona, vote in data["votes"].items():
                print(f"    {persona}: {vote}")
            print()
            print(f"  Consensus:")
            for line in data["consensus"].split("\n"):
                print(f"    {line}")
            print()
            print(f"  Time elapsed: {elapsed:.1f}s")
            print()

    deliberation = engine.deliberate(question, on_event=on_event)

    # Save output
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "test_deliberation.json")

    result = deliberation.to_dict()
    result["metadata"] = {
        "elapsed_seconds": round(time.time() - start_time, 2),
        "cost": deliberation.cost.to_dict() if deliberation.cost else None,
        "cumulative_cost": engine.cost_tracker.get_cumulative_summary(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print_separator()
    print(f"  Output saved to: {output_path}")
    if deliberation.cost:
        cost = deliberation.cost
        print(f"  Total tokens: {cost.total_tokens}")
        print(f"  Estimated cost: ${cost.total_cost_usd:.4f}")
    print_separator()

    return deliberation


if __name__ == "__main__":
    main()
