#!/usr/bin/env python3
"""
CASPER Cost Monitor - Azure spending tracker for the MAGI Project.
Queries Azure Cost Management and maintains a local cost tracking file.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

COSTS_DIR = Path(__file__).parent.parent / "costs"
TRACKER_FILE = COSTS_DIR / "tracker.json"


def run_az_command(args: list[str]) -> dict | list | str:
    """Run an az CLI command and return parsed JSON output."""
    cmd = ["az"] + args + ["-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"Warning: az command failed: {result.stderr.strip()}", file=sys.stderr)
        return {}
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        return result.stdout.strip()


def get_resource_group_cost() -> dict:
    """Query resource group level cost info using az consumption."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Try to get consumption usage for today
    try:
        usage = run_az_command([
            "consumption", "usage", "list",
            "--start-date", today,
            "--end-date", today,
        ])
        if isinstance(usage, list):
            total = sum(float(item.get("pretaxCost", 0)) for item in usage)
            return {
                "date": today,
                "total_cost_usd": round(total, 4),
                "item_count": len(usage),
                "source": "az-consumption-usage",
            }
    except Exception as e:
        print(f"Consumption API not available: {e}", file=sys.stderr)

    return {
        "date": today,
        "total_cost_usd": 0.0,
        "item_count": 0,
        "source": "az-consumption-usage",
        "note": "No usage data available yet (may take up to 24h to appear)",
    }


def get_openai_resource_info() -> dict:
    """Get Azure OpenAI resource info."""
    try:
        resources = run_az_command([
            "cognitiveservices", "account", "list",
            "--resource-group", "magi-project",
        ])
        if isinstance(resources, list):
            return {
                "openai_resources": [
                    {
                        "name": r.get("name"),
                        "location": r.get("location"),
                        "sku": r.get("sku", {}).get("name"),
                    }
                    for r in resources
                ]
            }
    except Exception:
        pass
    return {"openai_resources": []}


def load_tracker() -> dict:
    """Load existing tracker or create new one."""
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE) as f:
            return json.load(f)
    return {
        "project": "MAGI Project Phase 2",
        "budget_usd": 10000.0,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "snapshots": [],
        "api_calls": [],
    }


def save_tracker(tracker: dict) -> None:
    """Save tracker to JSON file."""
    COSTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)
    print(f"Tracker saved to {TRACKER_FILE}")


def add_snapshot(tracker: dict) -> dict:
    """Add a new cost snapshot to the tracker."""
    cost_info = get_resource_group_cost()
    openai_info = get_openai_resource_info()

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "azure_cost": cost_info,
        "openai_resources": openai_info.get("openai_resources", []),
    }

    tracker["snapshots"].append(snapshot)
    tracker["last_updated"] = datetime.now(timezone.utc).isoformat()
    return tracker


def log_api_call(tracker: dict, model: str, prompt_tokens: int,
                 completion_tokens: int, purpose: str) -> dict:
    """Log an API call to the tracker."""
    # Approximate pricing (per 1K tokens)
    pricing = {
        "gpt-5": {"input": 0.01, "output": 0.03},
        "gpt-5.1": {"input": 0.005, "output": 0.015},
        "gpt-5.2": {"input": 0.003, "output": 0.006},
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-image-1.5": {"input": 0.0, "output": 0.0, "per_image": 0.04},
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


def print_summary(tracker: dict) -> None:
    """Print a summary of current costs."""
    print("\n" + "=" * 60)
    print("  MAGI Project - CASPER Cost Monitor")
    print("=" * 60)
    print(f"  Budget: ${tracker['budget_usd']:,.2f}")
    print(f"  API calls logged: {len(tracker.get('api_calls', []))}")
    total_api = tracker.get("total_estimated_api_cost", 0)
    print(f"  Estimated API cost: ${total_api:,.4f}")
    print(f"  Remaining budget: ${tracker['budget_usd'] - total_api:,.2f}")

    if tracker.get("snapshots"):
        latest = tracker["snapshots"][-1]
        azure_cost = latest["azure_cost"].get("total_cost_usd", 0)
        print(f"  Latest Azure cost snapshot: ${azure_cost:,.4f}")
        if latest["azure_cost"].get("note"):
            print(f"  Note: {latest['azure_cost']['note']}")
    print("=" * 60 + "\n")


def main():
    tracker = load_tracker()
    tracker = add_snapshot(tracker)
    save_tracker(tracker)
    print_summary(tracker)


if __name__ == "__main__":
    main()
