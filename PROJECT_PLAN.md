# MAGI Project Phase 2 - Collective Intelligence Platform

## Overview
エヴァンゲリオンのMAGIシステムにインスパイアされた、3つのAI人格が合議して意思決定を行うプラットフォーム。

## Timeline
- **開始**: 2026-03-06 06:50 JST
- **終了**: 2026-03-06 10:00 JST (3時間10分)
- **予算**: $10,000 Azure credits

## Teams (MAGI System)

### MELCHIOR (メルキオール/科学者)
- **役割**: バックエンド・コンセンサスエンジン構築
- **担当**: Python APIでMAGI合議システムを実装
- **使用リソース**: Azure OpenAI (GPT-5, GPT-5.1)

### BALTHASAR (バルタザール/母)
- **役割**: フロントエンド・UXデザイン
- **担当**: インタラクティブWebデモの構築
- **使用リソース**: Azure Static Web Apps

### CASPER (カスパー/女)
- **役割**: 実験・監視・ドキュメント
- **担当**: コスト監視、実験実行、記事素材準備
- **使用リソース**: Azure Cost Management, gpt-image-1.5

## Standup Schedule
| # | Time | Status |
|---|------|--------|
| 1 | 07:20 | Pending |
| 2 | 07:50 | Pending |
| 3 | 08:20 | Pending |
| 4 | 08:50 | Pending |
| 5 | 09:20 | Pending |
| Final | 09:50 | Article Writing |

## Architecture
```
[User] --> [Web Frontend (BALTHASAR)]
              |
              v
         [MAGI API (MELCHIOR)]
              |
    +---------+---------+
    |         |         |
[MELCHIOR] [BALTHASAR] [CASPER]
 (科学者)   (母)       (女)
    |         |         |
    +---------+---------+
              |
         [Consensus]
              |
         [Response]
```

## Azure Resources
- **OpenAI Endpoint**: Canaveral (eastus2)
- **Models**: GPT-5, GPT-5.1, GPT-5.2, gpt-image-1.5
- **Resource Group**: magi-project (japaneast)
