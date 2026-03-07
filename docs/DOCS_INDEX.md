# WatchMe Docs Index

最終更新: 2026-03-07  
Status: Active  
Source of truth: このファイルは `server-configs/docs` の入口です

## 使い方

まず以下の順で確認します。

1. [CURRENT_STATE.md](./CURRENT_STATE.md)
2. [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md)
3. [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md)

注意:
- `Active` は現行運用で参照すべき文書
- `Reference` は補助資料
- `Historical` は履歴・移行経緯であり、現行仕様の正ではありません
- 迷ったら `CURRENT_STATE.md` と `DEPLOYMENT_RUNBOOK.md` を優先します

## 文書一覧

| 文書 | Status | 用途 | 備考 |
|------|--------|------|------|
| [CURRENT_STATE.md](./CURRENT_STATE.md) | Active | 現在の運用モデル確認 | 最初に読む |
| [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) | Active | 何をどこからどう反映するか判断 | デプロイ時の主参照 |
| [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md) | Active | Spot/Daily/Weekly の処理フロー | パイプライン理解用 |
| [NON_TECH_PIPELINE_OVERVIEW.md](./NON_TECH_PIPELINE_OVERVIEW.md) | Active | 非エンジニア向けの全体像説明 | 共有資料・概念図の元ネタ |
| [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md) | Active | API リポジトリ側の CI/CD 標準 | API デプロイ方式の基準 |
| [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) | Reference | 広い技術仕様の参照 | 一部古い記述あり。現行運用判断には使わない |
| [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md) | Reference | 運用手順の補助資料 | 一部 systemd 前提の旧記述あり |
| [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) | Reference | 既知障害・詰まりどころ | 調査時に参照 |
| [NEW_API_INTEGRATION_GUIDE.md](./NEW_API_INTEGRATION_GUIDE.md) | Reference | 新規 API 追加時の手順 | 新規開発向け |
| [SPOT_AND_DAILY_ANALYSIS_GUIDE.md](./SPOT_AND_DAILY_ANALYSIS_GUIDE.md) | Reference | 分析仕様の補助理解 | 処理内容の補足 |
| [NEXT_SESSION_HANDOFF_2026-03-07.md](./NEXT_SESSION_HANDOFF_2026-03-07.md) | Active | 次セッションへの作業引き継ぎ | 今回の改善計画とデプロイ状況 |
| [SPOT_PIPELINE_HANDOFF_2026-03-07.md](./SPOT_PIPELINE_HANDOFF_2026-03-07.md) | Historical | Spot 調査の引き継ぎ | セッション文脈用 |
| [ARCHITECTURE_AND_MIGRATION_GUIDE.md](./ARCHITECTURE_AND_MIGRATION_GUIDE.md) | Historical | 移行経緯の記録 | 現行仕様の正ではない |
| [SCALABILITY_ROADMAP.md](./SCALABILITY_ROADMAP.md) | Reference | 将来の拡張計画 | 将来検討用 |
| [COST_MANAGEMENT.md](./COST_MANAGEMENT.md) | Reference | コスト運用 | FinOps 用 |
| [FUTURE_LONG_TERM_MEMORY.md](./FUTURE_LONG_TERM_MEMORY.md) | Historical | 将来構想メモ | 現行実装前提ではない |

## 更新ルール

以下を変更したら、このインデックスも更新します。

- 文書の追加・削除
- 現行運用の source of truth の変更
- 文書の `Active / Reference / Historical` の区分変更

## このセッションで整理したこと

- `CHANGELOG.md` は削除
- 現行運用の入口を `CURRENT_STATE.md` と `DEPLOYMENT_RUNBOOK.md` に集約
- 古い文書は削除せず、まずは役割を明示
