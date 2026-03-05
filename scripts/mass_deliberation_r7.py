#!/usr/bin/env python3
"""Round 7: Mass deliberation - 50 topics across 5 categories with retry logic and graceful error handling."""
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
# 50 NEW topics - no overlap with R1-R6 (99 existing topics)
# 5 categories x 10 topics each: deep 2 + standard 4 + fast 4
# ============================================================
TOPICS = [
    # ---- Category 1: Science & Technology (10 topics) ----
    ("deep", "量子インターネットが2035年に実用化された場合、通信・暗号技術・国家安全保障・科学研究のパラダイムはどう変わるか？古典インターネットとの共存期における課題と移行戦略を論じよ"),
    ("deep", "人工光合成技術が大規模に実現した場合、化石燃料産業・農業・化学工業にどのような構造転換をもたらすか？CO2回収との相乗効果と技術的ボトルネックを分析せよ"),
    ("standard", "ニューラリンクのような脳埋め込みデバイスは一般消費者に普及すべきか"),
    ("standard", "AIによる科学論文の自動生成は学術研究の質を向上させるか劣化させるか"),
    ("standard", "小型モジュール型原子炉（SMR）は次世代エネルギーの本命となりうるか"),
    ("standard", "宇宙デブリ問題の解決責任は誰が負うべきか？国家・企業・国際機関の役割分担"),
    ("fast", "量子センサーは医療診断を根本的に変えるか"),
    ("fast", "3Dプリンタで建設した住宅は主流になるか"),
    ("fast", "室温超伝導体は2040年までに発見されるか"),
    ("fast", "合成データでAIを訓練することは実データと同等の成果を生むか"),

    # ---- Category 2: Society (10 topics) ----
    ("deep", "少子化対策として「子どもを持つことへの経済的インセンティブ」は有効か？北欧モデル・東アジアモデル・イスラエルモデルを比較し、日本の出生率回復に最も効果的な政策パッケージを提案せよ"),
    ("deep", "2040年の高齢者介護は人間とロボットのどちらが主体となるべきか？尊厳・コスト・人材不足・テクノロジーの限界を包括的に分析し、最適なハイブリッドモデルを設計せよ"),
    ("standard", "公共交通機関を全面無償化すべきか？都市計画・財源・環境・社会的公平性の観点から"),
    ("standard", "テレワーク時代に地方移住を促進する政策は都市一極集中を解消できるか"),
    ("standard", "高齢ドライバーの免許返納を義務化すべきか？移動の自由と公共安全のバランス"),
    ("standard", "監視カメラの街中への大量設置は犯罪抑止に有効か、それともプライバシーの侵害か"),
    ("fast", "選挙の投票年齢を13歳に引き下げるべきか"),
    ("fast", "夫婦別姓は日本で法制化すべきか"),
    ("fast", "刑務所は更生施設としてリデザインすべきか"),
    ("fast", "公共施設における喫煙を全面禁止すべきか"),

    # ---- Category 3: Ethics (10 topics) ----
    ("deep", "AIが人間の感情を正確に読み取れるようになった場合、その技術の利用にどのような倫理的制約を設けるべきか？採用面接・教育現場・刑事捜査・マーケティングにおける具体的ガイドラインを提案せよ"),
    ("deep", "死後のデジタル人格（故人のAIアバター）の作成・運用に関する倫理的・法的フレームワークをどう構築すべきか？遺族の権利、故人の尊厳、ビジネス利用の規制を論じよ"),
    ("standard", "企業がAI倫理委員会を設置することを法律で義務化すべきか"),
    ("standard", "AIによるディープフェイクポルノの作成・配布に対して厳罰化は有効か"),
    ("standard", "戦争における民間軍事会社（PMC）の利用は倫理的に許容されるか"),
    ("standard", "人間のクローン作成を研究目的に限定して許可すべきか"),
    ("fast", "AI搭載の監視ドローンを警察が日常的に使用することは許されるか"),
    ("fast", "遺伝情報に基づく保険料の差別化は認められるべきか"),
    ("fast", "動物園は廃止すべきか"),
    ("fast", "ロボットに「電子人格」として法的権利を与えるべきか"),

    # ---- Category 4: Economy (10 topics) ----
    ("deep", "日本の国家債務がGDP比300%を超えた場合のシナリオ分析を行え。財政破綻・ハイパーインフレ・段階的調整の3シナリオについて、国民生活・国際的信用・金融市場への影響を論じよ"),
    ("deep", "プラットフォーム経済の独占問題に対して、GAFAMの分割は有効な解決策か？反トラスト法の限界、イノベーションへの影響、消費者利益、代替的規制アプローチを包括的に分析せよ"),
    ("standard", "全ての企業にESG情報の開示を義務化すべきか？グリーンウォッシングの防止と中小企業への負担"),
    ("standard", "不動産の外国人所有を制限すべきか？経済自由主義と国家安全保障の観点から"),
    ("standard", "労働時間ではなく成果に基づく賃金体系は全業種に適用可能か"),
    ("standard", "年金受給開始年齢を75歳に引き上げることは現実的か"),
    ("fast", "NFTはデジタル資産の所有権証明として生き残るか"),
    ("fast", "最低賃金を全国一律にすべきか"),
    ("fast", "日本の農業に大規模な外国人労働者受け入れは必要か"),
    ("fast", "宇宙産業は2040年までに100兆円市場になるか"),

    # ---- Category 5: Culture (10 topics) ----
    ("deep", "AIが文学・音楽・映像を高品質に生成できる時代に、人間のアーティストの社会的役割と価値はどう再定義されるべきか？著作権制度、芸術教育、文化政策の抜本的改革案を提示せよ"),
    ("deep", "日本語が2100年までに消滅の危機に瀕する可能性はあるか？グローバル化・AI翻訳の普及・少子化による話者減少を考慮し、言語保存と文化的アイデンティティの維持策を論じよ"),
    ("standard", "図書館は紙の書籍を廃止して完全デジタル化すべきか"),
    ("standard", "伝統的な祭りや文化行事に公的資金を投入し続ける正当性はあるか"),
    ("standard", "AIが生成したコンテンツにはその旨のラベル表示を義務化すべきか"),
    ("standard", "日本のアニメ・マンガ産業は国策として保護すべきか、それとも市場に委ねるべきか"),
    ("fast", "紙の新聞は10年以内に消滅するか"),
    ("fast", "美術館の入場料を無料にすべきか"),
    ("fast", "方言は積極的に保存すべきか、自然消滅に任せるべきか"),
    ("fast", "音楽教育は義務教育から外してもよいか"),
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
        "experiment": "mass_deliberation_r7",
        "round": 7,
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

    output_path = OUTPUT_DIR / "mass_deliberation_r7.json"
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
                            "purpose": f"R7 Mass deliberation - {r['topic'][:50]}",
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
        timeout=600.0,  # 10 minute client-level timeout
    )

    # Conservative concurrency: 5 simultaneous API calls
    semaphore = asyncio.Semaphore(5)

    print(f"{'='*70}")
    print(f"  MAGI MASS DELIBERATION ROUND 7 - {len(TOPICS)} Topics")
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

    # Process in batches of 10 to avoid overwhelming the API
    BATCH_SIZE = 10
    completed = 0
    for batch_start in range(0, len(TOPICS), BATCH_SIZE):
        batch = TOPICS[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(TOPICS) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n  --- Batch {batch_num}/{total_batches} ({len(batch)} topics) ---", flush=True)

        tasks = []
        for tier, topic in batch:
            model = MODELS[tier]
            tasks.append(run_single_deliberation(client, topic, model, semaphore))

        # Process batch as they complete
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
    print(f"  MASS DELIBERATION ROUND 7 COMPLETE")
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
        ("Science & Technology", 0, 10),
        ("Society", 10, 20),
        ("Ethics", 20, 30),
        ("Economy", 30, 40),
        ("Culture", 40, 50),
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
