#!/usr/bin/env python3
"""Round 6: Robust mass deliberation - 30 topics with retry logic and graceful error handling."""
import json, time, os, sys, asyncio, traceback
from datetime import datetime, timezone
from pathlib import Path
from openai import AsyncAzureOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))

AZURE_ENDPOINT = "https://canaveral.openai.azure.com/"
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "REDACTED_AZURE_OPENAI_KEY_2")
API_VERSION = "2024-12-01-preview"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
COSTS_DIR = Path(__file__).parent.parent / "costs"
TRACKER_FILE = COSTS_DIR / "tracker.json"

MODELS = {
    "deep": "gpt-5",
    "standard": "gpt-5.1",
    "fast": "gpt-5.2",
}

PRICING = {
    "gpt-5": {"input": 0.01, "output": 0.03},
    "gpt-5.1": {"input": 0.005, "output": 0.015},
    "gpt-5.2": {"input": 0.003, "output": 0.006},
}

# ============================================================
# 30 NEW topics - no overlap with R1-R5
# ============================================================
TOPICS = [
    # ---- Science & Space (6 topics) ----
    ("deep", "核融合発電が2040年に商用化された場合、エネルギー地政学・電力網設計・産業構造はどう変容するか？石油依存国の経済転換と再生可能エネルギーとの共存シナリオを論じよ"),
    ("standard", "深海資源開発は推進すべきか？レアメタル確保の戦略的意義と海洋生態系保全の両立"),
    ("standard", "合成生物学で作られた人工生命体に特許を認めるべきか"),
    ("fast", "月面基地は2040年までに実現するか"),
    ("fast", "太陽光発電衛星は地上の再生可能エネルギーに勝るか"),
    ("fast", "人工冬眠技術は深宇宙探査に不可欠か"),

    # ---- Education & Youth (6 topics) ----
    ("deep", "生成AIが学習ツールとして浸透した教育現場で、「考える力」をどう評価・育成すべきか？試験制度、カリキュラム設計、教師の役割の抜本的見直しを提案せよ"),
    ("standard", "大学入試を廃止し、高校卒業資格のみで大学進学を可能にすべきか"),
    ("standard", "子どものスマートフォン所有に年齢制限を設けるべきか？発達心理学と情報アクセス権の観点から"),
    ("fast", "学校の制服は廃止すべきか"),
    ("fast", "小学校で金融リテラシー教育は必要か"),
    ("fast", "eスポーツを正式な部活動として認めるべきか"),

    # ---- Healthcare & Life Sciences (6 topics) ----
    ("deep", "遺伝子治療が一般化した社会で、「治療」と「強化」の境界をどう定めるべきか？医療保険の適用範囲、社会的不平等への影響、人間の多様性の価値を包括的に分析せよ"),
    ("standard", "パンデミック対策として各国はワクチンの強制接種権限を持つべきか"),
    ("standard", "精神疾患の治療にサイケデリクス（幻覚剤）を医療利用すべきか"),
    ("fast", "臓器売買を合法化すべきか"),
    ("fast", "美容整形に年齢制限を設けるべきか"),
    ("fast", "AIによる医療診断は医師の診断より信頼できるか"),

    # ---- Governance & Law (6 topics) ----
    ("deep", "AIが立法・司法・行政の意思決定を補助する「AI統治」は民主主義を強化するか？アルゴリズム透明性、説明責任、市民参加の変容を論じよ"),
    ("standard", "インターネット上の匿名性を制限し実名制を義務化すべきか"),
    ("standard", "多国籍テック企業への「デジタル税」は公平で実効性があるか"),
    ("fast", "投票を義務化すべきか"),
    ("fast", "大麻の合法化は日本で実現すべきか"),
    ("fast", "AIが書いた契約書は法的に有効か"),

    # ---- Environment & Sustainability (6 topics) ----
    ("deep", "地球工学（ジオエンジニアリング）による気候変動対策は許容されるべきか？成層圏エアロゾル注入・海洋鉄肥沃化等の技術的リスク、倫理的問題、国際合意形成の課題を包括的に論じよ"),
    ("standard", "食品ロス削減のために賞味期限表示を廃止すべきか"),
    ("standard", "全ての新築住宅にソーラーパネル設置を義務化すべきか"),
    ("fast", "ファストファッションに環境税を課すべきか"),
    ("fast", "ペットボトル飲料を全面禁止すべきか"),
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

MAX_RETRIES = 3
RETRY_DELAY_BASE = 5  # seconds, exponential backoff


async def call_llm_with_retry(
    client: AsyncAzureOpenAI,
    model: str,
    system: str,
    user_msg: str,
    max_tokens: int,
    semaphore: asyncio.Semaphore,
    pricing: dict,
    is_reasoning_model: bool,
) -> tuple[str, dict]:
    """Call the LLM with retry logic and per-call timeout."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
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

                resp = await asyncio.wait_for(
                    client.chat.completions.create(**kwargs),
                    timeout=300.0,  # 5 minute per-call timeout
                )
                usage = resp.usage
                cost = (usage.prompt_tokens / 1000) * pricing["input"] + (usage.completion_tokens / 1000) * pricing["output"]
                return resp.choices[0].message.content, {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "reasoning_tokens": getattr(getattr(usage, 'completion_tokens_details', None), 'reasoning_tokens', 0) or 0,
                    "cost": round(cost, 6),
                }
        except asyncio.TimeoutError:
            last_error = f"Timeout after 300s (attempt {attempt}/{MAX_RETRIES})"
            print(f"    [RETRY] {last_error}", flush=True)
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:200]} (attempt {attempt}/{MAX_RETRIES})"
            print(f"    [RETRY] {last_error}", flush=True)

        if attempt < MAX_RETRIES:
            delay = RETRY_DELAY_BASE * (2 ** (attempt - 1))
            await asyncio.sleep(delay)

    raise RuntimeError(f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")


async def run_single_deliberation(
    client: AsyncAzureOpenAI,
    topic: str,
    model: str,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Run a single 3-phase deliberation with robust error handling."""
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

    try:
        # Phase 1: Independent Analysis (parallel for 3 personas)
        phase1_tasks = []
        for p in PERSONAS:
            prompt = f"以下のテーマについて、あなたの視点から独立して分析してください。最終的にAPPROVE（承認）、REJECT（却下）、CONDITIONAL（条件付き承認）のいずれかの立場を取ることになりますが、まずは多角的に分析してください。\n\nテーマ: {topic}"
            phase1_tasks.append(
                call_llm_with_retry(client, model, p["system"], prompt,
                                    2048 if model == "gpt-5" else 1024,
                                    semaphore, pricing, is_reasoning_model)
            )

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

        # Phase 2: Debate
        analyses_summary = "\n".join(
            f"[{d['persona']}]: {d.get('analysis', d.get('error', 'N/A'))[:300]}"
            for d in phase1_data
        )

        phase2_tasks = []
        for p in PERSONAS:
            prompt = f"他の2体のMAGIの分析を踏まえて、反論または補強してください。\n\nテーマ: {topic}\n\n各AIの分析:\n{analyses_summary}"
            phase2_tasks.append(
                call_llm_with_retry(client, model, p["system"], prompt,
                                    1024 if model == "gpt-5" else 512,
                                    semaphore, pricing, is_reasoning_model)
            )

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
            phase3_tasks.append(
                call_llm_with_retry(client, model, p["system"], prompt,
                                    512 if model == "gpt-5" else 256,
                                    semaphore, pricing, is_reasoning_model)
            )

        phase3_results = await asyncio.gather(*phase3_tasks, return_exceptions=True)
        phase3_data = []
        votes = []
        for i, r in enumerate(phase3_results):
            if isinstance(r, Exception):
                phase3_data.append({"persona": PERSONAS[i]["name"], "error": str(r)})
            else:
                content, usage_info = r
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
        result["error"] = f"{type(e).__name__}: {str(e)[:500]}"
        result["end_time"] = datetime.now(timezone.utc).isoformat()
        print(f"    [ERROR] Topic failed: {topic[:40]}... -> {result['error'][:100]}", flush=True)

    return result


def _save_results(results, total_cost, total_tokens, start_time):
    summary = {
        "experiment": "mass_deliberation_r6",
        "round": 6,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_topics": len(results),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "elapsed_seconds": round(time.time() - start_time, 1),
        "model_breakdown": {},
        "results": results,
    }
    for model_name in ["gpt-5", "gpt-5.1", "gpt-5.2"]:
        model_results = [r for r in results if r["model"] == model_name]
        summary["model_breakdown"][model_name] = {
            "count": len(model_results),
            "cost": round(sum(r["total_cost"] for r in model_results), 4),
            "tokens": sum(r["total_tokens"] for r in model_results),
        }

    output_path = OUTPUT_DIR / "mass_deliberation_r6.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"    [SAVED] {output_path} ({len(results)} results)", flush=True)


def _update_tracker(results):
    try:
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
                            "purpose": f"R6 Mass deliberation - {r['topic'][:50]}",
                        })

        tracker["total_estimated_api_cost"] = round(
            sum(c["estimated_cost_usd"] for c in tracker["api_calls"]), 4
        )
        tracker["last_updated"] = datetime.now(timezone.utc).isoformat()

        COSTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRACKER_FILE, "w") as f:
            json.dump(tracker, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"    [WARN] Failed to update tracker: {e}", flush=True)


async def main():
    client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
        timeout=300.0,  # 5 minute client-level timeout
    )

    # Conservative concurrency: 5 simultaneous API calls
    semaphore = asyncio.Semaphore(5)

    print(f"{'='*70}")
    print(f"  MAGI MASS DELIBERATION ROUND 6 - {len(TOPICS)} Topics")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}")
    print(f"{'='*70}")

    deep_count = sum(1 for m, _ in TOPICS if m == "deep")
    standard_count = sum(1 for m, _ in TOPICS if m == "standard")
    fast_count = sum(1 for m, _ in TOPICS if m == "fast")

    print(f"  Deep (GPT-5): {deep_count} topics")
    print(f"  Standard (GPT-5.1): {standard_count} topics")
    print(f"  Fast (GPT-5.2): {fast_count} topics")
    print(f"  Retry: up to {MAX_RETRIES} attempts per API call")
    print(f"  Semaphore: 5 concurrent calls")
    print(f"  Per-call timeout: 300s")
    print(flush=True)

    all_results = []
    total_cost = 0.0
    total_tokens = 0
    start_time = time.time()

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
        elapsed_so_far = time.time() - start_time
        print(f"  [{completed:2d}/{len(TOPICS)}] {result['model']:8s} | {status:9s} | {consensus:20s} | ${cost:.4f} | {tokens:>6} tok | {elapsed_so_far:.0f}s | {topic_short}...", flush=True)

        all_results.append(result)

        # Save incremental results every 5 topics
        if completed % 5 == 0:
            _save_results(all_results, total_cost, total_tokens, start_time)

    elapsed = time.time() - start_time

    # Final save
    _save_results(all_results, total_cost, total_tokens, start_time)

    # Update cost tracker
    _update_tracker(all_results)

    completed_count = sum(1 for r in all_results if r.get('status') == 'completed')
    error_count = sum(1 for r in all_results if r.get('status') == 'error')

    print(f"\n{'='*70}")
    print(f"  MASS DELIBERATION ROUND 6 COMPLETE")
    print(f"{'='*70}")
    print(f"  Topics: {len(all_results)}")
    print(f"  Completed: {completed_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    if completed_count > 0:
        print(f"  Avg cost/topic: ${total_cost/completed_count:.4f}")
    print(f"{'='*70}")

    # Print consensus summary
    categories = [
        ("Science & Space", 0, 6),
        ("Education & Youth", 6, 12),
        ("Healthcare & Life Sciences", 12, 18),
        ("Governance & Law", 18, 24),
        ("Environment & Sustainability", 24, 30),
    ]
    print(f"\n  CONSENSUS SUMMARY:")
    for cat_name, start_idx, end_idx in categories:
        print(f"\n  --- {cat_name} ---")
        cat_topics = [t for _, t in TOPICS[start_idx:end_idx]]
        for r in all_results:
            if r["topic"] in cat_topics:
                status_marker = "OK" if r.get("status") == "completed" else "ERR"
                print(f"    [{r['model']:8s}] [{status_marker}] {r.get('consensus', 'N/A'):20s} | {r['topic'][:50]}")


if __name__ == "__main__":
    asyncio.run(main())
