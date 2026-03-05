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
    # ---- Category 1: AI & Robotics (10) ----
    ("deep", "汎用人工知能(AGI)が実現した場合、現行の知的財産制度・労働法・社会保障制度はどのように再設計すべきか？AGI以前と以後の社会契約の断絶と接続を論じよ"),
    ("standard", "介護ロボットに感情表現機能を搭載すべきか"),
    ("standard", "AIが生成した芸術作品に著作権を認めるべきか"),
    ("standard", "自律型致死兵器(LAWS)の国際条約は実現可能か"),
    ("fast", "AIチャットボットとの恋愛関係は健全か"),
    ("fast", "AIによる採用選考は人間の面接官より公平か"),
    ("fast", "ロボットに市民権を与えるべきか"),
    ("fast", "AIが書いた小説は文学賞を受賞すべきか"),
    ("fast", "自動運転タクシーは2030年に普及するか"),
    ("fast", "AIによる犯罪予測は許容されるべきか"),

    # ---- Category 2: Economy & Work (10) ----
    ("deep", "完全自動化経済において人間の「労働」の意味はどう変容するか？ポスト労働社会のアイデンティティ・目的・社会構造を哲学的・経済学的に分析せよ"),
    ("standard", "週4日勤務制を法制化すべきか"),
    ("standard", "暗号通貨を法定通貨として採用すべきか"),
    ("standard", "プラットフォーム労働者(ギグワーカー)に正社員と同等の保護を与えるべきか"),
    ("fast", "ベーシックインカムは勤労意欲を低下させるか"),
    ("fast", "最低賃金を2倍にすべきか"),
    ("fast", "副業を全面解禁すべきか"),
    ("fast", "新卒一括採用制度は廃止すべきか"),
    ("fast", "起業失敗者への公的支援は必要か"),
    ("fast", "AIによる株式取引を規制すべきか"),

    # ---- Category 3: Ethics & Philosophy (10) ----
    ("deep", "「デジタル不死」（人間の意識をデジタル化して保存する技術）は追求すべきか？意識の本質・アイデンティティの連続性・死の意味の再定義を包括的に論じよ"),
    ("standard", "動物実験は全面的に廃止すべきか"),
    ("standard", "安楽死を合法化すべきか"),
    ("standard", "遺伝子編集ベビーは許容されるべきか"),
    ("fast", "死刑制度は廃止すべきか"),
    ("fast", "肉食は倫理的に正当化できるか"),
    ("fast", "嘘をつく権利は基本的人権か"),
    ("fast", "完全な監視社会は犯罪ゼロを実現できるか"),
    ("fast", "人間のクローン作成は許可すべきか"),
    ("fast", "AIに倫理的判断を委ねるべきか"),

    # ---- Category 4: Environment & Energy (10) ----
    ("deep", "2050年カーボンニュートラル達成のために原子力発電の大幅拡大は不可避か？再エネ100%シナリオとの比較、核廃棄物問題、社会的受容性を包括的に分析せよ"),
    ("standard", "食肉の代わりに培養肉を推進すべきか"),
    ("standard", "飛行機の利用に炭素税を課すべきか"),
    ("standard", "深海底マイニングは許可すべきか"),
    ("fast", "プラスチック製品を全面禁止すべきか"),
    ("fast", "個人の炭素排出量に上限を設けるべきか"),
    ("fast", "原発再稼働は日本で推進すべきか"),
    ("fast", "電気自動車の補助金は継続すべきか"),
    ("fast", "森林伐採を全面禁止すべきか"),
    ("fast", "水素エネルギーは実用的か"),

    # ---- Category 5: Media & Information (10) ----
    ("deep", "SNSのアルゴリズムによるフィルターバブルは民主主義を脅かしているか？情報の自由・プラットフォーム責任・市民のメディアリテラシーの三角関係を分析し、具体的な制度設計を提案せよ"),
    ("standard", "フェイクニュースの発信者に刑事罰を科すべきか"),
    ("standard", "子どものSNS利用を16歳以上に制限すべきか"),
    ("standard", "報道機関にAI生成コンテンツの明示義務を課すべきか"),
    ("fast", "新聞は2035年までに消滅するか"),
    ("fast", "テレビの受信料制度は廃止すべきか"),
    ("fast", "インフルエンサーに資格制度は必要か"),
    ("fast", "ディープフェイクの作成を犯罪とすべきか"),
    ("fast", "読書は動画視聴より知的成長に寄与するか"),
    ("fast", "AIニュースキャスターは人間に取って代わるか"),

    # ---- Category 6: Space & Frontier (10) ----
    ("deep", "火星のテラフォーミングは倫理的に許容されるか？もし火星に微生物が存在した場合の生命倫理、惑星保護条約、人類の宇宙進出の哲学的正当性を論じよ"),
    ("standard", "宇宙資源の所有権は誰に帰属すべきか"),
    ("standard", "民間宇宙旅行は規制すべきか"),
    ("standard", "地球外知的生命体へのメッセージ送信は続けるべきか"),
    ("fast", "宇宙エレベーターは2050年に実現するか"),
    ("fast", "月面での商業活動を許可すべきか"),
    ("fast", "宇宙軍は必要か"),
    ("fast", "小惑星採掘は地球経済を変えるか"),
    ("fast", "人間は火星で繁殖できるか"),
    ("fast", "光速を超える航行は理論的に可能か"),

    # ---- Category 7: Culture & Lifestyle (10) ----
    ("deep", "グローバル化による文化の均質化は不可避か？ローカル文化の保存・デジタルアーカイブ・文化的多様性の経済的価値を多角的に分析し、共存モデルを提案せよ"),
    ("standard", "義務教育に哲学の授業を導入すべきか"),
    ("standard", "国民の幸福度を経済指標と同等に政策評価に使うべきか"),
    ("standard", "伝統的な性別役割分担は完全に廃止すべきか"),
    ("fast", "紙の本は電子書籍に完全に置き換わるか"),
    ("fast", "リモートワークは都市を消滅させるか"),
    ("fast", "ペットの飼育に免許制を導入すべきか"),
    ("fast", "学校教育で競争を排除すべきか"),
    ("fast", "タトゥーに対する社会的偏見は解消すべきか"),
    ("fast", "人工知能は人間の創造性を超えるか"),

    # ---- Category 8: Health & Biotech (10) ----
    ("deep", "人間の寿命を200歳以上に延長する技術が実現した場合、社会保障・人口政策・世代間公平性・人生設計はどう変わるか？長寿社会の光と影を論じよ"),
    ("standard", "全ゲノム解析を出生時に義務化すべきか"),
    ("standard", "精神疾患の診断にAIを導入すべきか"),
    ("standard", "人体改造（サイボーグ化）は個人の自由として認めるべきか"),
    ("fast", "砂糖に税を課すべきか"),
    ("fast", "睡眠時間を短縮する薬は開発すべきか"),
    ("fast", "遺伝子検査で結婚相手を選ぶべきか"),
    ("fast", "テレメディシン（遠隔医療）は対面診療と同等か"),
    ("fast", "アンチエイジング治療に保険適用すべきか"),
    ("fast", "脳のバックアップは技術的に可能になるか"),
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
        "experiment": "mass_deliberation_r8",
        "round": 8,
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

    output_path = OUTPUT_DIR / "mass_deliberation_r8.json"
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
    print(f"  MAGI MASS DELIBERATION ROUND 8 - {len(TOPICS)} Topics")
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
    print(f"  ROUND 8 COMPLETE: {ok} ok, {err} errors")
    print(f"  Tokens: {total_tokens:,} | Cost: ${total_cost:.4f} | Time: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    if ok > 0:
        print(f"  Avg: ${total_cost/ok:.4f}/topic")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())
