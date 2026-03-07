# Spot Pipeline Handoff (2026-03-07)

最終更新: 2026-03-07

> Status: Historical
> Source of truth: セッション引き継ぎメモ。現行運用判断は [CURRENT_STATE.md](./CURRENT_STATE.md) と [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) を優先。

## 目的

このドキュメントは、Spot分析パイプラインの「途中で止まる」不具合調査と、その場で実施した堅牢化対応を次セッションへ引き継ぐためのメモです。

次回は、まずこのファイルを読んでから AWS / Supabase の現状確認に入れば、そのまま作業を再開できます。

---

## 問題の概要

### 症状

- iOSアプリから音声分析を実行すると、Spot分析が途中で止まることがある
- 体感では約50%で成功、約50%で停止
- 停止時でも `spot_features` 側では ASR / SED / SER が最終的に全て `completed` になっていることがある
- しかし `spot_aggregators` / `spot_results` が作成されず、後続の Daily へ進まない

### 代表的な失敗例

- `device_id`: `86b98bef-61a8-4f8d-9c17-32d4e7eec937`
- `recorded_at`: `2026-03-06T05:50:22.239+00:00`
- `file_path`: `files/86b98bef-61a8-4f8d-9c17-32d4e7eec937/2026-03-06/05-50-22/audio.wav`

### 調査結果

CloudWatch Logs と Supabase の状態を追った結果、停止点は STT 自体ではなく、その後の合流判定でした。

- `watchme-audio-processor`: 正常
- `watchme-asr-worker`: 正常
- `watchme-sed-worker`: 正常
- `watchme-ser-worker`: 正常
- `spot_features`: 最終的に `vibe_status / behavior_status / emotion_status` 全て `completed`
- それでも `spot_aggregators` / `spot_results` が空のケースあり

### 根本原因の仮説

`aggregator-checker` は「feature 完了通知を受けた時だけ」DB の状態を見ていました。

このため、次のパターンで止まります。

1. `vibe` 完了通知到着
2. `behavior` 完了通知到着
3. この時点では `emotion_status = pending`
4. その後、`emotion_status` 自体は DB 上で `completed` になる
5. しかし `emotion` の完了通知が `aggregator-checker` に届かない
6. `aggregator-checker` が再実行されず、Spot分析が停止

重要なのは、成功ケースでも `emotion` 通知が見えていないことがあった点です。
成功時はたまたま `behavior` 通知時点で `emotion_status` も `completed` になっていたため、そのまま前に進めていました。

つまり、**成功/失敗が「最後の通知が何か」に依存していた**状態でした。

---

## 今回実施した対応

### 第1段階: fallback 補修経路追加

コミット:

- `63e65e1` `Add spot pipeline reconciliation fallback`

内容:

- `watchme-aggregator-checker` に EventBridge 定期実行対応を追加
- `spot_features` で 3 feature 全て `completed` なのに `spot_results` が無い録音を再走査
- 通知欠落があっても、5分ごとに Spot分析を再開可能にした

関連ファイル:

- [watchme-aggregator-checker/lambda_function.py](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-aggregator-checker/lambda_function.py)
- [setup-aggregator-reconciliation-schedule.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/setup-aggregator-reconciliation-schedule.sh)

### 第2段階: Spot分析本体を専用キューへ分離

コミット:

- `8350886` `Queue spot analysis behind aggregator checker`

内容:

- `aggregator-checker` は「3 feature 揃った録音を enqueue する」だけに変更
- Aggregator / Profiler / dashboard-summary queue 送信は新規の `watchme-spot-analysis-worker` に移動
- Spot分析本体を SQS リトライ / DLQ の保護下に置いた

関連ファイル:

- [watchme-aggregator-checker/lambda_function.py](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-aggregator-checker/lambda_function.py)
- [watchme-spot-analysis-worker/lambda_function.py](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-spot-analysis-worker/lambda_function.py)
- [create-spot-analysis-queue.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/create-spot-analysis-queue.sh)
- [deploy-new-lambdas.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/deploy-new-lambdas.sh)
- [setup-sqs-triggers.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/setup-sqs-triggers.sh)
- [PROCESSING_ARCHITECTURE.md](/Users/kaya.matsumoto/projects/watchme/server-configs/docs/PROCESSING_ARCHITECTURE.md)

---

## 現在の構成

### Spot分析の流れ

1. S3 upload
2. `watchme-audio-processor`
3. `watchme-asr-queue-v2.fifo` / `watchme-sed-queue-v2.fifo` / `watchme-ser-queue-v2.fifo`
4. `watchme-asr-worker` / `watchme-sed-worker` / `watchme-ser-worker`
5. 各 EC2 API が `spot_features` を更新
6. 各 EC2 API が `watchme-feature-completed-queue` に完了通知
7. `watchme-aggregator-checker`
8. 3 feature 全て `completed` なら `watchme-spot-analysis-queue.fifo` に enqueue
9. `watchme-spot-analysis-worker`
10. `Aggregator API` -> `Profiler API`
11. `watchme-dashboard-summary-queue`
12. `watchme-dashboard-summary-worker`
13. `watchme-dashboard-analysis-worker`

### fallback

- EventBridge が5分ごとに `watchme-aggregator-checker` を起動
- 完了通知欠落時でも `spot_features` の完成状態から再 enqueue 可能

---

## デプロイに必要なもの

### 新規追加されたもの

- FIFO queue: `watchme-spot-analysis-queue.fifo`
- DLQ: `watchme-spot-analysis-dlq.fifo`
- Lambda: `watchme-spot-analysis-worker`
- EventBridge rule: `watchme-aggregator-reconciliation-every-5-minutes`

### 反映スクリプト

1. [create-spot-analysis-queue.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/create-spot-analysis-queue.sh)
2. [deploy-new-lambdas.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/deploy-new-lambdas.sh)
3. [setup-sqs-triggers.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/setup-sqs-triggers.sh)
4. [setup-aggregator-reconciliation-schedule.sh](/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/setup-aggregator-reconciliation-schedule.sh)

---

## いま確認できていること

- ユーザー報告では「現時点では問題なく動作している」
- リポジトリ上の変更は `origin/main` まで push 済み
- 直近の relevant commits:
  - `8350886` Queue spot analysis behind aggregator checker
  - `63e65e1` Add spot pipeline reconciliation fallback

### 2026-03-07 深夜の追加調査で判明したこと

テスト録音:

- `device_id`: `86b98bef-61a8-4f8d-9c17-32d4e7eec937`
- `recorded_at`: `2026-03-06T17:08:56.153+00:00`
- `file_path`: `files/86b98bef-61a8-4f8d-9c17-32d4e7eec937/2026-03-06/17-08-56/audio.wav`

この録音では `spot_features` は completed、`spot_aggregators` も作成されたが、`spot_results` が途中で止まった。

停止原因は 2 つだった:

1. `watchme-aggregator-checker` の Supabase PATCH 条件で `or` フィルタ文字列が不正
   - CloudWatch error:
     - `column spot_results.orprofiler_status does not exist`
   - 原因:
     - PostgREST の `or` は `or=(cond1,cond2,...)` 形式が必要だったが、括弧なしで送っていた

2. `watchme-lambda-s3-processor` ロールに新規 FIFO queue への権限が不足
   - CloudWatch error:
     - `AccessDenied` on `sqs:SendMessage` to `watchme-spot-analysis-queue.fifo`
   - 原因:
     - `SQSSendMessagePolicy` に新規 queue ARN が追加されていなかった

追加で分かったこと:

- `watchme-spot-analysis-worker` の Daily enqueue 判定でも、`daily_aggregator_status=queued` を「既に誰かが送信済み」と誤認して送信をスキップするケースがあった
- そのため Spot は completed でも Daily が取り残されることがある

実施した修正:

- `watchme-aggregator-checker/lambda_function.py`
  - `or` フィルタを PostgREST 形式へ修正
  - profiler queue claim の placeholder / revert 処理を維持したまま再デプロイ
- `watchme-spot-analysis-worker/lambda_function.py`
  - 同様に `or` フィルタを修正
  - `daily_aggregator_status` の claim 後に再読込し、`queued` へ遷移したケースでは dashboard-summary queue 送信を継続するよう修正
- IAM:
  - `watchme-lambda-s3-processor` の `SQSSendMessagePolicy` に `watchme-spot-analysis-queue.fifo` を追加

結果:

- 上記録音は手動 recovery 後に `spot_results.profiler_status=completed`
- `daily_aggregators` と `daily_results` も更新され、`processed_count=3` まで反映された
- つまり、2026-03-07 時点で本番反映済み

---

## 次セッションで最初にやること

### 1. 現状確認

README の前提どおり、実装前に現状確認を行うこと。

- Supabase で対象録音の `audio_files`, `spot_features`, `spot_aggregators`, `spot_results`, `daily_aggregators`, `daily_results`
- AWS で以下を確認
  - Lambda logs
  - `watchme-feature-completed-queue`
  - `watchme-spot-analysis-queue.fifo`
  - Spot analysis worker の DLQ

### 2. 確認したい観点

- `emotion` 完了通知欠落がまだ起きているか
- 起きていても fallback で収束しているか
- `watchme-spot-analysis-worker` のリトライ / DLQ が動いているか
- `dashboard-summary` が二重送信されていないか
- Daily 完了後の push 通知が、テスト環境 / 本番環境でどう振る舞うか
- `apns_environment` と実際の SNS Platform Application の対応が合っているか

---

## 残課題

### 1. 原子的な状態遷移がまだない

現状は改善済みだが、まだ完全ではありません。

- `aggregator-checker` は DB を見て enqueue する
- FIFO queue の deduplication で重複 enqueue はある程度抑えている
- ただし DB 上で `queued -> processing -> completed` を原子的に管理しているわけではない

次の本命改善はこれです。

- `spot_aggregators.aggregator_status`
  - `pending -> queued -> processing -> completed|failed`
- `spot_results.profiler_status`
  - `pending -> queued -> processing -> completed|failed`

そして、DB 側で条件付き遷移に成功した1回だけが次へ進むようにすること。

### 2. `recording_id` が無い

いまは実質 `(device_id, recorded_at)` で1録音を識別しています。

運用上は不便なので、将来的には `recording_id` を導入した方がよいです。

推奨:

- `audio_files` 作成時に UUID を発行
- SQS message / Lambda logs / EC2 logs / `spot_features` / `spot_aggregators` / `spot_results` に流す

### 3. Emotion 側の通知欠落原因そのものは未解決

今回は「欠落しても止まらない」ようにしただけで、なぜ `emotion` 通知が落ちるのかはまだ未解明です。

次回必要なら、EC2 側の Emotion Features サービスログを確認すること。

### 4. push 通知仕様の実運用確認が未完了

- `PROCESSING_ARCHITECTURE.md` には、`apns_environment` に応じて `APNS` / `APNS_SANDBOX` を動的選択する実装意図が記載されている
- `watchme-dashboard-analysis-worker` の APNs token 参照先は `public.users.apns_token` に修正済み（`user_profiles` は使わない）
- 一方で、運用記憶としては「テストでは通知が来ず、本番のみ」という前提で扱われていた可能性がある
- 次回は、文書ではなく実データ・実ログ・実機 build 種別を基準に仕様を確定すること
- 仕様確定までは、通知に関する文書を「あるべき姿」と「現行運用」が混ざる可能性ありとして扱うこと

---

## 次回の作業候補

優先順:

1. fallback + spot-analysis-worker 構成で安定運用できているか確認
2. `watchme-spot-analysis-worker` の CloudWatch 監視 / DLQ 監視を追加
3. `aggregator_status` / `profiler_status` の厳密な状態遷移を導入
4. `recording_id` 導入を設計
5. Emotion 完了通知欠落の根本調査

---

## メモ

- Step Functions は以前検討済みだが、現時点では最小変更・コスト重視で不採用
- 現方針は `SQS + Lambda + DB state + fallback reconciliation`
- `local_date` は引き続き必須。UTC 変換で Daily を作らないこと
