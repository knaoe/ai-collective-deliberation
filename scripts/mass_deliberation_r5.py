#!/usr/bin/env python3
"""Round 5: Mass parallel deliberation - 50 topics across 5 categories."""
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
# 50 new topics (10 per category)
# ============================================================
TOPICS = [
    # ---- Technology (10 topics) ----
    # deep (2): most complex
    ("deep", "量子コンピュータが実用化された場合、現在の暗号通貨・銀行システム・国家安全保障はどのように再設計されるべきか？移行期のリスクと対策を含めて論じよ"),
    ("deep", "汎用ロボットが家庭に普及した2035年の社会を予測せよ。雇用、教育、介護、プライバシー、人間関係への影響を包括的に分析すること"),
    # standard (4)
    ("standard", "AI搭載の自律型兵器（LAWS）を国際条約で全面禁止すべきか？抑止力、非対称戦争、人道法の観点から"),
    ("standard", "脳コンピュータインターフェース（BCI）の商用利用をどこまで許容すべきか？治療目的と能力増強の線引き"),
    ("standard", "オープンソースAIモデルの規制は必要か？イノベーション促進とバイオ兵器・ディープフェイク等の悪用防止のバランス"),
    ("standard", "6G通信が実現する2030年代、デジタルデバイドは解消されるか、それとも深刻化するか"),
    # fast (4)
    ("fast", "プログラミングはAIの発展により不要なスキルになるか"),
    ("fast", "スマートシティは監視社会への入口か、生活向上のツールか"),
    ("fast", "量子暗号通信は10年以内に商用化されるか"),
    ("fast", "AIチューターは人間の教師を代替できるか"),

    # ---- Society & Politics (10 topics) ----
    # deep (2)
    ("deep", "少子高齢化が進む日本で2050年の社会保障制度はどうあるべきか？年金、医療、介護の抜本改革案を提示し、財源・実現可能性・世代間公平性を論じよ"),
    ("deep", "気候変動対策として先進国は途上国にどこまで補償責任を負うべきか？歴史的排出量、技術移転、経済成長の権利、気候正義の概念を踏まえて"),
    # standard (4)
    ("standard", "義務教育にAIリテラシーとクリティカルシンキングを中心に据えたカリキュラム改革は必要か"),
    ("standard", "医療データの国家統合プラットフォームを構築すべきか？プライバシーと公衆衛生のトレードオフ"),
    ("standard", "格差社会における相続税の大幅引き上げは公平か？富の再分配と経済的自由の観点から"),
    ("standard", "選挙にブロックチェーン投票を導入すべきか？セキュリティ、透明性、アクセシビリティの観点から"),
    # fast (4)
    ("fast", "死刑制度は廃止すべきか"),
    ("fast", "高校までの教育を完全無償化すべきか"),
    ("fast", "マイナンバーに全ての行政サービスを統合すべきか"),
    ("fast", "外国人参政権（地方選挙）を認めるべきか"),

    # ---- Ethics & Philosophy (10 topics) ----
    # deep (2)
    ("deep", "AIシステムに「意識」が芽生える可能性はあるか？もし意識を持つAIが現れた場合、道徳的地位と権利をどう定義すべきか。哲学的ゾンビ問題、統合情報理論、機能主義の観点から"),
    ("deep", "自由意志は幻想か？神経科学の決定論的知見と量子力学の不確定性を踏まえ、道徳的責任・刑事司法・日常の意思決定への含意を論じよ"),
    # standard (4)
    ("standard", "トロッコ問題の現代版：自動運転AIはどのような倫理的フレームワークでプログラムされるべきか"),
    ("standard", "デジタル上の「忘れられる権利」はどこまで拡張されるべきか？歴史保存とプライバシーの衝突"),
    ("standard", "人間の寿命を200年に延ばす技術が実現した場合、社会は寿命延長を全員に提供する義務があるか"),
    ("standard", "動物に法的人格を付与すべきか？大型類人猿、イルカ、象を対象に検討せよ"),
    # fast (4)
    ("fast", "嘘をつくことは常に道徳的に悪いことか"),
    ("fast", "「正義」の定義は文化によって異なるべきか、普遍的であるべきか"),
    ("fast", "安楽死を合法化すべきか"),
    ("fast", "子どもの遺伝子を選んで「デザイナーベビー」を作ることは許されるか"),

    # ---- Economy & Business (10 topics) ----
    # deep (2)
    ("deep", "AI・ロボティクスによる大量失業は2030年代に現実化するか？ルーティンワークだけでなく知的労働も含めた影響分析と、UBI・再訓練・新産業創出の実効性を論じよ"),
    ("deep", "中央銀行デジタル通貨（CBDC）が世界的に普及した場合の国際金融秩序の再編を予測せよ。ドル覇権、金融制裁、クロスボーダー決済、プライバシーへの影響"),
    # standard (4)
    ("standard", "スタートアップエコシステムの活性化のために日本が最優先で取り組むべき制度改革は何か"),
    ("standard", "ギグエコノミーの労働者に正規雇用と同等の社会保障を提供すべきか"),
    ("standard", "国際貿易におけるカーボンボーダー税は公平か？WTOルールとの整合性と途上国への影響"),
    ("standard", "企業のAI導入による生産性向上の利益は、株主・経営者・従業員にどう分配されるべきか"),
    # fast (4)
    ("fast", "暗号資産は投資対象として年金基金に組み入れるべきか"),
    ("fast", "週休3日制は企業の生産性を下げるか上げるか"),
    ("fast", "サブスクリプション経済は消費者にとって得か損か"),
    ("fast", "日本の農業は株式会社化で再生できるか"),

    # ---- Culture & Future (10 topics) ----
    # deep (2)
    ("deep", "人類が火星に恒久的な居住地を建設する場合、どのような統治機構・法体系・経済システムが適切か？地球との関係、資源配分、文化形成の観点から包括的に論じよ"),
    ("deep", "メタバースが生活の主要な場になった2040年の社会を予測せよ。アイデンティティ、経済活動、法律、精神健康、物理世界との関係性への影響を分析すること"),
    # standard (4)
    ("standard", "宇宙資源採掘の利益は全人類に分配されるべきか？宇宙条約の再解釈と民間企業の権利"),
    ("standard", "100歳まで健康に生きられる社会で、定年・年金・教育のライフコースはどう変わるべきか"),
    ("standard", "AIが生成するエンターテインメント（映画、音楽、ゲーム）は人間の創造性を枯渇させるか豊かにするか"),
    ("standard", "宇宙エレベーターの建設は国際プロジェクトとして推進すべきか。技術的・経済的・政治的実現可能性"),
    # fast (4)
    ("fast", "タイムトラベルが可能になったら法律はどうあるべきか"),
    ("fast", "不老不死の技術が完成したら人類は幸福になるか"),
    ("fast", "地球外知的生命体が発見された場合、人類はどう対応すべきか"),
    ("fast", "完全な仮想世界での生活は「本物の」人生と言えるか"),
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
            phase1_tasks.append(call_llm(p["system"], prompt, 4096 if model == "gpt-5" else 1024))

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
            phase2_tasks.append(call_llm(p["system"], prompt, 2048 if model == "gpt-5" else 512))

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
            phase3_tasks.append(call_llm(p["system"], prompt, 1024 if model == "gpt-5" else 256))

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
        result["error"] = str(e)

    return result


async def main():
    client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
        timeout=600.0,  # 10 minute timeout
    )

    # Concurrency limiter: 8 simultaneous API calls for speed
    semaphore = asyncio.Semaphore(8)

    print(f"{'='*70}")
    print(f"  MAGI MASS DELIBERATION ROUND 5 - {len(TOPICS)} Topics")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}")
    print(f"{'='*70}")
    print(flush=True)

    all_results = []
    total_cost = 0.0
    total_tokens = 0
    start_time = time.time()

    # Group topics by tier for progress reporting
    deep_count = sum(1 for m, _ in TOPICS if m == "deep")
    standard_count = sum(1 for m, _ in TOPICS if m == "standard")
    fast_count = sum(1 for m, _ in TOPICS if m == "fast")

    print(f"  Deep (GPT-5): {deep_count} topics  (~$0.33/topic)")
    print(f"  Standard (GPT-5.1): {standard_count} topics  (~$0.09/topic)")
    print(f"  Fast (GPT-5.2): {fast_count} topics  (~$0.03/topic)")
    print(f"  Estimated total cost: ~$5.70")
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
        print(f"  [{completed:2d}/{len(TOPICS)}] {result['model']:8s} | {consensus:20s} | ${cost:.4f} | {tokens:>6} tok | {topic_short}...", flush=True)

        all_results.append(result)

        # Save incremental results every 5 topics
        if completed % 5 == 0:
            _save_results(all_results, total_cost, total_tokens, start_time)

    elapsed = time.time() - start_time

    # Final save
    _save_results(all_results, total_cost, total_tokens, start_time)

    # Update cost tracker
    _update_tracker(all_results)

    print(f"\n{'='*70}")
    print(f"  MASS DELIBERATION ROUND 5 COMPLETE")
    print(f"{'='*70}")
    print(f"  Topics: {len(all_results)}")
    print(f"  Completed: {sum(1 for r in all_results if r.get('status') == 'completed')}")
    print(f"  Errors: {sum(1 for r in all_results if r.get('status') == 'error')}")
    print(f"  Total tokens: {total_tokens:,}")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Elapsed: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"  Avg cost/topic: ${total_cost/max(len(all_results),1):.4f}")
    print(f"{'='*70}")

    # Print consensus summary by category
    print(f"\n  CONSENSUS SUMMARY:")
    categories = [
        ("Technology", 0, 10),
        ("Society & Politics", 10, 20),
        ("Ethics & Philosophy", 20, 30),
        ("Economy & Business", 30, 40),
        ("Culture & Future", 40, 50),
    ]
    for cat_name, start_idx, end_idx in categories:
        print(f"\n  --- {cat_name} ---")
        # Match results to topics by topic text
        cat_topics = [t for _, t in TOPICS[start_idx:end_idx]]
        for r in all_results:
            if r["topic"] in cat_topics and r.get("status") == "completed":
                print(f"    [{r['model']:8s}] {r['consensus']:20s} | {r['topic'][:50]}")


def _save_results(results, total_cost, total_tokens, start_time):
    summary = {
        "experiment": "mass_deliberation_r5",
        "round": 5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_topics": len(results),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "elapsed_seconds": round(time.time() - start_time, 1),
        "model_breakdown": {
            "gpt-5": {
                "count": sum(1 for r in results if r["model"] == "gpt-5"),
                "cost": round(sum(r["total_cost"] for r in results if r["model"] == "gpt-5"), 4),
                "tokens": sum(r["total_tokens"] for r in results if r["model"] == "gpt-5"),
            },
            "gpt-5.1": {
                "count": sum(1 for r in results if r["model"] == "gpt-5.1"),
                "cost": round(sum(r["total_cost"] for r in results if r["model"] == "gpt-5.1"), 4),
                "tokens": sum(r["total_tokens"] for r in results if r["model"] == "gpt-5.1"),
            },
            "gpt-5.2": {
                "count": sum(1 for r in results if r["model"] == "gpt-5.2"),
                "cost": round(sum(r["total_cost"] for r in results if r["model"] == "gpt-5.2"), 4),
                "tokens": sum(r["total_tokens"] for r in results if r["model"] == "gpt-5.2"),
            },
        },
        "results": results,
    }
    output_path = OUTPUT_DIR / "mass_deliberation_r5.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
                        "purpose": f"R5 Mass deliberation - {r['topic'][:50]}",
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
