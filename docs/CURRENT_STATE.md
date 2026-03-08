# WatchMe Current State

最終更新: 2026-03-08  
Status: Active  
Source of truth: 現在の運用モデル・責務分担

## この文書の目的

この文書は「今の WatchMe がどう運用されているか」を短く固定するためのものです。  
歴史や移行経緯ではなく、現時点で作業判断に使う情報だけを置きます。

## 全体像

- クライアント: iOS App / Web Dashboard / Observer Device
- サーバー: EC2 上の Docker コンテナ群
- DB: Supabase
- 非同期処理: Lambda + SQS + EventBridge

重要:
- **実行基盤は Docker**
- ただし **デプロイ制御の経路は 1 本ではない**

## 現在のデプロイ責務

### 1. API アプリ本体

対象例:
- Aggregator API
- Profiler API
- その他の独立 API リポジトリ

原則:
- アプリコードは各 API リポジトリで管理
- デプロイは各 API リポジトリの **GitHub Actions CI/CD** が担当
- EC2 上には `/home/ubuntu/{api-name}/` に `docker-compose.prod.yml`, `.env`, `run-prod.sh` が配置される

つまり:
- **API のコード変更を `server-configs` から直接デプロイしない**
- まず各 API リポジトリの workflow を確認する

### 2. EC2 基盤設定

対象:
- Nginx (`production/sites-available/`)
- Docker network (`watchme-network`)
- `production/docker-compose-files/`

原則:
- これらは `server-configs` が source of truth
- EC2 に `production/` を反映する（`setup_server.sh` を使用）

### 3. AWS 非同期基盤

対象:
- Lambda
- SQS
- EventBridge
- Spot/Daily パイプラインのワーカーと配線

原則:
- **Lambda は `server-configs` から直接反映**
- API の CI/CD とは別経路

## コンテナのライフサイクル管理

**systemd は使用しない。** 2026-03-08 に全 systemd サービスを廃止済み。

### デプロイ（コンテナの作成・更新）

- 各 API リポジトリの **GitHub Actions CI/CD** が担当
- フロー: `git push` → GitHub Actions → ECR にイメージ push → EC2 に SSH → `run-prod.sh` 実行 → `docker-compose up -d`
- 2026-03-08: Avatar Uploader も CI/CD に統一済み

### 永続化（EC2 再起動時の自動復帰）

- **Docker の restart policy** に依存
- `restart: always` → Docker daemon 起動時に自動復帰（`docker stop` しても復帰）
- `restart: unless-stopped` → Docker daemon 起動時に自動復帰（`docker stop` した場合は復帰しない）
- EC2 起動時に Docker daemon が自動起動するため、restart policy が設定されたコンテナは自動復帰する

### Docker network

- `watchme-network`（bridge）を全コンテナで共有
- `setup_server.sh` または手動で `docker network create watchme-network` で作成

## Spot パイプラインの現行構成

Spot の主要要素:
- `watchme-audio-processor`
- `watchme-asr-worker`
- `watchme-sed-worker`
- `watchme-ser-worker`
- `watchme-aggregator-checker`
- `watchme-spot-analysis-worker`
- `watchme-spot-analysis-queue.fifo`
- `watchme-feature-completed-queue`
- `watchme-dashboard-summary-queue`
- `watchme-aggregator-reconciliation-every-5-minutes`

責務:
- feature extractor 完了後の合流判定と enqueue は Lambda/SQS 側
- Spot Aggregator / Spot Profiler の実処理本体は API 側

2026-03-07 時点の補足:
- 各 feature API (`behavior` / `emotion` / `vibe`) の `/async-process` は「ジョブ受付専用（queue enqueue）」として運用する
- デフォルトは queue モード (`*_JOB_QUEUE_ENABLED=true`)。queue が無効/不達のときは `503` を返し、Lambda 側の SQS リトライに委譲する
- `*_ALLOW_IN_PROCESS_FALLBACK` はデフォルト `false`（本番では無効）。ローカル検証でのみ明示有効化

## 作業前の確認原則

1. Supabase で対象テーブルと対象レコードを確認
2. AWS で Lambda/SQS/EventBridge/CloudWatch の現状を確認
3. API 本体変更か、基盤変更か、Lambda 変更かを分類
4. その分類に応じた反映経路を選ぶ

## 更新ルール

以下が変わったらこの文書を更新します。

- デプロイ方式の変更
- source of truth の変更
- Spot/Daily パイプラインの主要構成変更
- GitHub Actions 管理対象と `server-configs` 管理対象の境界変更
