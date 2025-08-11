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
各コンテナ（サービス）同士は、Dockerの共通ネットワーク (`watchme-network`) を通じて相互に通信します。

コンテナから別のコンテナのAPIを呼び出す際は、ホスト名として **サービス名（コンテナ名）** を使用します。

- **例**: スケジューラーAPIコンテナからWhisper APIコンテナを呼び出す場合、接続先は `http://api-transcriber:8001` となります。
- **重要**: Linux環境では `host.docker.internal` は使用できません。必ずコンテナ名を使用してください。

#### ネットワーク接続の確認方法
新しいコンテナを追加した際は、必ず共通ネットワークに接続してください：
```bash
# ネットワークへの接続
docker network connect watchme-network [コンテナ名]

# 接続確認
docker exec [コンテナA] ping -c 1 [コンテナB]
```

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
| **[心理] プロンプト生成** | `/vibe-aggregator/generate-mood-prompt-supabase` | `8009` | `mood-chart-api.service` | `watchme-api-whisper-prompt` |
| **[心理] スコアリング** | `/vibe-scorer/analyze-vibegraph-supabase` | `8002` | `api-gpt-v1.service` | `watchme-api-whisper-gpt` |
| **[行動] 音声イベント検出** | `/behavior-features/` | `8004` | `watchme-behavior-yamnet.service` | `watchme-behavior-yamnet` |
| **[行動] 音声イベント集計** | `/behavior-aggregator/` | `8010` | `api-sed-aggregator.service` | `watchme-behavior-yamnet-aggregator` |
| **[感情] 音声特徴量抽出** | `/emotion-features/` | `8011` | `opensmile-api.service` | `opensmile` |
| **[感情] 感情スコア集計** | `/emotion-aggregator/` | `8012` | `opensmile-aggregator.service` | `watchme-opensmile-aggregator` |

*※公開エンドポイントが `/` から始まるものは、`https://api.hey-watch.me` に続くパスです。*

### API詳細情報（2025年8月10日更新）

#### 🔍 エンドポイントの3層構造を理解する（全API開発者必読）

WatchMeシステムには**3種類の異なるエンドポイント**が存在し、それぞれ異なる役割を持っています。**新しいAPIを追加する際や、既存APIを修正する際は、必ずこの3層構造を理解してください。**

##### 1️⃣ **管理・設定用エンドポイント**
- **用途**: UIから各APIの設定を管理（例：スケジューラーのON/OFF）
- **例**: `https://api.hey-watch.me/scheduler/status/whisper`
- **Nginxルーティング**: `/scheduler/` → `http://localhost:8015/api/scheduler/`
- **重要**: FastAPIは `/api/scheduler/` でリスンする（Nginxが `/scheduler/` を `/api/scheduler/` に変換するため）

##### 2️⃣ **API間の実行エンドポイント（内部通信）**
- **用途**: あるAPIが別のAPIを呼び出す際に使用（例：スケジューラーが各APIを実行）
- **例**: `http://api-transcriber:8001/fetch-and-transcribe`
- **注意**: 必ずコンテナ名を使用（`localhost`や`host.docker.internal`は使用不可）
- **定義場所**: 各APIの実装コード内

##### 3️⃣ **外部公開エンドポイント**
- **用途**: ブラウザや外部システムからAPIにアクセス
- **例**: `https://api.hey-watch.me/vibe-transcriber/`
- **Nginxルーティング**: 公開パスから内部APIへプロキシ
- **定義場所**: Nginx設定ファイル（このリポジトリの`sites-available/`）

##### 📊 エンドポイント相関図
```
[外部クライアント]
    ↓ ③ 公開エンドポイント
    ↓ https://api.hey-watch.me/vibe-transcriber/
[Nginx]
    ↓ プロキシ
[api-transcriber:8001]

[管理UI]
    ↓ ① 管理用エンドポイント
    ↓ https://api.hey-watch.me/scheduler/toggle/whisper
[Nginx] → [scheduler-api:8015/api/scheduler/toggle/whisper]

[スケジューラー]
    ↓ ② 内部実行エンドポイント
    ↓ http://api-transcriber:8001/fetch-and-transcribe
[api-transcriber]
```

#### 🚨 重要：コンテナ間通信のエンドポイント一覧

スケジューラーやコンテナ間で通信する際の**正確な情報**（上記の②に該当）：

| API種類 | コンテナ名 | ポート | 内部エンドポイント | HTTPメソッド | 処理タイプ |
|---------|-----------|--------|------------------|-------------|-----------|
| **[心理] Whisper書き起こし** | `api-transcriber` | 8001 | `/fetch-and-transcribe` | POST | ファイルベース |
| **[心理] プロンプト生成** | `api_gen_prompt_mood_chart` | 8009 | `/generate-mood-prompt-supabase` | **GET** ⚠️ | デバイスベース |
| **[心理] スコアリング** | `api-gpt-v1` | 8002 | `/analyze-vibegraph-supabase` | POST | デバイスベース |
| **[行動] 音声イベント検出** | `api_sed_v1-sed_api-1` | 8004 | `/fetch-and-process-paths` | POST | ファイルベース |
| **[行動] 音声イベント集計** | `api-sed-aggregator` | 8010 | `/analysis/sed` | POST | デバイスベース |
| **[感情] 音声特徴量抽出** | `opensmile-api` | 8011 | `/process/emotion-features` | POST | ファイルベース |
| **[感情] 感情スコア集計** | `opensmile-aggregator` | 8012 | `/analyze/opensmile-aggregator` | POST | デバイスベース |

**⚠️ 注意事項:**
1. コンテナ間通信では`localhost`は使用不可。必ずコンテナ名を使用
2. `vibe-aggregator`（プロンプト生成）のみGETメソッド、他はすべてPOST
3. 公開URLのパスとコンテナ内部のパスは異なる場合がある

### ポート番号の統一について

すべてのサービスは、混乱を避けるため**公開ポート（ホスト側）とコンテナ内部ポートを同じ番号で統一**しています。これにより、設定の一貫性とメンテナンス性が向上します。

- **例**: opensmile-apiは公開ポート8011、内部ポート8011（2025年8月9日に統一完了）

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
---

## 7. トラブルシューティング

### よくある問題と解決方法

#### エンドポイントの混同による404エラー（最重要）
**症状**: 
- APIが404エラーを返す
- `Cannot GET /api/scheduler/api/scheduler/...` のような二重パスエラー
- 管理UIから設定が保存できない

**原因**: 3種類のエンドポイント（管理用、内部実行用、外部公開用）を混同している

**解決策**:
1. 上記の「エンドポイントの3層構造」を理解する
2. FastAPIでは、Nginxのプロキシパスを考慮したパスでリスンする
   - 例：Nginxが `/scheduler/` → `/api/scheduler/` にプロキシする場合、FastAPIは `/api/scheduler/` でリスン
3. コンテナ間通信では必ずコンテナ名を使用（localhostは不可）

#### Dockerコンテナ間通信エラー
**症状**: `Failed to resolve 'host.docker.internal'`
**原因**: Linux環境では `host.docker.internal` が使用できない
**解決策**: 
1. コンテナ名を使用して通信（例: `http://api-transcriber:8001`）
2. 両方のコンテナを共通ネットワーク（`watchme-network`）に接続

#### スケジューラーAPIエンドポイントエラー（2025年8月10日追記）
**症状**: スケジューラーが手動実行では成功するAPIを自動実行で失敗する
**原因**: エンドポイントのパスやHTTPメソッドの不一致
**解決策**:
1. 上記の「API詳細情報」表を必ず参照
2. 特に注意が必要なAPI:
   - `vibe-aggregator`: GETメソッドを使用（他はPOST）
   - `emotion-aggregator`: パスは `/analyze/opensmile-aggregator`（`/analyze/batch`ではない）
   - `vibe-scorer`: パスは `/analyze-vibegraph-supabase`（`/analyze-batch`ではない）
3. 修正ファイル:
   - `/home/ubuntu/watchme-api-manager/scheduler/run-api-process-docker.py`
   - API_CONFIGS辞書のエンドポイント設定を確認

#### API処理のタイムアウト
**症状**: Whisper APIなどの処理でタイムアウトエラーが発生
**注意**: 音声処理は数分から数十分かかることがあるため、タイムアウトエラーが表示されても処理は継続されている可能性が高い
**確認方法**: 
- ログファイルで処理状況を確認
- データベースで処理結果を確認

---

*最終更新: 2025年8月9日*
