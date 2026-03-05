#!/usr/bin/env python3
"""
CASPER Image Generator - Generate article images using Azure OpenAI gpt-image-1.5.
"""

import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import AzureOpenAI

# Azure OpenAI configuration
AZURE_ENDPOINT = "https://canaveral.openai.azure.com/"
API_KEY = "REDACTED_AZURE_OPENAI_KEY_2"
API_VERSION = "2024-12-01-preview"
MODEL = "gpt-image-1.5"

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "images"
COSTS_DIR = Path(__file__).parent.parent / "costs"
TRACKER_FILE = COSTS_DIR / "tracker.json"


def get_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )


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


def log_image_call(tracker: dict, purpose: str, cost: float = 0.04) -> dict:
    call_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost_usd": cost,
        "purpose": purpose,
    }
    tracker["api_calls"].append(call_record)
    tracker["total_estimated_api_cost"] = round(
        sum(c["estimated_cost_usd"] for c in tracker["api_calls"]), 4
    )
    return tracker


def generate_image(client: AzureOpenAI, prompt: str, filename: str,
                   size: str = "1024x1024", quality: str = "high") -> Path:
    """Generate an image and save it to the output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename

    print(f"Generating image: {filename}")
    print(f"  Prompt: {prompt[:80]}...")
    print(f"  Size: {size}, Quality: {quality}")

    try:
        result = client.images.generate(
            model=MODEL,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
            output_format="png",
        )

        # Decode and save the image
        image_data = base64.b64decode(result.data[0].b64_json)
        with open(output_path, "wb") as f:
            f.write(image_data)

        print(f"  Saved to: {output_path}")
        print(f"  File size: {len(image_data):,} bytes")
        return output_path

    except Exception as e:
        print(f"  Error generating image: {e}", file=sys.stderr)
        raise


def main():
    client = get_client()
    tracker = load_tracker()

    # 1. Generate hero image
    hero_prompt = (
        "A futuristic command center with three massive supercomputers labeled "
        "MELCHIOR, BALTHASAR, and CASPER, inspired by Evangelion's NERV headquarters. "
        "Dark atmosphere with orange and green holographic displays. "
        "Anime style, high detail."
    )
    try:
        hero_path = generate_image(client, hero_prompt, "hero.png",
                                   size="1536x1024", quality="high")
        tracker = log_image_call(tracker, "Article hero image - MAGI command center")
        print(f"\nHero image generated: {hero_path}")
    except Exception as e:
        print(f"Failed to generate hero image: {e}")

    # 2. Generate MAGI system logo
    logo_prompt = (
        "A minimalist logo for the MAGI System: three interconnected hexagons "
        "forming a triangle pattern, each hexagon containing a stylized brain icon. "
        "Colors: deep purple, orange, and teal on a dark background. "
        "Clean vector style, suitable for a tech project logo."
    )
    try:
        logo_path = generate_image(client, logo_prompt, "magi_logo.png",
                                   size="1024x1024", quality="high")
        tracker = log_image_call(tracker, "MAGI system logo")
        print(f"Logo generated: {logo_path}")
    except Exception as e:
        print(f"Failed to generate logo: {e}")

    save_tracker(tracker)
    print("\nImage generation complete. Cost tracker updated.")


if __name__ == "__main__":
    main()
