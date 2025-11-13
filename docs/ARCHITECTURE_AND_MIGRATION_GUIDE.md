# 🏗️ WatchMe アーキテクチャ・移行ガイド

**プロジェクト**: 心理・感情モニタリングプラットフォーム
**作成日**: 2025-11-11
**最終更新**: 2025-11-13
**ステータス**: ✅ Phase 3完了（85%） / ✅ Phase 4-1完了（Spot Profiler + 日本語出力）（95%）

---

## 📖 目次

1. [システムアーキテクチャ概要](#システムアーキテクチャ概要)
2. [3レイヤー設計思想](#3レイヤー設計思想)
3. [データフロー全体像](#データフロー全体像)
4. [データベーススキーマ](#データベーススキーマ)
5. [進捗状況](#進捗状況)
6. [次のタスク](#次のタスク)
7. [変更履歴](#変更履歴)

---

## 🎯 システムアーキテクチャ概要

### 設計原則

**UTC統一アーキテクチャ**: すべてのタイムスタンプをUTCで保存し、表示時に各デバイスのタイムゾーンでローカル時間に変換

**3レイヤー設計**: 特徴抽出 → 統合 → プロファイリング の明確な責任分離

**マイクロサービスアーキテクチャ**: 各APIは独立して動作し、データベースを通じて連携

---

## 🏗️ 3レイヤー設計思想

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Feature Extraction（特徴抽出層）                      │
│                                                               │
│ 役割: 音声ファイルから生データを抽出                             │
│ 技術: ASR (音声認識), SED (音響イベント), SER (感情認識)        │
│                                                               │
│ /api/vibe-analysis/transcriber                               │
│   ├─ 入力: S3音声ファイル                                      │
│   └─ 出力: spot_features.vibe_transcriber_result (TEXT)      │
│                                                               │
│ /api/behavior-analysis/feature-extractor                     │
│   ├─ 入力: S3音声ファイル                                      │
│   └─ 出力: spot_features.behavior_extractor_result (JSONB)   │
│                                                               │
│ /api/emotion-analysis/feature-extractor                      │
│   ├─ 入力: S3音声ファイル                                      │
│   └─ 出力: spot_features.emotion_extractor_result (JSONB)    │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Aggregation（統合層）                                │
│                                                               │
│ 役割: 3つの特徴データを統合し、LLM用プロンプトを生成             │
│ 技術: データ統合、時間コンテキスト生成、プロンプトエンジニアリング │
│                                                               │
│ /api/aggregator                                              │
│   ├─ 入力: spot_features (ASR + SED + SER)                   │
│   ├─ 処理: デバイスtimezone取得 → UTC→ローカル変換             │
│   │        subject_info統合 → プロンプト生成                   │
│   └─ 出力: spot_aggregators.aggregated_prompt (TEXT)         │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Profiler（プロファイリング層）🎯 このプロジェクトの中心  │
│                                                               │
│ 役割: LLM分析による心理プロファイリング（複数時間軸）             │
│ 技術: ChatGPT/Groq, 累積分析, 長期トレンド分析                  │
│                                                               │
│ /api/profiler ✅ 本番稼働中（2025-11-13）                       │
│                                                               │
│   ├─ POST /spot-profiler ✅                                   │
│   │  ├─ 入力: spot_aggregators.prompt                        │
│   │  ├─ 処理: LLM分析（スポット録音の心理分析）                │
│   │  ├─ 出力: spot_results                                    │
│   │  └─ 説明: 1回の録音（任意の長さ：3秒〜10分）の心理分析       │
│   │                                                           │
│   ├─ POST /daily-profiler                                    │
│   │  ├─ 入力: spot_results（1日分）                           │
│   │  ├─ 処理: LLM累積分析（1日の心理トレンド）                 │
│   │  ├─ 出力: summary_daily                                   │
│   │  └─ 説明: 1日分のspot録音を統合し、日次の心理状態を分析     │
│   │                                                           │
│   ├─ POST /weekly-profiler 🆕                                │
│   │  ├─ 入力: summary_daily（7日分）                          │
│   │  ├─ 処理: LLM週次分析（1週間の心理変動）                   │
│   │  ├─ 出力: summary_weekly                                  │
│   │  └─ 説明: 週単位の心理トレンド、週内の変動パターン分析       │
│   │                                                           │
│   └─ POST /monthly-profiler 🆕                               │
│      ├─ 入力: summary_daily（30日分）                         │
│      ├─ 処理: LLM月次分析（1ヶ月の長期トレンド）               │
│      ├─ 出力: summary_monthly                                 │
│      └─ 説明: 月単位の心理変化、生活リズム、長期的傾向分析       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 データフロー全体像

### Phase 1: 録音 → S3保存

```
iOS/Observer Device
  ↓ 音声録音（任意の長さ）
S3 Bucket (watchme-vault)
  ↓ S3イベント
Lambda (audio-processor)
  ↓ SQSキュー
Lambda (audio-worker)
  ↓ HTTPリクエスト
Vault API
  ↓ INSERT
audio_files (recorded_at: UTC)
```

---

### Phase 2: 特徴抽出（並列実行）

```
Lambda (audio-worker) → 3つのAPIを並列実行

┌─ Vibe Transcriber (ASR)
│    └─ 出力: spot_features.vibe_transcriber_result
│
├─ Behavior Features (SED)
│    └─ 出力: spot_features.behavior_extractor_result
│
└─ Emotion Features (SER)
     └─ 出力: spot_features.emotion_extractor_result

⏱️ 処理時間: 約5-10秒（並列処理）
```

---

### Phase 3: 統合・プロンプト生成

```
Aggregator API (/api/aggregator)

1. spot_features から ASR + SED + SER データ取得
2. devices.timezone 取得
3. UTC → ローカル時間に変換（pytz使用）
4. subject_info（年齢・性別）取得
5. 時間コンテキスト生成（季節、曜日、時間帯、祝日）
6. 統合プロンプト生成（3つのデータを統合）
7. spot_aggregators に保存

⏱️ 処理時間: 約1-2秒
```

---

### Phase 4: プロファイリング（LLM分析）🎯

```
Profiler API (/api/profiler) 🚧 新規作成予定

┌─ Spot Profiler
│  1. spot_aggregators.aggregated_prompt 取得
│  2. ChatGPT/Groq LLM実行
│  3. spot_results に保存
│  ⏱️ 処理時間: 約3-5秒
│
├─ Daily Profiler
│  1. spot_results（1日分）取得
│  2. 累積分析プロンプト生成
│  3. ChatGPT/Groq LLM実行
│  4. summary_daily に保存
│  ⏱️ 処理時間: 約5-10秒
│
├─ Weekly Profiler 🆕
│  1. summary_daily（7日分）取得
│  2. 週次分析プロンプト生成
│  3. ChatGPT/Groq LLM実行
│  4. summary_weekly に保存
│  ⏱️ 処理時間: 約10-15秒
│
└─ Monthly Profiler 🆕
   1. summary_daily（30日分）取得
   2. 月次分析プロンプト生成
   3. ChatGPT/Groq LLM実行
   4. summary_monthly に保存
   ⏱️ 処理時間: 約15-20秒
```

---

### Phase 5: 表示（iOS/Web）

```
iOS/Web Dashboard

1. 各resultsテーブルからデータ取得
   - spot_results: スポット分析結果
   - summary_daily: 日次分析結果
   - summary_weekly: 週次分析結果
   - summary_monthly: 月次分析結果

2. devices.timezone 取得

3. UTC → ローカル時間に変換

4. UI表示
   - タイムライン表示
   - スコアグラフ
   - 心理分析サマリー
   - トレンド分析
```

---

## 🗄️ データベーススキーマ

### 1. audio_files - 録音ファイル情報

```sql
CREATE TABLE audio_files (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC
  file_path TEXT NOT NULL,
  vibe_transcriber_status TEXT DEFAULT 'pending',
  behavior_extractor_status TEXT DEFAULT 'pending',
  emotion_extractor_status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (device_id, recorded_at)
);
```

**役割**: S3にアップロードされた音声ファイルのメタデータ管理

---

### 2. spot_features - 特徴抽出結果

```sql
CREATE TABLE spot_features (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC

  -- 3つの特徴抽出結果
  vibe_transcriber_result TEXT,          -- ASR: 文字起こしテキスト
  behavior_extractor_result JSONB,       -- SED: 527種類の音響イベント
  emotion_extractor_result JSONB,        -- SER: 8感情スコア + OpenSMILE特徴量

  -- 処理ステータス
  vibe_transcriber_status TEXT,
  vibe_transcriber_processed_at TIMESTAMPTZ,
  behavior_extractor_status TEXT,
  behavior_extractor_processed_at TIMESTAMPTZ,
  emotion_extractor_status TEXT,
  emotion_extractor_processed_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (device_id, recorded_at)
);
```

**役割**: Layer 1（特徴抽出層）の出力データ保存

**重要**: RLS（Row Level Security）は無効化（内部API専用テーブル）

---

### 3. spot_aggregators - 統合プロンプト

```sql
CREATE TABLE spot_aggregators (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC
  prompt TEXT NOT NULL,               -- LLM分析用統合プロンプト（旧: aggregated_prompt）
  context_data JSONB,                 -- メタデータ（timezone, subject_info等）
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- 旧: aggregated_at
  PRIMARY KEY (device_id, recorded_at)
);
```

**役割**: Layer 2（統合層）の出力データ保存

**重要**: RLS（Row Level Security）は無効化（内部API専用テーブル）

**prompt の内容**（約4000文字）- Timeline-Synchronized Format:
- Task Definition & Guidelines: ~2500文字
- Temporal Context: ~200文字
- Full Transcription (時系列なし): 100-500文字
- Timeline (10-second blocks): ~900文字
  - 各ブロックでSED + SER を同期表示
  - パターン自動検出（笑い声+喜び、衝突音+怒り等）
- Overall Summary: ~400文字
  - 統計情報（Speech Activity, Emotion Trend）
  - キーパターン（感情ピーク、同時発生イベント）

---

### 4. spot_results - スポット分析結果

```sql
CREATE TABLE spot_results (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC

  -- 分析結果
  vibe_score DOUBLE PRECISION NULL,  -- 心理スコア (-100 to +100)
  profile_result JSONB NOT NULL,     -- LLMの完全分析結果
  summary TEXT,                       -- ✅ NEW (2025-11-13): ダッシュボード表示用サマリー（日本語）
  behavior TEXT,                      -- ✅ NEW (2025-11-13): 主要行動パターン（カンマ区切り、3つ）

  -- メタ情報
  llm_model TEXT NULL,               -- 使用したLLMモデル (e.g., "groq/openai/gpt-oss-120b")
  created_at TIMESTAMPTZ DEFAULT NOW(),

  PRIMARY KEY (device_id, recorded_at)
);
```

**役割**: Layer 3（Profiler - Spot）の出力データ保存

**新カラム (2025-11-13追加)**:
- `summary` (TEXT): 日本語サマリー（2-3文、例："朝食の時間。家族と一緒に食事をしている。"）
- `behavior` (TEXT): 主要行動パターン3つ（カンマ区切り、例："会話, 食事, 家族団らん"）
  - 会話が検出された場合は必ず「会話」を含める

**profile_result JSONB構造**:
- `summary`: 状況の概要（日本語）
- `behavior`: 行動パターン（日本語、カンマ区切り）
- `psychological_analysis`: 心理分析（mood_state, mood_description[日本語], emotion_changes[日本語]）
- `behavioral_analysis`: 行動分析（detected_activities, behavior_pattern[日本語], situation_context[日本語]）
- `acoustic_metrics`: 音響メトリクス（speech_time_ratio, average_loudness_db, voice_stability_score等）
- `key_observations`: 重要な観察事項（日本語配列）

**RLS**: 無効（内部API専用）

---

### 5. summary_daily - 日次分析結果（既存）

```sql
CREATE TABLE summary_daily (
  device_id TEXT NOT NULL,
  date DATE NOT NULL,

  -- 累積分析結果
  cumulative_evaluation TEXT,         -- 1日の総合評価
  mood_trajectory TEXT,               -- 気分の変動パターン
  current_state_score INTEGER,        -- 現在の状態スコア

  -- 統計情報
  spot_count INTEGER,                 -- スポット録音の回数
  average_vibe_score REAL,            -- 平均vibeスコア

  -- 詳細分析
  daily_analysis_result JSONB,        -- LLMの完全レスポンス
  analyzed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),

  PRIMARY KEY (device_id, date)
);
```

**役割**: Layer 3（Profiler - Daily）の出力データ保存

---

### 6. summary_weekly - 週次分析結果 🆕

```sql
CREATE TABLE summary_weekly (
  device_id TEXT NOT NULL,
  week_start_date DATE NOT NULL,      -- 週の開始日（月曜日）
  week_end_date DATE NOT NULL,        -- 週の終了日（日曜日）

  -- 週次分析結果
  weekly_evaluation TEXT,             -- 1週間の総合評価
  mood_trend TEXT,                    -- 週内の気分トレンド
  average_weekly_score INTEGER,       -- 週平均スコア

  -- 統計情報
  active_days INTEGER,                -- アクティブな日数
  total_spot_count INTEGER,           -- 週全体のスポット録音数

  -- 詳細分析
  weekly_analysis_result JSONB,       -- LLMの完全レスポンス
  analyzed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),

  PRIMARY KEY (device_id, week_start_date)
);
```

**役割**: Layer 3（Profiler - Weekly）の出力データ保存 🆕

---

### 7. summary_monthly - 月次分析結果 🆕

```sql
CREATE TABLE summary_monthly (
  device_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,

  -- 月次分析結果
  monthly_evaluation TEXT,            -- 1ヶ月の総合評価
  long_term_trend TEXT,               -- 長期トレンド分析
  average_monthly_score INTEGER,      -- 月平均スコア

  -- 統計情報
  active_days INTEGER,                -- アクティブな日数
  total_spot_count INTEGER,           -- 月全体のスポット録音数

  -- 詳細分析
  monthly_analysis_result JSONB,      -- LLMの完全レスポンス
  analyzed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),

  PRIMARY KEY (device_id, year, month)
);
```

**役割**: Layer 3（Profiler - Monthly）の出力データ保存 🆕

---

### 8. devices（既存テーブル）

```sql
-- timezone カラムを使用
SELECT device_id, timezone FROM devices;
-- 例: 9f7d6e27-..., Asia/Tokyo
```

**役割**: デバイスのタイムゾーン情報管理（UTC→ローカル時間変換に使用）

---

## 📋 進捗状況（2025-11-12 最終更新）

### ✅ Phase 1完了: 録音（iOS → S3 → Vault API）

- ✅ データベース修正完了
- ✅ iOS アプリ: `recorded_at` をUTCで送信
- ✅ Vault API: `local_datetime` 削除、S3パス秒単位精度化
- ✅ 本番動作確認済み 🎉

---

### ✅ Phase 2完了: 特徴抽出（ASR + SED + SER）

- ✅ Vibe Transcriber（ASR）: `spot_features` 移行完了
- ✅ Behavior Features（SED）: `spot_features` 移行完了
- ✅ Emotion Feature Extractor v2（SER）: `spot_features` 移行完了
- ✅ 本番動作確認済み 🎉

---

### ✅ Phase 3完了: 統合・プロンプト生成（2025-11-12 完了）🎉

#### 基本実装（午前〜午後）

- ✅ Aggregator API: ASR+SED+SER統合、timezone対応、プロンプト生成完了
- ✅ `spot_aggregators` テーブルに保存
  - `prompt` カラム（旧 aggregated_prompt）
  - `context_data` カラム（JSONB）
  - `created_at` カラム（旧 aggregated_at）
  - RLS無効化完了
- ✅ UTC統一アーキテクチャ対応完了
  - `local_date`, `local_time` カラム削除
  - UTC→ローカル時間変換はプロンプト生成時のみ実施
- ✅ Nginx設定追加完了
  - `/aggregator/` → `http://localhost:8050/aggregator/`

#### Timeline-Synchronized Format実装（夕方）🎉

- ✅ **データ構造修正完了**
  - `data_fetcher.py`: 配列を直接返すように修正（辞書誤認識を解消）
  - 問題: `behavior_extractor_result`, `emotion_extractor_result` を辞書として誤処理
  - 解決: 実際は配列（時間ベース・チャンクベース）として正しく処理

- ✅ **プロンプト形式を全面刷新**
  - 旧: ASR/SED/SERが別々のセクション → 時系列の文脈が失われる
  - 新: 10秒ごとにSED+SERを同期表示（タイムライン型） → 時系列を保持
  - パターン検出機能追加: 「笑い声 + 喜び」「衝突音 + 怒り」を自動検出

- ✅ **技術名の汎用化**
  - YAMNet → SED (Sound Event Detection)
  - Kushinada → SER (Speech Emotion Recognition)
  - OpenSMILE → SER（統一）

- ✅ **プロンプト構造**
  ```
  1. Full Transcription (時系列なし)
  2. Timeline (10-second blocks): SED + SER 同期表示
  3. Pattern Detection: 自動相関検出
  4. Overall Summary: 統計とキーパターン
  ```

- ✅ **本番動作確認済み** 🎉
  - URL: https://api.hey-watch.me/aggregator/spot
  - プロンプト長: 4000文字（旧5000文字から20%削減）
  - 処理時間: 1-2秒
  - SED/SERデータ統合成功: "Data not available" 問題解消

#### 効果

- 「怒って物を投げた」のような複雑なシーンを時系列で正確に分析可能
- 感情の変化（喜び→怒り→悲しみ）を時間軸で追跡
- LLM分析の精度が大幅に向上

---

### ✅ Phase 4-1完了: Profiler API - Spot Profiler本番稼働開始（2025-11-13）

#### 完了した作業

**1. Profiler API新規作成・本番デプロイ完了**

ディレクトリ: `/Users/kaya.matsumoto/projects/watchme/api/profiler`

- ✅ Spot Profiler実装完了（`/spot-profiler` エンドポイント）
- ✅ 入力元: `spot_aggregators.prompt`（Timeline-Synchronized Format）
- ✅ 出力先: `spot_results` テーブル（新スキーマ）
- ✅ LLMプロバイダー抽象化（OpenAI/Groq対応）
- ✅ CI/CD自動デプロイ構築（GitHub Actions → ECR → EC2）
- ✅ 本番環境での動作確認完了

**インフラ構成**:
- Container: `profiler-api` (port 8051)
- ECR: `watchme-profiler`
- systemd: `profiler-api.service`
- Nginx: `/profiler/` → `http://localhost:8051/`
- Health check: `/health`
- External URL: `https://api.hey-watch.me/profiler/`

**LLM設定**:
- Provider: Groq
- Model: openai/gpt-oss-120b (reasoning model)
- Reasoning Effort: medium

**データベーススキーマ最終版**:
- 旧カラム削除完了: `local_date`, `local_time`, `behavior_score`, `emotion_score`, `composite_score`
- カラム名統一: `profiled_at` → `created_at`
- ✅ **新カラム追加** (2025-11-13): `summary` (TEXT), `behavior` (TEXT)
- RLS無効化（内部API専用）

#### 残作業（Phase 4-2以降）

**2. 累積分析エンドポイント追加**（今後の拡張）

- 🚧 Daily Profiler: `/daily-profiler`（日次分析）
- 🚧 Weekly Profiler: `/weekly-profiler`（週次分析）
- 🚧 Monthly Profiler: `/monthly-profiler`（月次分析）

**推定作業時間**: 各2-3時間

---

### ⏳ Phase 5未着手: クライアント側表示

- ⏳ iOS アプリ: 各resultsテーブルからデータ取得・表示
- ⏳ Web ダッシュボード: 同様（優先度低・休止中）

**推定作業時間**: 3-4時間

---

## 🚀 次のタスク（優先度順）

### Task 1: 累積分析エンドポイント実装

Phase 4-2以降で実装予定：
- Daily Profiler: `/daily-profiler`
- Weekly Profiler: `/weekly-profiler`
- Monthly Profiler: `/monthly-profiler`

### Task 2: クライアント側表示実装

各resultsテーブルからデータ取得・表示:
- iOS アプリでの実装
- Web ダッシュボードでの実装（優先度低）

---

## 🔧 開発メモ

### タイムゾーン変換

**Python (Aggregator API)**:
```python
import pytz
from datetime import datetime

# UTC to JST
utc_time = datetime(2025, 11, 11, 12, 31, 1, tzinfo=pytz.UTC)
jst = pytz.timezone('Asia/Tokyo')
local_time = utc_time.astimezone(jst)
# → 2025-11-11 21:31:01+09:00
```

**Swift (iOS)**:
```swift
let utcTime = Date()  // UTC
let timezone = TimeZone(identifier: "Asia/Tokyo")!
let formatter = DateFormatter()
formatter.timeZone = timezone
let localString = formatter.string(from: utcTime)
```

---

## 📝 変更履歴

### 2025-11-12 夕方セッション - Timeline-Synchronized Format完成 🎉

**目的**: 時系列の文脈を保持し、LLM分析の精度向上

**問題発見**:
- Aggregator APIがASRデータのみ使用、SED/SERが "Data not available"
- 原因: データ構造の誤認識（配列を辞書として処理）

**修正内容**:

1. **データ取得ロジック修正** (`data_fetcher.py`)
   - `get_behavior_data()`: 配列を直接返すように修正
   - `get_emotion_data()`: 配列を直接返すように修正
   - 存在しないキー（`events`, `selected_features_timeline`）への参照を削除

2. **プロンプト形式を全面刷新** (`prompt_generator.py`)
   - 旧: ASR/SED/SERが別々のセクション → 時系列の文脈が失われる
   - 新: 10秒ごとにSED+SERを同期表示（タイムライン型）
   - パターン検出機能追加: 「笑い声 + 喜び」「衝突音 + 怒り」を自動検出
   - 技術名の汎用化: YAMNet→SED, Kushinada→SER

3. **プロンプト構造**
   ```
   1. Full Transcription (時系列なし)
   2. Timeline (10-second blocks): SED + SER 同期表示
   3. Pattern Detection: 自動相関検出
   4. Overall Summary: 統計とキーパターン
   ```

**効果**:
- 「怒って物を投げた」のような複雑なシーンを時系列で正確に分析可能
- 感情の変化（喜び→怒り→悲しみ）を時間軸で追跡
- プロンプト長: 5000文字 → 4000文字（20%削減）
- SED/SERデータ統合成功: "Data not available" 問題完全解消

**コミット**:
- `fix: Correct data structure handling for SED/SER integration`
- `feat: Redesign prompt format with timeline synchronization`
- `docs: Update README with timeline-synchronized format details`

---

### 2025-11-12 午後セッション - Phase 3基本実装完了 🎉

- **Aggregator API本番稼働開始**:
  - エンドポイント: `https://api.hey-watch.me/aggregator/spot`
  - 処理時間: 1-2秒
  - プロンプト長: 約4700文字

- **データベース修正**:
  - `spot_aggregators` テーブル修正完了
  - カラム名変更: `aggregated_prompt` → `prompt`, `aggregated_at` → `created_at`
  - 不要カラム削除: `local_date`, `local_time`（UTC統一アーキテクチャ対応）
  - RLS無効化完了

- **Nginx設定追加**:
  - `/aggregator/` → `http://localhost:8050/aggregator/`
  - proxy_pass設定修正（FastAPIの内部パス構造に対応）

- **コード修正**:
  - UTC統一アーキテクチャ対応
  - `local_date`, `local_time` の計算・保存処理削除
  - カラム名を `prompt` に変更

- **ドキュメント更新**:
  - `/api/aggregator/README.md` 全面更新
  - 本番環境情報、データフロー、トラブルシューティング追加

---

### 2025-11-13 午後 - Japanese Output + Behavior Field 🎉

**目的**: ダッシュボード表示用に日本語出力とbehaviorフィールドを追加

**変更内容**:

1. **データベース修正**
   - `spot_results` テーブルに `summary` (TEXT), `behavior` (TEXT) カラム追加
   - Supabaseダッシュボードで手動実行

2. **Aggregator API修正** (`/api/aggregator`)
   - プロンプトに `behavior` フィールド追加（3つの行動パターン、カンマ区切り）
   - 全テキスト出力を日本語化（summary, mood_description, behavior_pattern等）
   - 会話検出時は必ず「会話」を含めるよう明示
   - プロンプト自体は英語（LLM効率のため）

3. **Profiler API修正** (`/api/profiler`)
   - LLMレスポンスから `summary` と `behavior` を抽出
   - データベース保存時に2つのカラムに保存
   - `profile_result` (JSONB) にも完全なデータを保存

4. **デプロイ・動作確認**
   - 両API本番環境にデプロイ完了
   - 実データでテスト成功
   - 出力例:
     - summary: "幼稚園の年長さんが食べ物や遊びについて自分で話している様子です。"
     - behavior: "会話, 食事, 遊び"
     - vibe_score: 35

5. **ドキュメント更新**
   - `/api/aggregator/README.md` に変更履歴追加
   - `/api/profiler/README.md` にv1.1.0 Changelog追加
   - 両READMEのスキーマ情報更新

**効果**:
- iOSアプリ・Webダッシュボードで直接日本語表示可能
- 行動パターンの視覚化が容易
- ユーザーフレンドリーな説明

**進捗更新**:
- Phase 1-3: 完了（85%）✅
- Phase 4-1: 完了（Spot Profiler + 日本語出力）✅ **95%達成**
- Phase 4-2以降: Daily/Weekly/Monthly Profiler未実装（残り3%）🚧
- Phase 5: クライアント側表示未着手（残り2%）⏳

---

### 2025-11-13 午前 - Phase 4-1 完了: Profiler API本番稼働開始 🎉

**Profiler API (Spot Profiler) デプロイ完了**:
- ✅ `/spot-profiler` エンドポイント本番稼働開始
- ✅ 入力: `spot_aggregators.prompt` (Timeline-Synchronized Format)
- ✅ 出力: `spot_results` テーブル（スキーマ確定）
- ✅ LLM: Groq OpenAI GPT-OSS-120B (reasoning model, medium effort)
- ✅ CI/CD自動デプロイパイプライン構築完了
- ✅ 本番環境での動作確認・DB保存成功

**インフラ**:
- Container: `profiler-api` (port 8051)
- External URL: `https://api.hey-watch.me/profiler/`
- ECR: `watchme-profiler`
- systemd: `profiler-api.service`

**データベース最終調整**:
- 旧カラム削除: `local_date`, `local_time`, `behavior_score`, `emotion_score`, `composite_score`
- カラム名統一: `profiled_at` → `created_at`
- RLS無効化（内部API専用）

---

### 2025-11-12 午前セッション - 3レイヤー設計の明確化 🎉

- **重要な設計思想の再確認**:
  - 3レイヤーアーキテクチャ: Feature Extraction → Aggregation → **Profiler**
  - Profiler APIが未作成であることを確認
  - 既存Scorer APIは旧アーキテクチャのまま（Profiler APIに移行が必要）

- **ドキュメント全面リニューアル**:
  - ファイル名変更: `SPOT_RECORDING_MIGRATION_GUIDE.md` → `ARCHITECTURE_AND_MIGRATION_GUIDE.md`
  - 3レイヤー設計思想の詳細説明を追加
  - Profiler API（4エンドポイント）の設計仕様を明記
  - summary_weekly, summary_monthly テーブルスキーマを追加
  - 残タスクを再整理（Profiler API新規作成が最優先）

- **進捗の再評価**:
  - Phase 1-3: 完了（80%）✅
  - Phase 4: 進行中（残り20%）🚧
    - Profiler API新規作成（未着手）
    - 4エンドポイント実装（2つは移植、2つは新規）
  - Phase 5: 未着手⏳

---

### 2025-11-12 13:00-13:50 - Phase 2-3 完了 🎉

- Emotion Feature Extractor v2修正完了
- Vibe Transcriber修正完了（バグ修正2回）
- Aggregator API修正完了（ASR+SED+SER統合）

---

### 2025-11-12 00:00-01:00 - Phase 2 進行中

- Vibe Aggregator API修正完了: devices.timezone対応 + UTC→ローカル時間変換
- Behavior Features動作確認: spot_featuresへのデータ保存成功 🎉
- データベース修正: spot_featuresテーブルに不足カラム追加 + RLS無効化

---

### 2025-11-11 最終セッション - Phase 1 完了

- Vault API: `local_datetime` 削除 + S3パス秒単位精度化（`{HH-MM-SS}` 形式）
- Vibe Transcriber, Behavior Features, Emotion Features: `spot_features` 移行完了
- S3パス構造を30分ブロックから秒単位精度に変更（上書き問題を解決）

---

### 2025-11-11 22:30 - UTC統一アーキテクチャへの方針転換

- `local_datetime` 廃止、UTC統一アーキテクチャに移行
- データベース修正: `local_datetime` カラム削除
- iOSアプリ修正: UTC送信に変更

---

## 📚 関連ドキュメント

- [システム全体構成](./README.md)
- [処理フロー詳細](./PROCESSING_ARCHITECTURE.md)
- [技術仕様](./TECHNICAL_REFERENCE.md)
- [運用ガイド](./OPERATIONS_GUIDE.md)

---

**このドキュメントは、WatchMeプロジェクトの包括的なアーキテクチャ・移行ガイドです。**
