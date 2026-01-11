# WatchMe サーバー設定リポジトリ

最終更新: 2025-12-10

**⚠️ 重要: 2025-12-10にイベント駆動型アーキテクチャへ移行しました**

## 📚 ドキュメントガイド

| 目的 | ドキュメント | 内容 |
|------|-------------|------|
| **📖 基本理解** | [README.md](./README.md)（このファイル） | システム全体の構成・概要 |
| **🔄 処理の流れ** | [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md) | 音声処理の全体フロー |
| **🔧 技術仕様** | [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) | 全サービス一覧、エンドポイント |
| **📝 作業手順** | [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md) | デプロイ・運用手順 |
| **🚀 CI/CD詳細** | [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md) | CI/CD実装ガイド、**起動方式の全体像** |
| **📈 スケーラビリティ** | [SCALABILITY_ROADMAP.md](./SCALABILITY_ROADMAP.md) | 1人→100人→1000人への改善計画 |
| **⚠️ 既知の問題** | [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) | 既知の問題と対応TODO |
| **🎯 Phase 1実装** | [PHASE1_FIFO_QUEUE_IMPLEMENTATION.md](./PHASE1_FIFO_QUEUE_IMPLEMENTATION.md) | **FIFO Queue移行手順（コピペ可能）** |

---

## 📊 システム概要

WatchMeは音声録音から心理・感情分析までを自動実行するプラットフォームです。

### 主要コンポーネント

**クライアント:**
- iOS App (Swift)
- Web Dashboard (React)
- Observer Device (M5 Core2)

**AWS Lambda (自動処理 - イベント駆動型):**
- audio-processor: 3つのSQSキューへ並列送信
- asr-worker / sed-worker / ser-worker: 各Feature Extractor API呼び出し
- aggregator-checker: 全特徴量完了後にAggregator/Profiler実行
- dashboard-summary-worker: 日次集計実行
- dashboard-analysis-worker: 日次LLM分析実行
- weekly-profile-worker: 週次分析実行（毎日00:00）

**EC2 API (Sydney - t4g.large):**
- Vault API (ポート8000): S3音声ファイル配信
- Behavior Features (ポート8017): 527種類の音響検出（**PaSST**）
- Emotion Features (ポート8018): 8感情認識（**Kushinada**）
- Vibe Transcriber (ポート8013): **Deepgram Nova-2** 文字起こし
- **Aggregator API (ポート8050)**: Spot/Daily/Weekly集計・プロンプト生成
- **Profiler API (ポート8051)**: LLM分析（**OpenAI GPT-5 Nano**）
- Janitor (ポート8030): 音声データ自動削除
- Admin (ポート9000): 管理ツール
- Avatar Uploader (ポート8014): アバター画像管理
- Demo Generator (ポート8020): デモデータ生成

**データベース:**
- Supabase (PostgreSQL)

---

## 🔄 データフロー

### Spot分析（録音ごと）- イベント駆動型 ✅

```
iOS録音 → S3アップロード
  ↓
Lambda: audio-processor → 3つのSQSキューへ並列送信
  ├─ SQS: asr-queue → Lambda: asr-worker
  ├─ SQS: sed-queue → Lambda: sed-worker
  └─ SQS: ser-queue → Lambda: ser-worker
  ↓
各Lambda Worker → EC2 API (/async-process) 呼び出し（202 Accepted）
  ├─ Vibe Transcriber v2 (バックグラウンド処理)
  ├─ Behavior Features v2 (バックグラウンド処理)
  └─ Emotion Features v2 (バックグラウンド処理)
  ↓
各API完了 → SQS: feature-completed-queue に完了通知
  ↓
Lambda: aggregator-checker（3つ全て completed か確認）
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
  ↓
プッシュ通知送信 (AWS SNS → APNs → iOS)
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

| サービス | ポート | 役割 | 使用モデル/API | メモリ |
|---------|--------|------|--------------|--------|
| Vault API | 8000 | S3音声ファイル配信、SKIP機能 | - | 306 MB |
| **Behavior Features** | 8017 | 527種類の音響イベント検出（SED） | **PaSST** (Patchout faSt Spectrogram Transformer) | 600 MB |
| **Emotion Features** | 8018 | 8感情認識（SER） | **Kushinada** (HuBERT-large-JTES-ER) | 959 MB |
| **Vibe Transcriber** | 8013 | 音声文字起こし（ASR/STT） | **Deepgram Nova-2** | 84 MB |

### 集計・分析層

| サービス | ポート | 役割 | 使用モデル/API | メモリ |
|---------|--------|------|--------------|--------|
| **Aggregator API** | **8050** | **Spot/Daily/Weekly集計、プロンプト生成** | - | 55 MB |
| **Profiler API** | **8051** | **LLM分析（Spot/Daily/Weekly）** | **OpenAI GPT-5 Nano** | 160 MB |

### 管理層

| サービス | ポート | 役割 |
|---------|--------|------|
| API Manager | 9001 | API管理 |
| Admin | 9000 | 管理ツール |
| Avatar Uploader | 8014 | アバター画像管理 |
| QR Code Generator | 8021 | デバイス共有用QRコード生成 |
| Janitor | 8030 | 音声データ自動削除（6時間ごと） |
| Demo Generator | 8020 | デモデータ生成 |

### AWS Lambda

| 関数名 | トリガー | 役割 | 状態 |
|--------|---------|------|------|
| **audio-processor** | S3 Upload | 3つのSQSキューに並列送信 | ✅ 稼働中 |
| **asr-worker** | SQS: asr-queue | Vibe Transcriber API呼び出し | ✅ 稼働中 |
| **sed-worker** | SQS: sed-queue | Behavior Features API呼び出し | ✅ 稼働中 |
| **ser-worker** | SQS: ser-queue | Emotion Features API呼び出し | ✅ 稼働中 |
| **aggregator-checker** | SQS: feature-completed-queue | 全完了後にAggregator/Profiler実行 | ✅ 稼働中 |
| dashboard-summary-worker | SQS: dashboard-summary-queue | Daily Aggregator実行 | ✅ 稼働中 |
| dashboard-analysis-worker | SQS: dashboard-analysis-queue | Daily Profiler実行、プッシュ通知送信 | ✅ 稼働中 |
| weekly-profile-worker | EventBridge (毎日00:00 UTC+9) | Weekly Aggregator + Profiler実行 | ✅ 稼働中 |
| janitor-trigger | EventBridge (6時間ごと) | Janitor API実行 | ✅ 稼働中 |
| ~~demo-generator-trigger~~ | ~~EventBridge (30分ごと)~~ | ~~デモデータ生成~~ | ⚠️ 廃止済み（V2に移行） |
| **demo-generator-v2** | **EventBridge Scheduler (1時間ごと)** | **デモアカウントSpotデータ生成** | 🚀 **稼働準備中** |

---

## 📱 デモアカウント

**Device ID**: `a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d`（5歳男児・幼稚園年長）

- Lambda関数（demo-generator-v2）が1時間ごとにSpotデータを自動生成
- 新規ユーザーに自動的に追加され、アプリ機能を即座に体験可能
- 詳細: [`lambda-functions/watchme-demo-generator-v2/README.md`](../production/lambda-functions/watchme-demo-generator-v2/README.md)

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

### DNS / ドメイン管理

- **ドメイン**: hey-watch.me
- **ドメイン登録**: お名前.com（契約保持）
- **DNS管理**: Cloudflare（完全移行済み）
- **ネームサーバー**:
  - `piers.ns.cloudflare.com`
  - `tessa.ns.cloudflare.com`

**運用方針**:
- DNSレコードの追加・編集はすべてCloudflare Dashboardで実施
- お名前.com側のDNS設定（dnsv.jp）は使用しない

**⚠️ 重要: Cloudflare Proxy設定（2025-12-29追記）**

Cloudflareは**DNS管理とメール転送のみ**に使用し、**プロキシ機能は使用しない**こと。

**DNSレコード設定:**
- `api.hey-watch.me`: **DNS only（⚪グレー雲）** ← 必須
- `admin.hey-watch.me`: Proxied（🟠オレンジ雲）でも可
- `dashboard.hey-watch.me`: Proxied（🟠オレンジ雲）でも可

**理由:**
- Cloudflare Proxyを有効にすると、Lambda Worker → API のレスポンスが51秒かかり、30秒でタイムアウトする
- DNS Onlyに変更することで、2.3秒に短縮（**22倍高速化**）
- 2025-12-29に発覚・修正済み（DLQに1,350件蓄積していた問題を解決）

**確認方法:**
```bash
# 正しい設定（EC2のIPが返る）
host api.hey-watch.me 8.8.8.8
# → api.hey-watch.me has address 3.24.16.82

# 誤った設定（CloudflareのIPが返る）
# → api.hey-watch.me has address 104.21.9.46  ← これが出たら修正必要
```

### メール管理（Cloudflare Email Routing）

- **サポートメール**: support@hey-watch.me → matsumotokaya@gmail.com（転送）
- **設定**: Cloudflare Email Routing機能を使用
- **送信**: Gmail側で send-as 設定により support@hey-watch.me として返信可能
- **MX/TXTレコード**: Cloudflare が自動管理

**使用箇所**:
- iOSアプリ（プライバシーポリシー、利用規約）
- サービスサイト（問い合わせ先）
- App Store Connect（サポートメールアドレス）

### Docker Network

- **ネットワーク名**: watchme-network
- **サブネット**: 172.27.0.0/16
- **稼働コンテナ数**: 15サービス

### 管理ツール

- **Nginx**: リバースプロキシ（HTTPS）
- **Docker**: 全APIコンテナ管理（`restart: always`で自動起動）
- **systemd**: 3サービスのみ（Infrastructure、API Manager、Web Dashboard）
- **GitHub Actions**: CI/CD自動デプロイ（10サービス）

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

- **プロバイダー**: OpenAI
- **モデル**: GPT-5 Nano
- **使用開始**: 2025年12月
- **月額コスト**: $9.31（2025-12月実績、18.98M tokens）

**過去の構成**:
- ~~Groq API (openai/gpt-oss-120b)~~ ← 廃止済み

プロバイダー切り替えは `/projects/watchme/api/profiler/llm_providers.py` で設定。

---

## 📅 完了機能

### ✅ 2025-12-11 🎯 **イベント駆動型アーキテクチャへ移行完了**

- **SQSキュー作成**: 4つの新規キュー（asr/sed/ser/feature-completed）
- **Lambda関数作成**: 4つの新規Lambda（asr-worker/sed-worker/ser-worker/aggregator-checker）
- **EC2 API非同期化**: 3つのAPIに `/async-process` エンドポイント追加
- **DBステータス管理**: spot_featuresに3つのステータスカラム追加
- **audio-processor修正**: 3つのSQSキューへ並列送信
- **旧audio-worker削除**: 同期処理からイベント駆動型へ完全移行
- **タイムアウト問題解決**: Cloudflare 100秒制限を完全回避
- **動作確認完了**: 全APIが2秒以内で202 Acceptedを返却

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

## 📁 テスト音源（共有リソース）

全プロジェクトで使用可能なテスト音源を `watchme-vault` バケットに配置しています。

### S3パス

```
s3://watchme-vault/test-audio/parent-interview-yoridokoro/
├── full_raw.wav           # フルバージョン（87MB・約15分）
├── section001_raw.wav     # 抜粋版・生音声（3.1MB・約30秒）★推奨
└── section001_clean.wav   # 抜粋版・ノイズ除去（3.1MB・約30秒）
```

### 使用例

```bash
# Business API（トランスクリプションテスト）
aws s3 cp s3://watchme-vault/test-audio/parent-interview-yoridokoro/section001_raw.wav . \
  --region ap-southeast-2

# 直接URL（署名付きURL生成）
aws s3 presign s3://watchme-vault/test-audio/parent-interview-yoridokoro/section001_raw.wav \
  --region ap-southeast-2 --expires-in 3600
```

### 音源について

- **シチュエーション**: 保護者ヒアリング（児童発達支援）
- **録音日**: 2025-05-08
- **推奨**: `section001_raw.wav`（本番環境に最も近い）

---

## 📚 関連ドキュメント

詳細な仕様・運用手順は以下を参照:

- **処理フロー**: [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md)
- **技術仕様**: [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md)
- **運用手順**: [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md)
- **CI/CD**: [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md)
- **変更履歴**: [CHANGELOG.md](./CHANGELOG.md)
