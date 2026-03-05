#!/usr/bin/env python3
"""Large-scale experiment to meaningfully use Azure budget."""
import json, time, os, base64
from datetime import datetime, timezone
from pathlib import Path
from openai import AzureOpenAI

AZURE_ENDPOINT = "https://canaveral.openai.azure.com/"
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "REDACTED_AZURE_OPENAI_KEY_2")
API_VERSION = "2024-12-01-preview"

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "experiments"
COSTS_DIR = Path(__file__).parent.parent / "costs"
TRACKER_FILE = COSTS_DIR / "tracker.json"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Approximate pricing (per 1K tokens)
PRICING = {
    "gpt-5": {"input": 0.01, "output": 0.03},
    "gpt-5.1": {"input": 0.005, "output": 0.015},
    "gpt-5.2": {"input": 0.003, "output": 0.006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
}

client = AzureOpenAI(azure_endpoint=AZURE_ENDPOINT, api_key=API_KEY, api_version=API_VERSION)

experiments = []
total_cost = 0.0


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
                 completion_tokens: int, cost: float, purpose: str) -> dict:
    call_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": round(cost, 6),
        "purpose": purpose,
    }
    tracker["api_calls"].append(call_record)
    tracker["total_estimated_api_cost"] = round(
        sum(c["estimated_cost_usd"] for c in tracker["api_calls"]), 4
    )
    return tracker


tracker = load_tracker()

# ============================================================
# Experiment 1: Long-form Creative Writing (GPT-5)
# ============================================================
print("=== Experiment 1: Long-form Creative Writing (GPT-5) ===")
start = time.time()
resp = client.chat.completions.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": "You are a brilliant science fiction author."},
        {"role": "user", "content": "Write an original short story (2000+ words) about three AI systems named MELCHIOR, BALTHASAR, and CASPER who must deliberate on the future of humanity. Include technical details about their architecture and the ethical dilemmas they face. Write in Japanese."}
    ],
    max_completion_tokens=16384,
)
elapsed = time.time() - start
usage = resp.usage
cost = (usage.prompt_tokens / 1000) * PRICING["gpt-5"]["input"] + (usage.completion_tokens / 1000) * PRICING["gpt-5"]["output"]
total_cost += cost
story = resp.choices[0].message.content
experiments.append({
    "name": "creative_writing_gpt5",
    "model": "gpt-5",
    "elapsed": round(elapsed, 2),
    "prompt_tokens": usage.prompt_tokens,
    "completion_tokens": usage.completion_tokens,
    "total_tokens": usage.total_tokens,
    "reasoning_tokens": getattr(getattr(usage, 'completion_tokens_details', None), 'reasoning_tokens', 0) or 0,
    "cost": round(cost, 6),
    "output_length": len(story),
})
tracker = log_api_call(tracker, "gpt-5", usage.prompt_tokens, usage.completion_tokens, cost, "Budget experiment - Creative writing GPT-5")
print(f"  Done: {usage.total_tokens} tokens, ${cost:.4f}, {elapsed:.1f}s, {len(story)} chars")

# Save story separately
with open(OUTPUT_DIR / "magi_short_story.txt", "w") as f:
    f.write(story)

# ============================================================
# Experiment 2: Long-form Creative Writing (GPT-5.1)
# ============================================================
print("\n=== Experiment 2: Long-form Creative Writing (GPT-5.1) ===")
start = time.time()
resp2 = client.chat.completions.create(
    model="gpt-5.1",
    messages=[
        {"role": "system", "content": "You are a brilliant science fiction author."},
        {"role": "user", "content": "Write an original short story (2000+ words) about three AI systems named MELCHIOR, BALTHASAR, and CASPER who must deliberate on the future of humanity. Include technical details about their architecture and the ethical dilemmas they face. Write in Japanese."}
    ],
    max_completion_tokens=16384,
)
elapsed = time.time() - start
usage = resp2.usage
cost = (usage.prompt_tokens / 1000) * PRICING["gpt-5.1"]["input"] + (usage.completion_tokens / 1000) * PRICING["gpt-5.1"]["output"]
total_cost += cost
story2 = resp2.choices[0].message.content
experiments.append({
    "name": "creative_writing_gpt51",
    "model": "gpt-5.1",
    "elapsed": round(elapsed, 2),
    "prompt_tokens": usage.prompt_tokens,
    "completion_tokens": usage.completion_tokens,
    "total_tokens": usage.total_tokens,
    "reasoning_tokens": getattr(getattr(usage, 'completion_tokens_details', None), 'reasoning_tokens', 0) or 0,
    "cost": round(cost, 6),
    "output_length": len(story2),
})
tracker = log_api_call(tracker, "gpt-5.1", usage.prompt_tokens, usage.completion_tokens, cost, "Budget experiment - Creative writing GPT-5.1")
print(f"  Done: {usage.total_tokens} tokens, ${cost:.4f}, {elapsed:.1f}s, {len(story2)} chars")

with open(OUTPUT_DIR / "magi_short_story_51.txt", "w") as f:
    f.write(story2)

# ============================================================
# Experiment 3: Same deliberation topic through ALL model tiers
# ============================================================
print("\n=== Experiment 3: Deliberation Comparison (All Models) ===")
deliberation_prompt = """You are one of three AI systems in the MAGI collective intelligence platform.
The question before you: "Should AI systems be granted limited legal personhood to enable them to enter contracts, own intellectual property, and be held accountable for their decisions?"

Deliberate on this from multiple angles. Consider:
1. Legal implications
2. Ethical considerations
3. Economic impact
4. Technical feasibility
5. Social consequences

Provide your verdict: APPROVE, REJECT, or CONDITIONAL (with conditions).
Write a thorough analysis in Japanese (1000+ words)."""

deliberation_results = []
for model in ["gpt-4o", "gpt-5", "gpt-5.1", "gpt-5.2"]:
    print(f"  Running deliberation with {model}...")
    start = time.time()
    try:
        resp_d = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "あなたはMAGIシステムの合議AIです。論理的かつ多角的に分析してください。"},
                {"role": "user", "content": deliberation_prompt},
            ],
            max_completion_tokens=8192,
        )
        elapsed = time.time() - start
        usage_d = resp_d.usage
        model_pricing = PRICING.get(model, {"input": 0.01, "output": 0.03})
        cost_d = (usage_d.prompt_tokens / 1000) * model_pricing["input"] + (usage_d.completion_tokens / 1000) * model_pricing["output"]
        total_cost += cost_d
        answer = resp_d.choices[0].message.content
        reasoning = getattr(getattr(usage_d, 'completion_tokens_details', None), 'reasoning_tokens', 0) or 0

        deliberation_results.append({
            "model": model,
            "elapsed": round(elapsed, 2),
            "prompt_tokens": usage_d.prompt_tokens,
            "completion_tokens": usage_d.completion_tokens,
            "total_tokens": usage_d.total_tokens,
            "reasoning_tokens": reasoning,
            "cost": round(cost_d, 6),
            "answer_length": len(answer),
            "answer_preview": answer[:300],
        })
        tracker = log_api_call(tracker, model, usage_d.prompt_tokens, usage_d.completion_tokens, cost_d, f"Budget experiment - Deliberation {model}")

        # Save full deliberation
        with open(OUTPUT_DIR / f"deliberation_{model.replace('.', '_')}.txt", "w") as f:
            f.write(answer)

        print(f"    {usage_d.total_tokens} tokens, ${cost_d:.4f}, {elapsed:.1f}s")
    except Exception as e:
        print(f"    Error: {e}")
        deliberation_results.append({"model": model, "error": str(e)})

experiments.append({
    "name": "deliberation_comparison",
    "models": ["gpt-4o", "gpt-5", "gpt-5.1", "gpt-5.2"],
    "results": deliberation_results,
})

# ============================================================
# Experiment 4: Image Generation (3 images)
# ============================================================
print("\n=== Experiment 4: Image Generation ===")
image_prompts = [
    ("agents_deliberation.png", "Three AI agents deliberating around a holographic table. Cyberpunk anime style, blue/orange/purple color scheme, dark background with glowing elements. Each agent represented as a translucent holographic figure."),
    ("consensus.png", "Three hexagonal screens showing APPROVE/CONDITIONAL/REJECT votes merging into a unified decision. Evangelion NERV style UI, dark sci-fi aesthetic with orange and green accents."),
    ("timeline.png", "A futuristic timeline visualization showing 3 hours of AI deliberation, with branching paths and decision nodes. Tech/sci-fi style, glowing blue and green lines on dark background, Japanese text overlays."),
]

for filename, prompt in image_prompts:
    print(f"  Generating {filename}...")
    try:
        img_resp = client.images.generate(
            model="gpt-image-1.5",
            prompt=prompt,
            n=1,
            size="1024x1024",
        )
        img_data = base64.b64decode(img_resp.data[0].b64_json)
        img_path = Path(__file__).parent.parent / "output" / "images" / filename
        img_path.parent.mkdir(parents=True, exist_ok=True)
        with open(img_path, "wb") as f:
            f.write(img_data)
        img_cost = 0.04
        total_cost += img_cost
        experiments.append({"name": f"image_{filename}", "model": "gpt-image-1.5", "cost": img_cost, "path": str(img_path)})
        tracker = log_api_call(tracker, "gpt-image-1.5", 0, 0, img_cost, f"Budget experiment - Image {filename}")
        print(f"    Saved: {img_path}")
    except Exception as e:
        print(f"    Error: {e}")
        experiments.append({"name": f"image_{filename}", "model": "gpt-image-1.5", "error": str(e)})

# ============================================================
# Experiment 5: Embedding Generation
# ============================================================
print("\n=== Experiment 5: Embedding Generation ===")
texts_to_embed = [
    "MELCHIOR analyzes with cold scientific precision",
    "BALTHASAR weighs human impact and compassion",
    "CASPER calculates strategic pragmatic outcomes",
    "The MAGI system achieves consensus through deliberation",
    "Three aspects of one mind, forever debating humanity's future",
    "AIエージェントの自律性と責任の境界",
    "マルチエージェントシステムによる集合知の実現",
    "GPT-5の推論トークンが示す「思考の深さ」",
    "1万ドルの予算で3時間、AIに何ができるか",
    "人間とAIの協調作業における最適な役割分担",
]
try:
    emb_resp = client.embeddings.create(model="text-embedding-3-small", input=texts_to_embed)
    emb_cost = (emb_resp.usage.total_tokens / 1000) * 0.00002
    total_cost += emb_cost
    experiments.append({
        "name": "embeddings",
        "model": "text-embedding-3-small",
        "tokens": emb_resp.usage.total_tokens,
        "cost": round(emb_cost, 8),
        "dimensions": len(emb_resp.data[0].embedding),
        "num_texts": len(texts_to_embed),
    })
    tracker = log_api_call(tracker, "text-embedding-3-small", emb_resp.usage.total_tokens, 0, emb_cost, "Budget experiment - Embeddings")
    print(f"  Done: {emb_resp.usage.total_tokens} tokens, dimensions={len(emb_resp.data[0].embedding)}")

    # Save embeddings for potential visualization
    embeddings_data = {
        "texts": texts_to_embed,
        "embeddings": [e.embedding[:10] for e in emb_resp.data],  # First 10 dims only for readability
        "full_dimensions": len(emb_resp.data[0].embedding),
    }
    with open(OUTPUT_DIR / "embeddings_sample.json", "w") as f:
        json.dump(embeddings_data, f, indent=2, ensure_ascii=False)
except Exception as e:
    print(f"  Error: {e}")
    experiments.append({"name": "embeddings", "error": str(e)})

# ============================================================
# Experiment 6: GPT-5.2 Bulk Analysis (cheap model, high volume)
# ============================================================
print("\n=== Experiment 6: GPT-5.2 Bulk Analysis ===")
analysis_topics = [
    "AIエージェントの自律性レベルを1-5で分類し、各レベルの具体例を挙げてください",
    "マルチエージェントシステムの合議アルゴリズムを5つ比較してください",
    "2026年時点でのLLMの主要な限界と克服策を論じてください",
    "AIプロジェクトのコスト最適化戦略を10個提案してください",
    "GPT-5とGPT-5.1の使い分け基準を実務者向けに解説してください",
]

bulk_results = []
for i, topic in enumerate(analysis_topics):
    print(f"  [{i+1}/{len(analysis_topics)}] {topic[:40]}...")
    start = time.time()
    try:
        resp_b = client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {"role": "system", "content": "あなたはAI技術の専門家です。詳細かつ実践的な分析を提供してください。"},
                {"role": "user", "content": topic},
            ],
            max_completion_tokens=4096,
        )
        elapsed = time.time() - start
        usage_b = resp_b.usage
        cost_b = (usage_b.prompt_tokens / 1000) * PRICING["gpt-5.2"]["input"] + (usage_b.completion_tokens / 1000) * PRICING["gpt-5.2"]["output"]
        total_cost += cost_b
        answer_b = resp_b.choices[0].message.content
        bulk_results.append({
            "topic": topic,
            "model": "gpt-5.2",
            "elapsed": round(elapsed, 2),
            "tokens": usage_b.total_tokens,
            "cost": round(cost_b, 6),
            "answer_length": len(answer_b),
        })
        tracker = log_api_call(tracker, "gpt-5.2", usage_b.prompt_tokens, usage_b.completion_tokens, cost_b, f"Budget experiment - Bulk analysis #{i+1}")
        print(f"    {usage_b.total_tokens} tokens, ${cost_b:.6f}, {elapsed:.1f}s")

        # Save each analysis
        with open(OUTPUT_DIR / f"analysis_{i+1}.txt", "w") as f:
            f.write(f"Topic: {topic}\nModel: gpt-5.2\n\n{answer_b}")
    except Exception as e:
        print(f"    Error: {e}")
        bulk_results.append({"topic": topic, "error": str(e)})

experiments.append({
    "name": "bulk_analysis_gpt52",
    "model": "gpt-5.2",
    "num_queries": len(analysis_topics),
    "results": bulk_results,
})

# ============================================================
# Save all results
# ============================================================
summary = {
    "experiment": "budget_experiment",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "experiments": experiments,
    "total_estimated_cost": round(total_cost, 4),
    "budget_remaining": round(10000 - total_cost, 2),
}
with open(OUTPUT_DIR / "budget_experiment.json", "w") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

# Save tracker
save_tracker(tracker)

print(f"\n{'='*60}")
print(f"  BUDGET EXPERIMENT COMPLETE")
print(f"{'='*60}")
print(f"  Total estimated cost: ${total_cost:.4f}")
print(f"  Budget remaining: ${10000 - total_cost:.2f}")
print(f"  Results saved to {OUTPUT_DIR / 'budget_experiment.json'}")
print(f"  Tracker updated: {TRACKER_FILE}")
print(f"{'='*60}")
