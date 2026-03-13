# WatchMe Server Configurations

最終更新: 2026-03-08

WatchMe 全体のサーバー設定と運用ドキュメントを集約するリポジトリ。  
このリポジトリ自体はアプリ本体ではなく、`EC2/Nginx/Docker/Lambda/運用文書` の基盤レイヤーを管理します。

## リポジトリ構成の注意（重要）

WatchMe は **単一Gitリポジトリではありません**。  
`/Users/kaya.matsumoto/projects/watchme` 配下に、用途ごとの **独立リポジトリ（マルチリポ）** が並ぶ構成です。

- `server-configs`: 基盤・運用・Lambda配線の source of truth
- 各 API: それぞれ独立したマイクロサービスリポジトリ（独立CI/CD）
- App / Web / Business: それぞれ独立リポジトリ

そのため、実装変更時は「どのリポジトリが責務を持つか」を先に切り分け、必要なら複数リポジトリを同時に更新します。

## 公式情報（連絡先）

- 公式サイト: `https://hey-watch.me`
- サポートメール: `support@hey-watch.me`

### Cloudflare Email Routing（受信設定）

- カスタムアドレス: `support@hey-watch.me`
- アクション: `Send to an email`
- 転送先: `matsumotokaya@gmail.com`
- ステータス: `Active`
- Catch-all: `Disabled`（`Drop`）

## 最初に読むもの

1. [docs/DOCS_INDEX.md](./docs/DOCS_INDEX.md)
2. [docs/CURRENT_STATE.md](./docs/CURRENT_STATE.md)
3. [docs/DEPLOYMENT_RUNBOOK.md](./docs/DEPLOYMENT_RUNBOOK.md)
4. [docs/PROCESSING_ARCHITECTURE.md](./docs/PROCESSING_ARCHITECTURE.md)

この順で読むと、`どの文書が現行の正か` と `何をどこからデプロイするか` が分かるようにしています。

> **⚠️ 開発の前提**
>
> - **データベースファースト**: テーブル構造・データは必ず Supabase 側の現状を確認すること
> - **AWS現状確認ファースト**: EC2/Lambda/SQS/ECR/CloudWatch の現状を確認してから変更すること
> - **MCP優先運用**: 調査・検証は `Supabase MCP + AWS MCP` を第一選択とし、AWS CLI は補助的に使用すること
> - **実装前チェック順序**:
>   1. DB 構造・対象レコード確認
>   2. AWS の関連サービス確認
>   3. 影響範囲を確定してから実装
> - **local_date原則**: すべての日付処理はデバイスの `local_date` を使用。UTC 変換・計算は禁止

## このリポジトリの役割

- `production/`: 本番 EC2 に反映する設定ファイル
- `docs/`: 運用・設計・調査用ドキュメント
- `production/lambda-functions/`: Lambda / SQS / EventBridge 関連の実装と反映スクリプト
- `production/sites-available/`: Nginx 設定
- `production/docker-compose-files/`: Docker Compose 設定（Web アプリ等）

重要:
- **API アプリ本体のコードは原則このリポジトリにはありません**
- `Aggregator API` や `Profiler API` のアプリコード変更は各 API リポジトリで管理します
- **Lambda はこのリポジトリから直接デプロイする運用です**

## デプロイ責務の早見表

| 変更対象 | どこを触るか | 反映方法 |
|---------|-------------|---------|
| Lambda 関数 | `server-configs/production/lambda-functions/` | 手動で AWS に反映 |
| SQS / EventBridge / Lambda 配線 | `server-configs` | 手動で AWS に反映 |
| Nginx / Docker network | `server-configs/production/` | EC2 で `setup_server.sh` を実行 |
| Aggregator / Profiler など API 本体 | 各 API リポジトリ | GitHub Actions CI/CD |
| DB スキーマ | プロジェクト全体の Supabase migrations | migration 実行 |

詳細は [docs/DEPLOYMENT_RUNBOOK.md](./docs/DEPLOYMENT_RUNBOOK.md) を参照。

## ディレクトリ構造

```text
server-configs/
├── production/
│   ├── docker-compose-files/
│   ├── lambda-functions/
│   ├── scripts/
│   ├── sites-available/
│   └── setup_server.sh
└── docs/
```

運用方針:
- EC2 に配置するのは基本的に `production/`
- `docs/` は作業者向けの知識集約

## コンテナの永続化方式

**全 API コンテナは Docker の restart policy で永続化しています（systemd は使用しません）。**

| 方式 | 説明 |
|------|------|
| `restart: always` | Docker daemon 起動時に自動復帰。`docker stop` しても復帰 |
| `restart: unless-stopped` | Docker daemon 起動時に自動復帰。`docker stop` した場合は復帰しない |

- EC2 再起動 → Docker daemon 自動起動 → restart policy に従いコンテナ自動復帰
- デプロイは GitHub Actions CI/CD が `run-prod.sh` を実行し `docker-compose up -d` する方式
- Docker network (`watchme-network`) は `setup_server.sh` または手動で作成

## 文書の見方

- 文書の索引: [docs/DOCS_INDEX.md](./docs/DOCS_INDEX.md)
- 現在の運用状態: [docs/CURRENT_STATE.md](./docs/CURRENT_STATE.md)
- デプロイ判断: [docs/DEPLOYMENT_RUNBOOK.md](./docs/DEPLOYMENT_RUNBOOK.md)

補足:
- `TECHNICAL_REFERENCE.md` は広い参照用
- `CICD_STANDARD_SPECIFICATION.md` は API 側 CI/CD の基準
- `OPERATIONS_GUIDE.md` は旧来の運用説明を含むため、まず Runbook を読むこと
- handoff / migration 文書は履歴・調査文脈として扱うこと

## 関連プロジェクト

### WatchMe iOS App

- リポジトリ: `/Users/kaya.matsumoto/projects/watchme/app/ios-watchme`
- 役割: 録音、Spot/Daily/Weekly の閲覧、通知、QR 共有
- 詳細: `/Users/kaya.matsumoto/projects/watchme/app/ios-watchme/README.md`

### WatchMe Business

- リポジトリ: `/Users/kaya.matsumoto/projects/watchme/business`
- 役割: B2B 向け音声分析・支援計画生成
- 詳細: [business/README.md](/Users/kaya.matsumoto/projects/watchme/business/README.md)
