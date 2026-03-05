#!/usr/bin/env python3
"""Mass parallel deliberation - burn through budget with 20+ topics."""
import json, time, os, sys, asyncio
from datetime import datetime, timezone
from pathlib import Path
from openai import AsyncAzureOpenAI

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

AZURE_ENDPOINT = "https://canaveral.openai.azure.com/"
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "REDACTED_AZURE_OPENAI_KEY_2")
API_VERSION = "2024-12-01-preview"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
COSTS_DIR = Path(__file__).parent.parent / "costs"
TRACKER_FILE = COSTS_DIR / "tracker.json"

# Model selection: GPT-5 for deep deliberation, GPT-5.1 for fast/cheap
# Use GPT-5 for high-value topics, GPT-5.1 for bulk
MODELS = {
    "deep": "gpt-5",      # ~$1.67 per full deliberation
    "standard": "gpt-5.1", # ~$0.30 per full deliberation
    "fast": "gpt-5.2",     # ~$0.10 per full deliberation
}

PRICING = {
    "gpt-5": {"input": 0.01, "output": 0.03},
    "gpt-5.1": {"input": 0.005, "output": 0.015},
    "gpt-5.2": {"input": 0.003, "output": 0.006},
}

# 20 deliberation topics spanning diverse domains
TOPICS = [
    # Tier 1: Deep (GPT-5) - controversial/complex topics
    ("deep", "2030年までにAGI(汎用人工知能)は実現するか？実現した場合の社会的影響と、実現しなかった場合のAI産業への影響を論じよ"),
    ("deep", "日本は移民政策を大幅に緩和すべきか？人口減少、経済成長、文化的アイデンティティの観点から"),
    ("deep", "暗号通貨は法定通貨に取って代わるべきか？金融安定性、プライバシー、マネーロンダリング対策の観点から"),

    # Tier 2: Standard (GPT-5.1) - policy/ethics topics
    ("standard", "完全自動運転車の事故における法的責任は誰が負うべきか？メーカー、ソフトウェア開発者、所有者、それとも新たな法的主体か"),
    ("standard", "ベーシックインカムは日本で実現可能か？財源、労働意欲、社会保障制度との整合性を検討せよ"),
    ("standard", "リモートワークを原則とする働き方は生産性を向上させるか？メンタルヘルス、イノベーション、都市計画の観点から"),
    ("standard", "SNSプラットフォームは言論の自由をどこまで制限すべきか？ヘイトスピーチ、フェイクニュース、民主主義への影響"),
    ("standard", "宇宙開発は民間企業に任せるべきか？国際協力、安全保障、科学的探求のバランス"),
    ("standard", "遺伝子編集技術（CRISPR）をヒト胚に適用すべきか？医療倫理、社会的公平性、進化への介入"),
    ("standard", "原子力発電は気候変動対策として再評価すべきか？安全性、コスト、再生可能エネルギーとの比較"),

    # Tier 3: Fast (GPT-5.2) - lighter topics for volume
    ("fast", "AIが生成した芸術作品に著作権を認めるべきか"),
    ("fast", "大学教育は無償化すべきか"),
    ("fast", "動物実験は全面的に禁止すべきか"),
    ("fast", "18歳選挙権を16歳に引き下げるべきか"),
    ("fast", "プログラミング教育を小学1年生から必修にすべきか"),
    ("fast", "食肉税を導入して環境負荷を下げるべきか"),
    ("fast", "AIによる顔認識技術を公共空間で使用すべきか"),
    ("fast", "週4日勤務制を法制化すべきか"),
    ("fast", "ソーシャルメディアの利用を16歳未満に禁止すべきか"),
    ("fast", "デジタル通貨（CBDC）を日本が導入すべきか"),
]

PERSONAS = [
    {
        "name": "MELCHIOR",
        "system": "あなたはMAGIシステムの合議AI「MELCHIOR（メルキオール）」です。科学者としての視点から、データと論理に基づいて分析してください。感情的な議論ではなく、エビデンスと技術的実現可能性を重視します。",
    },
    {
        "name": "BALTHASAR",
        "system": "あなたはMAGIシステムの合議AI「BALTHASAR（バルタザール）」です。母親としての視点から、人間の幸福と社会的影響を重視して分析してください。弱者への配慮と持続可能性を大切にします。",
    },
    {
        "name": "CASPER",
        "system": "あなたはMAGIシステムの合議AI「CASPER（カスパー）」です。女性としての視点から、現実的な実装可能性と政治的バランスを考慮して分析してください。理想と現実の橋渡しを目指します。",
    },
]


async def run_single_deliberation(
    client: AsyncAzureOpenAI,
    topic: str,
    model: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Run a single 3-phase deliberation."""
    result = {
        "topic": topic,
        "model": model,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "phases": {},
        "total_tokens": 0,
        "total_cost": 0.0,
    }
    pricing = PRICING[model]

    is_reasoning_model = model == "gpt-5"

    async def call_llm(system: str, user_msg: str, max_tokens: int = 1024) -> tuple[str, dict]:
        async with semaphore:
            kwargs = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "max_completion_tokens": max_tokens,
            }
            if not is_reasoning_model:
                kwargs["temperature"] = 0.8

            resp = await client.chat.completions.create(**kwargs)
            usage = resp.usage
            cost = (usage.prompt_tokens / 1000) * pricing["input"] + (usage.completion_tokens / 1000) * pricing["output"]
            return resp.choices[0].message.content, {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "reasoning_tokens": getattr(getattr(usage, 'completion_tokens_details', None), 'reasoning_tokens', 0) or 0,
                "cost": round(cost, 6),
            }

    try:
        # Phase 1: Independent Analysis (parallel for 3 personas)
        phase1_tasks = []
        for p in PERSONAS:
            prompt = f"以下のテーマについて、あなたの視点から独立して分析してください。最終的にAPPROVE（承認）、REJECT（却下）、CONDITIONAL（条件付き承認）のいずれかの立場を取ることになりますが、まずは多角的に分析してください。\n\nテーマ: {topic}"
            phase1_tasks.append(call_llm(p["system"], prompt, 2048 if model == "gpt-5" else 1024))

        phase1_results = await asyncio.gather(*phase1_tasks, return_exceptions=True)
        phase1_data = []
        for i, r in enumerate(phase1_results):
            if isinstance(r, Exception):
                phase1_data.append({"persona": PERSONAS[i]["name"], "error": str(r)})
            else:
                content, usage_info = r
                phase1_data.append({"persona": PERSONAS[i]["name"], "analysis": content[:500], "usage": usage_info})
                result["total_tokens"] += usage_info["prompt_tokens"] + usage_info["completion_tokens"]
                result["total_cost"] += usage_info["cost"]

        result["phases"]["phase1_analysis"] = phase1_data

        # Phase 2: Debate (each persona responds to others)
        analyses_summary = "\n".join(
            f"[{d['persona']}]: {d.get('analysis', d.get('error', 'N/A'))[:300]}"
            for d in phase1_data
        )

        phase2_tasks = []
        for p in PERSONAS:
            prompt = f"他の2体のMAGIの分析を踏まえて、反論または補強してください。\n\nテーマ: {topic}\n\n各AIの分析:\n{analyses_summary}"
            phase2_tasks.append(call_llm(p["system"], prompt, 1024 if model == "gpt-5" else 512))

        phase2_results = await asyncio.gather(*phase2_tasks, return_exceptions=True)
        phase2_data = []
        for i, r in enumerate(phase2_results):
            if isinstance(r, Exception):
                phase2_data.append({"persona": PERSONAS[i]["name"], "error": str(r)})
            else:
                content, usage_info = r
                phase2_data.append({"persona": PERSONAS[i]["name"], "debate": content[:500], "usage": usage_info})
                result["total_tokens"] += usage_info["prompt_tokens"] + usage_info["completion_tokens"]
                result["total_cost"] += usage_info["cost"]

        result["phases"]["phase2_debate"] = phase2_data

        # Phase 3: Final Vote
        debate_summary = "\n".join(
            f"[{d['persona']}]: {d.get('debate', d.get('error', 'N/A'))[:200]}"
            for d in phase2_data
        )

        phase3_tasks = []
        for p in PERSONAS:
            prompt = f"最終投票を行ってください。以下のフォーマットで回答:\n投票: APPROVE / REJECT / CONDITIONAL\n理由: (100文字以内)\n条件: (CONDITIONALの場合のみ)\n\nテーマ: {topic}\n\n討論結果:\n{debate_summary}"
            phase3_tasks.append(call_llm(p["system"], prompt, 512 if model == "gpt-5" else 256))

        phase3_results = await asyncio.gather(*phase3_tasks, return_exceptions=True)
        phase3_data = []
        votes = []
        for i, r in enumerate(phase3_results):
            if isinstance(r, Exception):
                phase3_data.append({"persona": PERSONAS[i]["name"], "error": str(r)})
            else:
                content, usage_info = r
                # Extract vote
                vote = "UNKNOWN"
                for v in ["APPROVE", "REJECT", "CONDITIONAL"]:
                    if v in content.upper():
                        vote = v
                        break
                votes.append(vote)
                phase3_data.append({"persona": PERSONAS[i]["name"], "vote": vote, "reasoning": content[:300], "usage": usage_info})
                result["total_tokens"] += usage_info["prompt_tokens"] + usage_info["completion_tokens"]
                result["total_cost"] += usage_info["cost"]

        result["phases"]["phase3_votes"] = phase3_data

        # Determine consensus
        if len(set(votes)) == 1 and votes:
            result["consensus"] = f"UNANIMOUS {votes[0]}"
        elif votes.count("APPROVE") >= 2:
            result["consensus"] = "MAJORITY APPROVE"
        elif votes.count("REJECT") >= 2:
            result["consensus"] = "MAJORITY REJECT"
        elif votes.count("CONDITIONAL") >= 2:
            result["consensus"] = "MAJORITY CONDITIONAL"
        else:
            result["consensus"] = f"SPLIT ({', '.join(votes)})"

        result["end_time"] = datetime.now(timezone.utc).isoformat()
        result["status"] = "completed"

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


async def main():
    client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
    )

    # Concurrency limiter: 5 simultaneous API calls to avoid rate limits
    semaphore = asyncio.Semaphore(5)

    print(f"{'='*60}")
    print(f"  MAGI MASS DELIBERATION - {len(TOPICS)} Topics")
    print(f"  Started: {datetime.now().strftime('%H:%M:%S JST')}")
    print(f"{'='*60}")
    print(flush=True)

    all_results = []
    total_cost = 0.0
    total_tokens = 0
    start_time = time.time()

    # Group topics by tier for progress reporting
    deep_topics = [(t, m) for m, t in TOPICS if m == "deep"]
    standard_topics = [(t, m) for m, t in TOPICS if m == "standard"]
    fast_topics = [(t, m) for m, t in TOPICS if m == "fast"]

    print(f"  Deep (GPT-5): {len(deep_topics)} topics")
    print(f"  Standard (GPT-5.1): {len(standard_topics)} topics")
    print(f"  Fast (GPT-5.2): {len(fast_topics)} topics")
    print(flush=True)

    # Run all deliberations concurrently
    tasks = []
    for tier, topic in TOPICS:
        model = MODELS[tier]
        tasks.append(run_single_deliberation(client, topic, model, semaphore))

    # Process as they complete
    completed = 0
    for coro in asyncio.as_completed(tasks):
        result = await coro
        completed += 1
        status = result.get("status", "unknown")
        consensus = result.get("consensus", "N/A")
        cost = result.get("total_cost", 0)
        tokens = result.get("total_tokens", 0)
        total_cost += cost
        total_tokens += tokens

        topic_short = result["topic"][:40]
        print(f"  [{completed}/{len(TOPICS)}] {result['model']:8s} | {consensus:20s} | ${cost:.4f} | {tokens:>6} tok | {topic_short}...", flush=True)

        all_results.append(result)

        # Save incremental results
        if completed % 5 == 0:
            _save_results(all_results, total_cost, total_tokens, start_time)

    elapsed = time.time() - start_time

    # Final save
    _save_results(all_results, total_cost, total_tokens, start_time)

    # Update cost tracker
    _update_tracker(all_results)

    print(f"\n{'='*60}")
    print(f"  MASS DELIBERATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Topics: {len(all_results)}")
    print(f"  Completed: {sum(1 for r in all_results if r.get('status') == 'completed')}")
    print(f"  Errors: {sum(1 for r in all_results if r.get('status') == 'error')}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"{'='*60}")

    # Print consensus summary
    print(f"\n  CONSENSUS SUMMARY:")
    for r in all_results:
        if r.get("status") == "completed":
            print(f"    [{r['model']:8s}] {r['consensus']:20s} | {r['topic'][:50]}")


def _save_results(results, total_cost, total_tokens, start_time):
    summary = {
        "experiment": "mass_deliberation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_topics": len(results),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "elapsed_seconds": round(time.time() - start_time, 1),
        "results": results,
    }
    output_path = OUTPUT_DIR / "mass_deliberation.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def _update_tracker(results):
    if TRACKER_FILE.exists():
        with open(TRACKER_FILE) as f:
            tracker = json.load(f)
    else:
        tracker = {"api_calls": []}

    for r in results:
        if r.get("status") != "completed":
            continue
        for phase_name, phase_data in r.get("phases", {}).items():
            for persona_result in phase_data:
                usage = persona_result.get("usage", {})
                if usage:
                    tracker["api_calls"].append({
                        "timestamp": r.get("end_time", datetime.now(timezone.utc).isoformat()),
                        "model": r["model"],
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "estimated_cost_usd": usage.get("cost", 0),
                        "purpose": f"Mass deliberation - {r['topic'][:50]}",
                    })

    tracker["total_estimated_api_cost"] = round(
        sum(c["estimated_cost_usd"] for c in tracker["api_calls"]), 4
    )
    tracker["last_updated"] = datetime.now(timezone.utc).isoformat()

    COSTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRACKER_FILE, "w") as f:
        json.dump(tracker, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    asyncio.run(main())
