#!/usr/bin/env python3
"""Round 8: Massive deliberation - 80 topics for final push. Focus on GPT-5.2 for throughput."""
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
# 80 NEW topics - no overlap with R1-R7 (~160 existing topics)
# 8 categories x 10 topics: deep 1 + standard 3 + fast 6
# Estimated cost: ~$5-7
# ============================================================
TOPICS = [
    # ---- Daily Life (10) ----
    ("fast", "コンビニの24時間営業は維持すべきか"),
    ("fast", "通勤電車の女性専用車両は差別か"),
    ("fast", "マイナンバーカードの義務化は是か非か"),
    ("fast", "年賀状文化は廃止すべきか"),
    ("fast", "現金決済はいつ消滅するか"),
    ("fast", "PTA活動は任意にすべきか"),
    ("fast", "残業代ゼロ法案は労働者にとって有益か"),
    ("standard", "日本の移民政策は大幅に緩和すべきか"),
    ("standard", "タワーマンションの建設を規制すべきか"),
    ("standard", "日本の夏時間導入は検討に値するか"),

    # ---- Tech Ethics (10) ----
    ("fast", "スマートスピーカーは家庭のプライバシーを脅かすか"),
    ("fast", "顔認識技術の公共利用を禁止すべきか"),
    ("fast", "子供のゲーム時間を法律で制限すべきか"),
    ("fast", "電子投票は導入すべきか"),
    ("fast", "デジタル遺品の管理は法整備が必要か"),
    ("fast", "AIカウンセラーは人間のカウンセラーに代われるか"),
    ("fast", "自動翻訳で外国語学習は不要になるか"),
    ("standard", "SNSでの誹謗中傷に対する法的規制は十分か"),
    ("standard", "テック企業のCEO報酬は過大か"),
    ("standard", "オンラインゲームの課金システムにギャンブル規制を適用すべきか"),

    # ---- Education (10) ----
    ("fast", "大学の授業料を無償化すべきか"),
    ("fast", "プログラミング教育は必修であるべきか"),
    ("fast", "飛び級制度を日本でも導入すべきか"),
    ("fast", "学校の部活動を地域クラブに移行すべきか"),
    ("fast", "教科書のデジタル化は紙の教科書より優れているか"),
    ("fast", "英語教育は小学1年生から始めるべきか"),
    ("fast", "宿題は学習効果があるか"),
    ("standard", "不登校の子供にオンライン教育は有効な代替手段か"),
    ("standard", "高等教育は社会に出るために本当に必要か"),
    ("standard", "教師の給与を大幅に引き上げるべきか"),

    # ---- Health (10) ----
    ("fast", "マスク着用の義務化はパンデミック時に有効か"),
    ("fast", "健康保険制度は維持可能か"),
    ("fast", "電子タバコは紙タバコより安全か"),
    ("fast", "ストレスチェック制度は形骸化しているか"),
    ("fast", "処方箋なしで買える薬の範囲を広げるべきか"),
    ("fast", "不妊治療への公的支援は十分か"),
    ("fast", "肥満に対して医学的介入は積極的に行うべきか"),
    ("standard", "終末期医療の在り方を見直すべきか"),
    ("standard", "代理出産を合法化すべきか"),
    ("standard", "精子・卵子バンクの匿名性は維持すべきか"),

    # ---- Politics (10) ----
    ("fast", "国会議員の定数を削減すべきか"),
    ("fast", "政治家に年齢制限を設けるべきか"),
    ("fast", "政治献金を全面禁止すべきか"),
    ("fast", "世襲政治家を制限する法律は必要か"),
    ("fast", "直接民主制の要素を増やすべきか"),
    ("fast", "地方議会はオンライン化すべきか"),
    ("fast", "日本は核武装を検討すべきか"),
    ("standard", "天皇制は今後も維持すべきか"),
    ("standard", "日本国憲法第9条は改正すべきか"),
    ("standard", "女性議員クオータ制は導入すべきか"),

    # ---- Food & Agriculture (10) ----
    ("fast", "有機農業は従来農業に取って代われるか"),
    ("fast", "昆虫食は主流になるか"),
    ("fast", "食品添加物の規制は強化すべきか"),
    ("fast", "フードデリバリーは飲食店を衰退させるか"),
    ("fast", "給食費は完全無償化すべきか"),
    ("fast", "農業の完全自動化は可能か"),
    ("fast", "食料自給率を上げる政策は必要か"),
    ("standard", "遺伝子組み換え食品の表示義務は十分か"),
    ("standard", "フードバンクを制度化すべきか"),
    ("standard", "酒類の広告を全面禁止すべきか"),

    # ---- Transport (10) ----
    ("fast", "高速道路の無料化は実現すべきか"),
    ("fast", "自転車にヘルメット着用を義務化すべきか"),
    ("fast", "リニア新幹線は本当に必要か"),
    ("fast", "空飛ぶタクシーは実用化されるか"),
    ("fast", "電動キックボードの規制は適切か"),
    ("fast", "運転免許の取得年齢を引き下げるべきか"),
    ("fast", "鉄道のダイヤ遅延に対して補償制度は必要か"),
    ("standard", "地方の公共交通をどう維持すべきか"),
    ("standard", "都市部の自家用車禁止は検討に値するか"),
    ("standard", "MaaS（統合型移動サービス）は交通問題を解決するか"),

    # ---- Environment (10) ----
    ("fast", "ペットショップでの動物販売を禁止すべきか"),
    ("fast", "使い捨てプラスチックストローの禁止は意味があるか"),
    ("fast", "花粉症対策にスギの大規模伐採は有効か"),
    ("fast", "海洋プラスチック問題の解決策はあるか"),
    ("fast", "環境保護のために肉の消費に課税すべきか"),
    ("fast", "再生可能エネルギー100%の社会は実現可能か"),
    ("fast", "動物の権利を憲法に明記すべきか"),
    ("standard", "環境破壊に対する企業の法的責任を強化すべきか"),
    ("standard", "気候変動対策として飛行機利用を制限すべきか"),
    ("standard", "自然災害への備えとして強制移住は許容されるか"),

    # ---- Security (10) ----
    ("fast", "監視社会と安全のトレードオフは許容できるか"),
    ("fast", "サイバー攻撃に対して反撃は許されるか"),
    ("fast", "民間人の銃所持は日本でも議論すべきか"),
    ("fast", "テロリストの通信を傍受する権限は必要か"),
    ("fast", "警察によるドローン監視は許容されるか"),
    ("fast", "刑期を終えた犯罪者の情報公開は適切か"),
    ("fast", "少年法の適用年齢を引き下げるべきか"),
    ("standard", "死後の個人データはどう扱うべきか"),
    ("standard", "企業のデータ侵害に対する罰則は十分か"),
    ("standard", "国家によるバックドア要求は許されるか"),

    # ---- Future (10) ----
    ("fast", "仮想現実での生活は現実の代替になりうるか"),
    ("fast", "デジタルツインは都市計画を変えるか"),
    ("fast", "ポストヒューマニズムは人類の未来か"),
    ("fast", "意識のアップロードは倫理的に許されるか"),
    ("fast", "宇宙移民の選抜基準はどうあるべきか"),
    ("fast", "AIが人類を滅ぼす確率は無視できるか"),
    ("fast", "2100年の世界はユートピアかディストピアか"),
    ("standard", "技術的特異点(シンギュラリティ)は到来するか"),
    ("standard", "人間とAIのハイブリッド存在は倫理的に許されるか"),
    ("standard", "次の100年で人類が直面する最大の脅威は何か"),
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
RETRY_DELAY_BASE = 5


async def call_llm_with_retry(client, model, system, user_msg, max_tokens, semaphore, pricing, is_reasoning_model):
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
                    timeout=300.0,
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


async def run_single_deliberation(client, topic, model, semaphore):
    result = {
        "topic": topic, "model": model,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "phases": {}, "total_tokens": 0, "total_cost": 0.0,
    }
    pricing = PRICING[model]
    is_reasoning = model == "gpt-5"

    try:
        # Phase 1: Independent Analysis
        p1_tasks = [
            call_llm_with_retry(client, model, p["system"],
                f"以下のテーマについて、あなたの視点から独立して分析してください。最終的にAPPROVE（承認）、REJECT（却下）、CONDITIONAL（条件付き承認）のいずれかの立場を取ることになりますが、まずは多角的に分析してください。\n\nテーマ: {topic}",
                2048 if is_reasoning else 1024, semaphore, pricing, is_reasoning)
            for p in PERSONAS
        ]
        p1_results = await asyncio.gather(*p1_tasks, return_exceptions=True)
        p1_data = []
        for i, r in enumerate(p1_results):
            if isinstance(r, Exception):
                p1_data.append({"persona": PERSONAS[i]["name"], "error": str(r)})
            else:
                content, usage = r
                p1_data.append({"persona": PERSONAS[i]["name"], "analysis": content[:500], "usage": usage})
                result["total_tokens"] += usage["prompt_tokens"] + usage["completion_tokens"]
                result["total_cost"] += usage["cost"]
        result["phases"]["phase1_analysis"] = p1_data

        # Phase 2: Debate
        analyses = "\n".join(f"[{d['persona']}]: {d.get('analysis', d.get('error', 'N/A'))[:300]}" for d in p1_data)
        p2_tasks = [
            call_llm_with_retry(client, model, p["system"],
                f"他の2体のMAGIの分析を踏まえて、反論または補強してください。\n\nテーマ: {topic}\n\n各AIの分析:\n{analyses}",
                1024 if is_reasoning else 512, semaphore, pricing, is_reasoning)
            for p in PERSONAS
        ]
        p2_results = await asyncio.gather(*p2_tasks, return_exceptions=True)
        p2_data = []
        for i, r in enumerate(p2_results):
            if isinstance(r, Exception):
                p2_data.append({"persona": PERSONAS[i]["name"], "error": str(r)})
            else:
                content, usage = r
                p2_data.append({"persona": PERSONAS[i]["name"], "debate": content[:500], "usage": usage})
                result["total_tokens"] += usage["prompt_tokens"] + usage["completion_tokens"]
                result["total_cost"] += usage["cost"]
        result["phases"]["phase2_debate"] = p2_data

        # Phase 3: Final Vote
        debate = "\n".join(f"[{d['persona']}]: {d.get('debate', d.get('error', 'N/A'))[:200]}" for d in p2_data)
        p3_tasks = [
            call_llm_with_retry(client, model, p["system"],
                f"最終投票を行ってください。以下のフォーマットで回答:\n投票: APPROVE / REJECT / CONDITIONAL\n理由: (100文字以内)\n条件: (CONDITIONALの場合のみ)\n\nテーマ: {topic}\n\n討論結果:\n{debate}",
                512 if is_reasoning else 256, semaphore, pricing, is_reasoning)
            for p in PERSONAS
        ]
        p3_results = await asyncio.gather(*p3_tasks, return_exceptions=True)
        p3_data = []
        votes = []
        for i, r in enumerate(p3_results):
            if isinstance(r, Exception):
                p3_data.append({"persona": PERSONAS[i]["name"], "error": str(r)})
            else:
                content, usage = r
                vote = "UNKNOWN"
                for v in ["APPROVE", "REJECT", "CONDITIONAL"]:
                    if v in content.upper():
                        vote = v
                        break
                votes.append(vote)
                p3_data.append({"persona": PERSONAS[i]["name"], "vote": vote, "reasoning": content[:300], "usage": usage})
                result["total_tokens"] += usage["prompt_tokens"] + usage["completion_tokens"]
                result["total_cost"] += usage["cost"]
        result["phases"]["phase3_votes"] = p3_data

        # Consensus
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
        print(f"    [ERROR] {topic[:40]}... -> {result['error'][:100]}", flush=True)

    return result


def _save_results(results, total_cost, total_tokens, start_time):
    summary = {
        "experiment": "mass_deliberation_r9",
        "round": 9,
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

    output_path = OUTPUT_DIR / "mass_deliberation_r9.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"    [SAVED] {output_path} ({len(results)} results)", flush=True)


async def main():
    client = AsyncAzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        api_version=API_VERSION,
        timeout=600.0,
    )
    semaphore = asyncio.Semaphore(8)

    print(f"{'='*70}")
    print(f"  MAGI MASS DELIBERATION ROUND 9 - {len(TOPICS)} Topics")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}")
    print(f"{'='*70}")

    deep = sum(1 for m, _ in TOPICS if m == "deep")
    std = sum(1 for m, _ in TOPICS if m == "standard")
    fast = sum(1 for m, _ in TOPICS if m == "fast")
    print(f"  Deep (GPT-5): {deep} | Standard (GPT-5.1): {std} | Fast (GPT-5.2): {fast}")
    print(f"  Semaphore: 8 | Retry: {MAX_RETRIES} | Timeout: 300s/call")
    print(flush=True)

    all_results = []
    total_cost = 0.0
    total_tokens = 0
    start_time = time.time()

    BATCH_SIZE = 10
    for batch_start in range(0, len(TOPICS), BATCH_SIZE):
        batch = TOPICS[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(TOPICS) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n  --- Batch {batch_num}/{total_batches} ({len(batch)} topics) ---", flush=True)

        tasks = [run_single_deliberation(client, topic, MODELS[tier], semaphore) for tier, topic in batch]

        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            cost = result.get("total_cost", 0)
            tokens = result.get("total_tokens", 0)
            total_cost += cost
            total_tokens += tokens
            all_results.append(result)

            done = len(all_results)
            elapsed = time.time() - start_time
            print(f"  [{done:2d}/{len(TOPICS)}] {result['model']:8s} | {result.get('status','?'):9s} | {result.get('consensus','N/A'):20s} | ${cost:.4f} | {tokens:>6} tok | {elapsed:.0f}s | {result['topic'][:40]}...", flush=True)

            if done % 5 == 0:
                _save_results(all_results, total_cost, total_tokens, start_time)

    _save_results(all_results, total_cost, total_tokens, start_time)

    ok = sum(1 for r in all_results if r.get('status') == 'completed')
    err = sum(1 for r in all_results if r.get('status') == 'error')
    elapsed = time.time() - start_time

    print(f"\n{'='*70}")
    print(f"  ROUND 9 COMPLETE: {ok} ok, {err} errors")
    print(f"  Tokens: {total_tokens:,} | Cost: ${total_cost:.4f} | Time: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    if ok > 0:
        print(f"  Avg: ${total_cost/ok:.4f}/topic")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
