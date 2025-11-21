# WatchMe サーバー設定リポジトリ

最終更新: 2025-11-15

## 📚 ドキュメントガイド

| 目的 | ドキュメント | 内容 |
|------|-------------|------|
| **📖 基本理解** | [README.md](./README.md)（このファイル） | システム全体の構成・概要 |
| **🔄 処理の流れ** | [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md) | 音声処理の全体フロー |
| **🔧 技術仕様** | [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) | 全サービス一覧、エンドポイント |
| **📝 作業手順** | [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md) | デプロイ・運用手順 |
| **🚀 CI/CD詳細** | [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md) | CI/CD実装ガイド、**起動方式の全体像** |

---

## 📊 システム概要

WatchMeは音声録音から心理・感情分析までを自動実行するプラットフォームです。

### 主要コンポーネント

**クライアント:**
- iOS App (Swift)
- Web Dashboard (React)
- Observer Device (M5 Core2)

**AWS Lambda (自動処理):**
- audio-worker: 音声分析の並列実行
- dashboard-summary-worker: 日次集計実行
- dashboard-analysis-worker: 日次LLM分析実行
- weekly-profile-worker: 週次分析実行（毎日00:00）

**EC2 API (Sydney - t4g.large):**
- Vault API (ポート8000): S3音声ファイル配信
- Behavior Features (ポート8017): 527種類の音響検出
- Emotion Features (ポート8018): 8感情認識
- Vibe Transcriber (ポート8013): Groq Whisper v3文字起こし
- **Aggregator API (ポート8011)**: Spot/Daily集計・プロンプト生成
- **Profiler API (ポート8051)**: LLM分析（Spot/Daily）
- Janitor (ポート8030): 音声データ自動削除

**データベース:**
- Supabase (PostgreSQL)

---

## 🔄 データフロー

### Spot分析（録音ごと）

```
iOS録音 → S3アップロード
  ↓
Lambda: audio-processor → SQS
  ↓
Lambda: audio-worker (並列実行)
  ├─ Behavior Features (音響検出)
  ├─ Emotion Features (感情認識)
  └─ Vibe Transcriber (文字起こし)
  ↓
Aggregator API (/aggregator/spot)
  → spot_aggregators テーブル (プロンプト生成)
  ↓
Profiler API (/profiler/spot-profiler)
  → spot_results テーブル (LLM分析結果)
```

### Daily分析（1日の累積）

```
Spot分析完了 → SQS: dashboard-summary-queue
  ↓
Lambda: dashboard-summary-worker
  ↓
Aggregator API (/aggregator/daily)
  → daily_aggregators テーブル (1日分のプロンプト生成)
  ↓
SQS: dashboard-analysis-queue
  ↓
Lambda: dashboard-analysis-worker
  ↓
Profiler API (/profiler/daily-profiler)
  → daily_results テーブル (1日分のLLM分析結果)
```

### Weekly分析（1週間の累積）✅ 本番稼働中

```
EventBridge (毎日00:00 UTC+9) → Lambda: weekly-profile-worker
  ↓
Aggregator API (/aggregator/weekly)
  → weekly_aggregators テーブル (1週間分のプロンプト生成)
  ↓
Profiler API (/profiler/weekly-profiler)
  → weekly_results テーブル (週次の印象的なイベント5件を抽出)
```

**処理タイミング:**
- 毎日 00:00（デバイスのローカル時間）に実行
- 前日を含む週（月曜〜日曜）のデータを処理
- 週の途中でも毎日更新されるため、常に最新の週次データを閲覧可能

---

## 📊 主要サービス一覧

### 音声処理層

| サービス | ポート | 役割 |
|---------|--------|------|
| Vault API | 8000 | S3音声ファイル配信、SKIP機能 |
| Behavior Features | 8017 | 527種類の音響イベント検出 |
| Emotion Features | 8018 | 8感情認識 |
| Vibe Transcriber | 8013 | Groq Whisper v3文字起こし |

### 集計・分析層

| サービス | ポート | 役割 |
|---------|--------|------|
| **Aggregator API** | **8011** | **Spot/Daily集計、プロンプト生成** |
| **Profiler API** | **8051** | **LLM分析（Spot/Daily）** |

### 管理層

| サービス | ポート | 役割 |
|---------|--------|------|
| API Manager | 9001 | API管理UI |
| Admin | 9000 | 管理ツール |
| Avatar Uploader | 8014 | アバター画像管理 |
| Janitor | 8030 | 音声データ自動削除（6時間ごと） |

### AWS Lambda

| 関数名 | トリガー | 役割 |
|--------|---------|------|
| audio-processor | S3 Upload | 録音ファイルをSQSに送信 |
| audio-worker | SQS | Feature Extractors並列実行 |
| dashboard-summary-worker | SQS | Daily Aggregator実行 |
| dashboard-analysis-worker | SQS | Daily Profiler実行 |
| weekly-profile-worker | EventBridge (毎日00:00 UTC+9) | Weekly Aggregator + Profiler実行 |
| janitor-trigger | EventBridge (6時間ごと) | Janitor API実行 |
| demo-generator-trigger | EventBridge (30分ごと) | デモデータ生成 |

---

## 🗄️ データベーステーブル

### Spot分析（録音ごと）

- **audio_files**: 録音メタデータ
- **spot_features**: 音響・感情・文字起こし特徴量
- **spot_aggregators**: Spot分析用プロンプト
- **spot_results**: Spot分析結果（LLM出力）

### Daily分析（1日の累積）

- **daily_aggregators**: Daily分析用プロンプト（1日分のspot_resultsを集約）
- **daily_results**: Daily分析結果（1日分のLLM出力）

### Weekly分析（1週間の累積）✅

- **weekly_aggregators**: Weekly分析用プロンプト（1週間分のspot_featuresを集約）
- **weekly_results**: Weekly分析結果（印象的なイベント5件を抽出）

### カラム構成

全テーブル共通:
- `device_id`: デバイスID
- `local_date`: デバイスのタイムゾーンに基づいたローカル日付
- `created_at`, `updated_at`: タイムスタンプ

daily_resultsの主要カラム:
- `vibe_score`: 平均バイブスコア (-100〜+100)
- `summary`: 1日の総合分析（日本語）
- `behavior`: 主要な行動（カンマ区切り）
- `profile_result`: 完全なLLM分析結果（JSONB）
- `vibe_scores`: 録音時刻ベースのスコア配列（JSONB配列）
- `burst_events`: 感情変化イベント（JSONB配列）
- `processed_count`: 処理済みspot数
- `llm_model`: 使用したLLMモデル

weekly_resultsの主要カラム:
- `summary`: 週の総合サマリー（日本語、2-3文）
- `memorable_events`: 印象的なイベント5件（JSONB配列）
  - rank: 順位（1-5）
  - date: 日付（YYYY-MM-DD）
  - time: 時刻（HH:MM）
  - day_of_week: 曜日（日本語）
  - event_summary: イベント要約（日本語）
  - transcription_snippet: 発話内容の抜粋
- `profile_result`: 完全なLLM分析結果（JSONB）
- `processed_count`: 処理済み録音数
- `llm_model`: 使用したLLMモデル

---

## 🌐 エンドポイント

### 外部アクセス

全API: `https://api.hey-watch.me/`

- `/vault/` → Vault API
- `/behavior-analysis/features/` → Behavior Features
- `/emotion-analysis/features/` → Emotion Features
- `/vibe-analysis/transcription/` → Vibe Transcriber
- `/aggregator/` → Aggregator API
  - `/aggregator/spot` - Spot集計
  - `/aggregator/daily` - Daily集計
  - `/aggregator/weekly` - Weekly集計
- `/profiler/` → Profiler API
  - `/profiler/spot-profiler` - Spot分析
  - `/profiler/daily-profiler` - Daily分析
  - `/profiler/weekly-profiler` - Weekly分析
- `/janitor/` → Janitor API

### ヘルスチェック

```bash
curl https://api.hey-watch.me/profiler/health
curl https://api.hey-watch.me/aggregator/health
```

---

## 🖥️ インフラストラクチャ

### EC2

- **インスタンス**: t4g.large (AWS Graviton2, 2 vCPU, 8GB RAM)
- **リージョン**: ap-southeast-2 (Sydney)
- **IP**: 3.24.16.82

### Docker Network

- **ネットワーク名**: watchme-network
- **サブネット**: 172.27.0.0/16
- **稼働コンテナ数**: 15サービス

### 管理ツール

- **Nginx**: リバースプロキシ（HTTPS）
- **systemd**: 15サービスの自動起動・監視
- **GitHub Actions**: CI/CD自動デプロイ

---

## 🚀 デプロイ

### API修正時

```bash
# 各APIリポジトリで
git add .
git commit -m "fix: 説明"
git push origin main

# → GitHub Actionsが自動でEC2にデプロイ
```

### サーバー設定変更時

```bash
# EC2に接続
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

# 設定を更新
cd /home/ubuntu/watchme-server-configs
git pull origin main
./setup_server.sh
```

---

## 🔧 LLM設定

### Profiler API

- **プロバイダー**: Groq
- **モデル**: openai/gpt-oss-120b (reasoning model)
- **Reasoning Effort**: medium

プロバイダー切り替えは `/projects/watchme/api/profiler/llm_providers.py` で設定。

---

## 📅 完了機能

### ✅ 2025-11-20

- **Weekly分析パイプライン**: 1週間分の累積分析（毎日00:00自動実行）
- **EventBridge自動トリガー**: 毎日00:00にweekly-profile-worker実行
- **週次印象的イベント抽出**: LLMによる1週間の重要なイベント5件を自動選出

### ✅ 2025-11-15

- **Spot分析パイプライン**: 録音ごとのリアルタイム分析
- **Daily分析パイプライン**: 1日分の累積分析
- **local_date対応**: タイムゾーンを考慮した日付管理
- **Aggregator API**: Spot/Daily集計の統一
- **Profiler API**: Spot/Daily LLM分析の統一

---

## 📚 関連ドキュメント

詳細な仕様・運用手順は以下を参照:

- **処理フロー**: [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md)
- **技術仕様**: [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md)
- **運用手順**: [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md)
- **CI/CD**: [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md)
- **変更履歴**: [CHANGELOG.md](./CHANGELOG.md)
