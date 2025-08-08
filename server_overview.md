# WatchMe サーバー構成概要

このドキュメントは、WatchMeプロジェクトのAWS EC2サーバーにおける、システム全体の構成、サービス一覧、および運用ルールについてまとめたものです。

---

## 1. サーバー基本情報

- **インスタンス**: AWS EC2
- **IPアドレス**: `3.24.16.82`
- **OS**: Ubuntu
- **SSH接続**:
  ```bash
  ssh -i [PEMキーのパス] ubuntu@3.24.16.82
  ```
  *(例: `ssh -i ~/watchme-key.pem ubuntu@3.24.16.82`)*

---

## 2. アーキテクチャ概要

当サーバーは、**Nginx** をリバースプロキシとしたマイクロサービスアーキテクチャを採用しています。

- **外部からのアクセス**: すべてのHTTPSリクエスト (ポート443) は、まずNginxが受け取ります。
- **ルーティング**: Nginxは、リクエストされたドメインやパスに基づき、適切な内部サービス (Dockerコンテナ) にリクエストを転送します。
- **サービス実行環境**: 各APIやWebアプリケーションは、独立した **Dockerコンテナ** 内で動作しています。
- **プロセス管理**: 各コンテナは、**systemd** によってサービスとして管理され、サーバー起動時に自動的に起動します。
- **SSL証明書**: HTTPS化のためのSSL証明書は、**Let's Encrypt** により自動で取得・更新されます。

### コンテナ間通信
各コンテナ（サービス）同士は、Dockerの内部ネットワーク (`watchme-net`) を通じて相互に通信します。

コンテナから別のコンテナのAPIを呼び出す際は、ホスト名として **サービス名（コンテナ名）** を使用します。

- **例**: スケジューラーAPIコンテナからWhisper APIコンテナを呼び出す場合、接続先は `http://api-transcriber:8001` となります。

```
[インターネット]
      │
      │ HTTPS (443)
      ▼
┌──────────────────┐
│   EC2 インスタンス   │
│ ┌────────────────┐ │
│ │     Nginx      │ │  <-- 総合受付 (リバースプロキシ)
│ └────────────────┘ │
│   │   │   │        │
│   ▼   ▼   ▼        │ ルーティング
│ ┌───┐ ┌───┐ ┌───┐  │
│ │ 8k│ │3001 │ │9001 │ ... (各ポート)
│ └─┬─┘ └─┬─┘ └─┬─┘  │
│   │     │     │    │
│ ┌─▼──┐┌─▼──┐┌─▼──┐  │
│ │API 1 ││WebUI ││API 2 │  │  <-- Docker コンテナ群
│ └────┘└────┘└────┘  │
└──────────────────┘
```

---

## 3. サーバー設定管理【最重要】

サーバーの安定稼働の要である **Nginx** と **systemd** の設定は、システムの安定稼働の要です。設定ミスは全サービスに影響を及ぼすため、以下のルールに基づき、厳格な管理を行います。

### 運用ルール

- **Gitでの一元管理**: Nginxとsystemdの設定ファイルは、すべて専用のGitリポジトリでバージョン管理します。サーバー上のファイルを直接編集することは**固く禁止**します。
- **変更フロー**:
    1. ローカルでGitリポジトリをクローンし、ブランチを作成して変更作業を行います。
    2. 変更後、GitHub上でPull Requestを作成し、レビューを受けます。
    3. マージ後、本番サーバー上で `git pull` を行い、変更を反映させます。

### Gitリポジトリ

- **リポジトリURL**: `git@github.com:matsumotokaya/watchme-server-configs.git`
- **ディレクトリ構造**:
    ```
    .
    ├── systemd/              # systemdサービスファイル (.service)
    └── sites-available/      # Nginx設定ファイル
    ```

### デプロイ手順

サーバー上で `git pull` を実行した後、変更内容に応じて以下の手順を実行します。

#### Nginx設定の反映

1.  **設定ファイルをコピー**: `sudo cp sites-available/api.hey-watch.me /etc/nginx/sites-available/`
2.  **文法テスト**: `sudo nginx -t`
3.  **反映**: `sudo systemctl reload nginx`

#### systemd設定の反映

1.  **設定ファイルをコピー**: `sudo cp systemd/your-service.service /etc/systemd/system/`
2.  **systemd再読み込み**: `sudo systemctl daemon-reload`
3.  **サービスの有効化と起動**: `sudo systemctl enable --now your-service.service`

---

## 4. サービス一覧

現在サーバー上で稼働している主要なサービスは以下の通りです。

| サービス概要 | 公開エンドポイント | 内部ポート | systemdサービス名 | Gitリポジトリ |
| :--- | :--- | :--- | :--- | :--- |
| **Gateway API (Vault)** | `https://api.hey-watch.me/` | `8000` | `watchme-vault-api.service` | `watchme-vault-api` |
| **Webダッシュボード** | `https://dashboard.hey-watch.me/` | `3001` | `watchme-web-app.service` | `watchme-web-app` |
| **API Manager (UI)** | `https://api.hey-watch.me/manager/` | `9001` | `watchme-api-manager.service` | `watchme-api-manager` |
| **API Manager (Scheduler)** | `https://api.hey-watch.me/scheduler/` | `8015` | `watchme-api-manager.service` | `watchme-api-manager` |
| **管理用フロントエンド** | `https://admin.hey-watch.me/` | `9000` | `watchme-admin.service` | `watchme_admin` |
| **[心理] Whisper書き起こし** | `/vibe-transcriber/` | `8001` | `api-transcriber.service` | `watchme_api_whisper` |
| **[心理] プロンプト生成** | `/vibe-aggregator/` | `8009` | `mood-chart-api.service` | `watchme-api-whisper-prompt` |
| **[心理] スコアリング** | `/vibe-scorer/` | `8002` | `api-gpt-v1.service` | `watchme-api-whisper-gpt` |
| **[行動] 音声イベント検出** | `/behavior-features/` | `8004` | `watchme-behavior-yamnet.service` | `watchme-behavior-yamnet` |
| **[行動] 音声イベント集計** | `/behavior-aggregator/` | `8010` | `api-sed-aggregator.service` | `watchme-behavior-yamnet-aggregator` |
| **[感情] 音声特徴量抽出** | `/emotion-features/` | `8011` | `opensmile-api.service` | `opensmile` |
| **[感情] 感情スコア集計** | `/emotion-aggregator/` | `8012` | `opensmile-aggregator.service` | `watchme-opensmile-aggregator` |

*※公開エンドポイントが `/` から始まるものは、`https://api.hey-watch.me` に続くパスです。*

---

## 5. セキュリティ

### 5.1. RLS (Row Level Security) 【要対応】

**警告**: Supabaseの多くのテーブルでRLS（行単位セキュリティ）が無効化されています。
- **問題**: この状態では、APIキーを知る第三者がデータベースの情報を不正に閲覧・操作できる可能性があります。
- **対象テーブル**: `users`, `devices`, `vibe_whisper` など多数。
- **今後の対応**: 各テーブルに対し、認証ユーザーのみが自身のデータにアクセスできるよう、適切なRLSポリシーを定義し、有効化する必要があります。

### 5.2. 機密情報管理

APIキーやパスワードなどの機密情報は、ソースコードやドキュメントに直接記述せず、環境変数や秘匿情報管理サービスを使用して安全に管理してください。

---

## 6. 機密情報・認証情報

| サービス | 情報 | 値 |
| :--- | :--- | :--- |
| **AWS** | アカウントID | `754724220380` |
| | コンソールURL | `https://[アカウントID].signin.aws.amazon.com/console` |
| | ユーザー名 | `admin-user` |
| | パスワード | `[非公開]` |
| **AWS S3 (watchme-api-user)** | アクセスキーID | `[PLACEHOLDER_AWS_ACCESS_KEY_ID]` |
| | シークレットアクセスキー | `[PLACEHOLDER_AWS_SECRET_ACCESS_KEY]` |
| **Claude API** | APIキー | `[PLACEHOLDER_CLAUDE_API_KEY]` |
| **Slack API (Socket Mode)** | トークン | `[PLACEHOLDER_SLACK_SOCKET_TOKEN]` |

---
*最終更新: 2025年8月6日*
