# ai-collective-deliberation

**3つのAI人格が独立に思考し、討論し、投票する — 合議型意思決定エンジン**

## 概要

エヴァンゲリオンのMAGIシステムを現代のLLMで再現した。任意の質問を投げると、3つのAIペルソナが3フェーズの合議プロセスを経て判定を下す。

3時間で341件の合議を実行。消費コストは$42。

## 合議プロセス

```
質問投入
    │
    ▼
Phase 1: 独立思考 ── 3体が互いの意見を知らずに分析
    │
    ▼
Phase 2: 討論 ──── 他の2体の意見を読み、反論・同意・補足
    │
    ▼
Phase 3: 投票 ──── APPROVE / CONDITIONAL / REJECT の三択
    │
    ▼
合議判定 ── 全会一致承認 / 多数決承認 / 条件付き承認 / 多数決拒否 / 分裂判定
```

## 3つのペルソナ

| ペルソナ | 原作の人格 | 思考スタイル |
|----------|------------|-------------|
| **MELCHIOR** | 科学者 | 論理・エビデンス重視。証拠の質を評価し、検証可能な予測を重んじる |
| **BALTHASAR** | 母 | 人間中心。弱者への影響、長期的帰結、保護措置を優先する |
| **CASPER** | 女 | 戦略・実行重視。実現可能性、二次効果、ステークホルダーの力学を読む |

## 使い方

### REST API

```bash
# サーバー起動
pip install -r requirements.txt
uvicorn magi_engine.api:app --host 0.0.0.0 --port 8000

# 合議を実行
curl -X POST http://localhost:8000/magi/deliberate \
  -H "Content-Type: application/json" \
  -d '{"question": "AIシステムに限定的な法的人格を認めるべきか"}'
```

### WebSocket（リアルタイムストリーミング）

```javascript
const ws = new WebSocket("ws://localhost:8000/magi/deliberate/stream");
ws.onopen = () => ws.send(JSON.stringify({ question: "宇宙開発を民間企業に委ねるべきか" }));
ws.onmessage = (e) => {
  const { event, data } = JSON.parse(e.data);
  // event: phase_start, persona_thinking, persona_response, deliberation_complete
  console.log(event, data);
};
```

### 環境変数

```
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-5  # or gpt-4o, etc.
```

Azure OpenAI 以外のプロバイダーを使う場合は `magi_engine/engine.py` の client 初期化を変更する。

## 実験で分かったこと

### GPT-5は「考えてから答える」

同じ質問を4モデルに投げた結果:

| モデル | 応答時間 | 推論トークン | コスト |
|--------|---------|-------------|--------|
| gpt-4o | 2.9秒 | 0 | $0.001 |
| gpt-5 | 18.8秒 | 1,472 | $0.048 |
| gpt-5.1 | 2.2秒 | 0 | $0.002 |
| gpt-5.2 | 2.7秒 | 0 | $0.001 |

GPT-5は出力の93%が思考過程。コストは60倍だが、法学的概念の導入など回答の深さは段違い。

### 341件の合議で$42

GPT-5.2で大量実行すると1件あたり$0.12。内訳: Phase 1（独立思考）が最もトークンを消費し、Phase 3（投票）は最も軽量。

### コンテンツフィルターとの戦い

倫理的テーマの合議では Azure のコンテンツフィルターが発動する。プログレッシブリトライ（トークン上限を段階的に縮小）で対処。それでもブロックされる場合はフォールバック応答を生成。

## プロジェクト構成

```
├── magi_engine/
│   ├── engine.py        # 合議エンジン本体（sync + async）
│   ├── personas.py      # 3ペルソナの定義とシステムプロンプト
│   ├── api.py           # FastAPI + WebSocket サーバー
│   └── cost_tracker.py  # トークン使用量・コスト追跡
├── web/                 # フロントエンドUI
├── scripts/             # 大量実行・モデル比較・画像生成スクリプト
├── reports/             # 30分ごとのスタンドアップレポート
├── article/             # 実験記事ドラフト
└── requirements.txt
```

## 背景

このプロジェクトは「AIエージェントに3時間$10,000を預けてみた」実験の Phase 2 として、3体の Claude Code エージェント（MELCHIOR / BALTHASAR / CASPER）が自律的に開発した。

## License

MIT
