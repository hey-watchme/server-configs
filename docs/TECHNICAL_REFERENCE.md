# WatchMe 技術仕様書

最終更新: 2025-11-15

> Status: Reference
> Source of truth: 現在の運用判断には [CURRENT_STATE.md](./CURRENT_STATE.md) と [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) を優先してください。
> Note: この文書には広い技術情報が残っていますが、一部の運用記述は現状より古い可能性があります。

## 🏗️ システムアーキテクチャ

### AWS EC2

- **インスタンスタイプ**: t4g.large (AWS Graviton2, 2 vCPU, 8GB RAM)
- **ストレージ**: 30GB gp3 SSD
- **リージョン**: ap-southeast-2 (Sydney)
- **IPアドレス**: 3.24.16.82

### AWSリージョン構成

**全てのAWSリソースは `ap-southeast-2` (Sydney) に統一**

| サービス | リージョン | 備考 |
|---------|-----------|------|
| EC2 | ap-southeast-2 | サーバー本体 |
| ECR | ap-southeast-2 | Dockerイメージレジストリ |
| Lambda | ap-southeast-2 | 処理関数 |
| S3 | ap-southeast-2 | 音声ファイル保管 |
| EventBridge | ap-southeast-2 | スケジューラー |
| SQS | ap-southeast-2 | メッセージキュー |

### AWS IAMユーザー

**アカウントID**: 754724220380

| ユーザー名 | 用途 | 権限 | アクセスキー | AWS CLIプロファイル |
|-----------|------|------|------------|------------------|
| **admin-user** | **管理・請求確認用** | AdministratorAccess, Billing | ✅ あり | `--profile admin` |
| **watchme-api-user** | **API操作用（デフォルト）** | S3, Lambda, SQS, CloudWatch, IAM, ECR | ✅ あり | `--profile default` |
| ses-smtp-user-watchme | メール送信用（SES） | SES関連のみ | 不明 | - |
| ses-smtp-user-watchme2 | メール送信用（SES） | SES関連のみ | 不明 | - |

**使い分け**:
- **日常的なAPI操作**: `watchme-api-user`（デフォルト）
- **請求情報確認・管理操作**: `admin-user`（`--profile admin`を指定）

**例**:
```bash
# 通常操作（デフォルト）
aws s3 ls

# 請求情報確認（adminプロファイル）
aws ce get-cost-and-usage --profile admin ...

# インスタンスタイプ変更（adminプロファイル推奨）
aws ec2 modify-instance-attribute --profile admin ...
```

**⚠️ セキュリティ注意**:
- `admin-user`のアクセスキーは厳重管理
- `~/.aws/credentials`のバックアップ推奨
- 不要になったら即座に削除

---

## 🌐 ネットワーク設計

### watchme-network

- **サブネット**: 172.27.0.0/16
- **ゲートウェイ**: 172.27.0.1
- **管理**: Docker network（CI/CDデプロイ時に自動参加）
- **設定ファイル**: docker-compose.infra.yml

### 接続コンテナ（稼働中のみ）

```
172.27.0.7  : watchme-vault-api
172.27.0.11 : vibe-transcriber
172.27.0.14 : watchme-admin
172.27.0.15 : watchme-avatar-uploader
172.27.0.17 : behavior-features
172.27.0.18 : emotion-features
172.27.0.20 : watchme-api-qr-code-generator
172.27.0.30 : janitor-api
172.27.X.X  : aggregator-api
172.27.X.X  : profiler-api
```

---

## 📡 サービス一覧

### クライアントアプリケーション

| サービス | プラットフォーム | 用途 | 技術スタック |
|---------|--------------|------|------------|
| iOS App | iOS | 録音・ダッシュボード閲覧 | Swift |
| Observer Device | ESP32/M5 Core2 | 30分ごと自動録音 | Arduino |
| Web Dashboard | Web | ダッシュボード閲覧 | React + Vite |

### EC2 APIサービス

| カテゴリ | サービス | ポート | エンドポイント | ECR | 役割 |
|---------|---------|--------|--------------|-----|------|
| **ゲートウェイ** | Vault API | 8000 | `/vault/` | watchme-api-vault | S3音声ファイル配信 |
| **音声処理** | Behavior Features | 8017 | `/behavior-analysis/features/` | watchme-behavior-analysis-feature-extractor | 527種類の音響検出 |
| | Emotion Features | 8018 | `/emotion-analysis/feature-extractor/` | watchme-emotion-analysis-feature-extractor | 音声感情認識 |
| | Vibe Transcriber | 8013 | `/vibe-analysis/transcriber/` | watchme-vibe-analysis-transcriber | マルチプロバイダーASR文字起こし |
| **集計・分析** | **Aggregator API** | **8011** | **`/aggregator/`** | **watchme-aggregator** | **Spot/Daily集計** |
| | **Profiler API** | **8051** | **`/profiler/`** | **watchme-profiler** | **Spot/Daily LLM分析** |
| **管理** | Admin | 9000 | `/admin/` | watchme-admin | 管理UI |
| | API Manager | 9001 | `/manager/` | watchme-api-manager | API管理UI |
| | Avatar Uploader | 8014 | `/avatar/` | watchme-api-avatar-uploader | アバター画像 |
| | **QR Code Generator** | **8021** | **`/qrcode/`** | **watchme-api-qr-code-generator** | **デバイスQRコード生成** |
| | Janitor | 8030 | `/janitor/` | watchme-api-janitor | 音声データ削除 |

### AWS Lambda関数

| 関数名 | トリガー | タイムアウト | 役割 |
|--------|---------|------------|------|
| audio-processor | S3 Upload | 10秒 | SQS送信 |
| audio-worker | SQS | 15分 | Feature Extractors並列実行 |
| dashboard-summary-worker | SQS | 15分 | Daily Aggregator実行 |
| dashboard-analysis-worker | SQS | 15分 | Daily Profiler実行 |
| janitor-trigger | EventBridge (6時間ごと) | 15分 | Janitor API実行 |
| demo-generator-trigger | EventBridge (30分ごと) | 15分 | デモデータ生成 |

---

## 🎙️ 音声処理API

### 1. Behavior Features API

**役割**: 527種類の音響イベント検出

**技術スタック**:
- モデル: PaSST (Patchout faSt Spectrogram Transformer)
- 処理時間: 10-20秒（60秒音声）

**検出イベント例**:
- 会話、笑い、泣き声
- 環境音（ドア、水、車）
- 動物の鳴き声
- 音楽、楽器

**エンドポイント**:
- `POST /behavior-analysis/features/fetch-and-process-paths`

### 2. Emotion Features API

**役割**: 音声感情認識

**技術スタック**:
- 処理時間: 10-20秒（60秒音声）
- 実装モデルはリポジトリ単位で管理（Kushinada / Hume 等、入れ替え可能）

> 検出感情の種類・粒度は使用モデルに依存する。
> 結果カラムもモデルにより異なる（`emotion_extractor_result` / `emotion_features_result_hume` 等）。
- その他4感情

**エンドポイント**:
- `POST /emotion-analysis/features/process/emotion-features`

### 3. Vibe Transcriber API

**役割**: 音声文字起こし（マルチプロバイダー対応）

**技術スタック**:
- マルチプロバイダー対応（Speechmatics / Deepgram / Groq / Azure / aiOla）
- 現在のプロバイダー設定は `api/vibe-analysis/transcriber-v2/README.md` 参照
- `app/asr_providers.py` の `CURRENT_PROVIDER` で切り替え

**エンドポイント**:
- `POST /vibe-analysis/transcriber/fetch-and-transcribe`

---

## 📊 集計・分析API

### 1. Aggregator API ✨

**役割**: Spot/Daily集計・プロンプト生成

**エンドポイント**:
- `POST /aggregator/spot` - Spot集計（録音ごと）
- `POST /aggregator/daily` - Daily集計（1日の累積）

**処理内容**:
- Feature Extractorsの結果を統合
- LLM分析用プロンプト生成
- データベース保存

**保存先**:
- `spot_aggregators` テーブル
- `daily_aggregators` テーブル

**処理時間**:
- Spot: 5-10秒
- Daily: 10-20秒

### 2. Profiler API ✨

**役割**: Spot/Daily LLM分析

**エンドポイント**:
- `POST /profiler/spot-profiler` - Spot分析（録音ごと）
- `POST /profiler/daily-profiler` - Daily分析（1日の累積）

**LLM設定**:
- プロバイダー: Groq
- モデル: openai/gpt-oss-120b (reasoning model)
- Reasoning Effort: medium

**処理内容**:
- Aggregatorからプロンプト取得
- LLM分析実行
- 結果を日本語で生成
- データベース保存

**保存先**:
- `spot_results` テーブル
- `daily_results` テーブル

**保存データ**:
- `vibe_score`: 心理スコア (-100〜+100)
- `summary`: サマリー（日本語）
- `behavior`: 検出された行動（カンマ区切り）
- `profile_result`: 完全な分析結果（JSONB）

**処理時間**:
- Spot: 10-15秒
- Daily: 10-30秒

---

## 🗄️ データベーステーブル

### Spot分析

| テーブル | 役割 | Primary Key |
|---------|------|------------|
| `audio_files` | 録音メタデータ | (device_id, recorded_at) |
| `spot_features` | 特徴量（音響・感情・文字起こし） | (device_id, recorded_at) |
| `spot_aggregators` | Spot分析用プロンプト | (device_id, recorded_at) |
| `spot_results` | Spot分析結果（LLM出力） | (device_id, recorded_at) |

### Daily分析

| テーブル | 役割 | Primary Key |
|---------|------|------------|
| `daily_aggregators` | Daily分析用プロンプト | (device_id, local_date) |
| `daily_results` | Daily分析結果（LLM出力） | (device_id, local_date) |

### 主要カラム

**共通**:
- `device_id`: デバイスID
- `local_date`: ローカル日付
- `created_at`, `updated_at`: タイムスタンプ

**spot_results**:
- `recorded_at`: 録音時刻（UTC）
- `vibe_score`, `summary`, `behavior`, `profile_result`

**daily_results**:
- `vibe_score`: 1日の平均スコア
- `summary`: 1日の総合サマリー
- `behavior`: 主要な行動パターン
- `profile_result`: 完全な分析結果（JSONB）
- `vibe_scores`: 録音時刻ベースのスコア配列（JSONB配列）
- `burst_events`: 感情変化イベント（JSONB配列）
- `processed_count`: 処理済みspot数

---

## 🌐 エンドポイント一覧

### 外部公開（Nginx経由 - HTTPS）

**ベースURL**: `https://api.hey-watch.me`

| パス | サービス | 用途 |
|------|---------|------|
| `/vault/` | Vault API | S3音声ファイル配信 |
| `/behavior-analysis/features/` | Behavior Features | 音響イベント検出 |
| `/emotion-analysis/feature-extractor/` | Emotion Features | 感情認識 |
| `/vibe-analysis/transcriber/` | Vibe Transcriber | 文字起こし |
| `/aggregator/` | Aggregator API | Spot/Daily集計 |
| `/profiler/` | Profiler API | Spot/Daily LLM分析 |
| `/janitor/` | Janitor | 音声データ削除 |
| `/admin/` | Admin | 管理UI |
| `/manager/` | API Manager | API管理UI |

### 内部通信（watchme-network内）

**形式**: `http://コンテナ名:ポート/`

例:
- `http://behavior-features:8017/`
- `http://emotion-features:8018/`
- `http://vibe-transcriber:8013/`

---

## ⚙️ Nginx設定

### タイムアウト設定

| API | パス | タイムアウト | 理由 |
|-----|------|------------|------|
| Behavior Features | `/behavior-analysis/features/` | 180秒 | 大規模モデル処理 |
| Emotion Features | `/emotion-analysis/feature-extractor/` | 180秒 | 感情認識処理 |
| Vibe Transcriber | `/vibe-analysis/transcriber/` | 180秒 | ASR処理 |
| Aggregator | `/aggregator/` | 60秒 | 軽量集計 |
| Profiler | `/profiler/` | 180秒 | LLM分析 |
| その他 | - | 60秒 | デフォルト |

### 設定例

```nginx
location /profiler/ {
    proxy_pass http://localhost:8051/;
    proxy_connect_timeout 180s;
    proxy_send_timeout 180s;
    proxy_read_timeout 180s;
}
```

### ⚠️ CORS設定の原則（重要）

**CORS（Cross-Origin Resource Sharing）はブラウザのセキュリティ機能**で、異なるドメイン間のAPIリクエストを制御します。

#### 絶対ルール：CORSは1箇所のみで設定

```
❌ NginxとFastAPI両方で設定 → ヘッダー重複でエラー
✅ どちらか一方のみで設定
```

**実例（2026-01-25発生）**:
```
Access-Control-Allow-Origin: https://business.hey-watch.me, *
                             ↑ FastAPIが追加    ↑ Nginxが追加
→ ブラウザがCORSエラーを返す
```

#### 現在の設定方針

| API種別 | 呼び出し元 | CORS設定場所 | 理由 |
|---------|-----------|-------------|------|
| **Business API** | ブラウザ | **FastAPI** | 細かいオリジン制御が必要 |
| Aggregator, Profiler等 | Lambda（サーバー間） | Nginx | サーバー間通信ではCORS不要だが互換性のため設定 |
| Behavior, Emotion等 | Lambda（サーバー間） | Nginx | 同上 |

#### 新規API追加時のガイドライン

1. **ブラウザから呼ばれるAPI** → FastAPI側でCORS設定、Nginx側は設定しない
2. **サーバー間通信のみのAPI** → Nginx側で`*`設定（または設定なし）
3. **既存APIにFastAPI CORSを追加する場合** → 必ずNginx側のCORS設定を削除

```python
# FastAPI側のCORS設定例（推奨）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://business.hey-watch.me",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

```nginx
# Nginx側：FastAPIでCORS設定済みのAPIは、CORS関連の記述を削除
location /business/ {
    proxy_pass http://localhost:8052/;
    # CORS設定なし（FastAPI側で処理）
}
```

---

## 🐳 コンテナ管理

全サービスは Docker + `restart: always` ポリシーで永続化。systemd は使用しない（2026-03-08 全廃済み）。

**確認コマンド**:
```bash
docker ps | grep watchme
docker logs <container-name> --tail 100 -f
```

**再起動**:
```bash
cd /home/ubuntu/<service-dir>
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

---

## 📈 パフォーマンス指標

### 処理時間（60秒音声）

| 処理 | 平均時間 |
|------|---------|
| S3イベント → SQS | 1-2秒 |
| Behavior Features | 10-20秒 |
| Emotion Features | 10-20秒 |
| Vibe Transcriber | 26-28秒 |
| Aggregator API (Spot) | 5-10秒 |
| Profiler API (Spot) | 10-15秒 |
| Aggregator API (Daily) | 10-20秒 |
| Profiler API (Daily) | 10-30秒 |
| **Spot分析合計** | **1-3分** |
| **Daily分析合計** | **30-40秒** |

### リソース使用量

**メモリ**:
- Behavior Features: 2-3GB
- Emotion Features: 3-3.5GB
- Vibe Transcriber: 1-2GB
- Aggregator/Profiler: 500MB-1GB

**ディスク**:
- 総容量: 30GB
- 使用中: 約26GB
- 空き: 約4GB

---

## 🔐 環境変数

### 必須環境変数

**AWS設定**:
```bash
AWS_REGION=ap-southeast-2
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
```

**Supabase設定**:
```bash
SUPABASE_URL=https://qvtlwotzuzbavrzqhyvt.supabase.co
SUPABASE_KEY=xxx
```

**LLM設定（Profiler API）**:
```bash
GROQ_API_KEY=gsk-xxx
```

**音声認識設定（Vibe Transcriber）**:
```bash
GROQ_API_KEY=gsk-xxx
```

---

## 🚨 トラブルシューティング

### エンドポイントの種類

**1. 内部通信** (watchme-network内):
- `http://コンテナ名:ポート/`
- 例: `http://profiler-api:8051/`

**2. 外部公開** (Nginx経由):
- `https://api.hey-watch.me/パス/`
- 例: `https://api.hey-watch.me/profiler/`

**3. ローカルテスト** (EC2内):
- `http://localhost:ポート/`
- 例: `http://localhost:8051/`

### よくあるエラー

**504 Gateway Timeout**:
- 原因: Nginxタイムアウト設定不足
- 解決: タイムアウトを180秒に延長

**Connection refused**:
- 原因: コンテナが起動していない
- 解決: `sudo systemctl restart <service-name>`

**Out of Memory**:
- 原因: 同時実行数が多すぎる
- 解決: Lambda同時実行数を制限

---

## 📚 関連ドキュメント

- **処理フロー**: [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md)
- **運用手順**: [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md)
- **CI/CD**: [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md)
- **システム概要**: [README.md](./README.md)

---

## 🚀 完了機能 (2025-11-15)

- ✅ Aggregator API統一（Spot/Daily）
- ✅ Profiler API統一（Spot/Daily）
- ✅ local_date対応
- ✅ マルチプロバイダーASR対応
- ✅ Kushinada感情認識
- ✅ PaSST音響検出
- ✅ Lambda自動処理パイプライン
