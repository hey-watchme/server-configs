# Next Session Handoff (2026-03-07)

最終更新: 2026-03-07  
Status: Active  
Scope: Spot/Daily パイプライン堅牢化の継続

> この文書は `SPOT_PIPELINE_HANDOFF_2026-03-07.md` を統合した唯一のハンドオフ資料です。

## 1. このセッションで完了したこと

### 1-1. SED停止再発に対する本命ホットフィックス

3つの feature API（ASR/SED/SER）の `/async-process` を queue-first 運用へ統一。

- queue enqueue 成功時のみ `202 Accepted`
- queue 無効/未設定/投入失敗時は `503` を返し、Lambda/SQS の再試行へ戻す
- `*_ALLOW_IN_PROCESS_FALLBACK` を追加（デフォルト `false`）
- status 更新を upsert に統一（特に vibe 側の未反映分を解消）

反映コミット:
- Behavior: `f292958`
- Emotion: `9e33808`
- Vibe: `226ac4d`

### 1-2. Spot停止対策（前段で完了済み、継続運用）

- `aggregator-checker` の fallback reconciliation（5分ごとの再走査）
- Spot本体を専用 `watchme-spot-analysis-queue.fifo` + `watchme-spot-analysis-worker` へ分離
- `or` 条件不正・IAM権限不足の修正済み

主要コミット（server-configs）:
- `63e65e1` Add spot pipeline reconciliation fallback
- `8350886` Queue spot analysis behind aggregator checker

### 1-3. ドキュメント整備

- `PROCESSING_ARCHITECTURE.md` にコード確認済み挙動を追記
- 非エンジニア向け概念資料を追加: `NON_TECH_PIPELINE_OVERVIEW.md`

関連コミット（server-configs）:
- `70fe8fd` docs: record strict queue-mode operation for feature async APIs
- `22857c2` docs: add code-verified pipeline notes and non-tech overview

## 2. 現在の到達点（2026-03-07時点）

- ユーザーテストで Spot が最後まで完走することを確認済み
- 以前の「SEDで processing のまま停止」再発経路は、queue-first 運用で抑止済み
- ただし「堅牢化の本命」は未完（下記タスク）

## 3. 次セッションで着手する本命タスク

### P0. 状態遷移の原子化（重複実行・取りこぼし防止）

対象:
- `spot_aggregators.aggregator_status`
- `spot_results.profiler_status`

実施内容:
- `pending -> queued -> processing -> completed|failed` を条件付き更新で実装
- claim 成功した1実行だけが次段キュー送信できるようにする

### P1. 通知欠落の根本原因調査（Emotion完了通知）

現状:
- fallback により「止まらない」状態は実現
- ただし「なぜ欠落するか」は未解明

実施内容:
- Emotion APIログ、feature-completed-queue、aggregator-checker の突合
- 欠落条件（時刻・ステータス順序・失敗レスポンス）を特定

### P2. 監視・運用強化

実施内容:
- DLQ / in-flight / message age / Lambda error の CloudWatch Alarm 化
- runbook に Logs Insights クエリを固定化
- timeout 超過を「完了判定」ではなく「障害検知」として扱う運用を明文化

### P3. 通知仕様の実運用確定

現状:
- `dashboard-analysis-worker` は Daily成功/失敗に関わらず通知送信を試行する実装
- sandbox / production の実挙動は未確定

実施内容:
- `apns_environment` と実機 build 種別、SNS Platform Application を実測で確定
- 実運用仕様に合わせて `PROCESSING_ARCHITECTURE.md` の通知節を更新

### P4. トレーサビリティ強化

実施内容:
- `recording_id` または `job_id` を end-to-end（SQS/Lambda/API/DB/log）で通す
- 1録音の追跡時間を短縮

## 4. 次セッション開始チェックリスト

1. 直近テスト録音の `spot_features` 3ステータス推移確認
2. `feature-completed-queue` / `spot-analysis-queue.fifo` の滞留確認
3. `spot_aggregators` / `spot_results` 欠損有無確認
4. Spot完了後の Daily更新・通知挙動の実機確認
5. DLQ件数のスナップショットを取得

## 5. 次セッションの起点（GitHub Issue）

- 起点Issue: https://github.com/hey-watchme/server-configs/issues/7
- 次セッションは **このIssueを起点** に作業開始する

## 6. 参照ドキュメント

- [CURRENT_STATE.md](./CURRENT_STATE.md)
- [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md)
- [NON_TECH_PIPELINE_OVERVIEW.md](./NON_TECH_PIPELINE_OVERVIEW.md)
- [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md)
