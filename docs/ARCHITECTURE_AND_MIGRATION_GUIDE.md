# 🏗️ WatchMe アーキテクチャ・移行ガイド

**プロジェクト**: 心理・感情モニタリングプラットフォーム
**作成日**: 2025-11-11
**最終更新**: 2025-11-14
**ステータス**: ✅ Phase 3完了（85%） / ✅ Phase 4-1完了（Spot Profiler + 日本語出力）（95%） / ✅ Lambda パイプライン再接続完了（98%）
**重要決定**: ❌ Step Functions導入却下（SQS + Lambda アーキテクチャで実装）

---

## 📖 目次

1. [⚠️ 重要：データフローの理解](#重要データフローの理解)
2. [システムアーキテクチャ概要](#システムアーキテクチャ概要)
3. [3レイヤー設計思想](#3レイヤー設計思想)
4. [データフロー全体像](#データフロー全体像)
5. [データベーススキーマ](#データベーススキーマ)
6. [進捗状況](#進捗状況)
7. [次のタスク](#次のタスク)
8. [❌ Step Functions 却下理由](#step-functions-却下理由)
9. [変更履歴](#変更履歴)

---

## ⚠️ 重要：データフローの理解

### 最も重要な原則

**必ず理解すべきこと**: `*_aggregators` テーブルと `*_results` テーブルの関係

```
┌─────────────────────────────────────────────────────────────────────┐
│ 【Layer 2: Aggregation】 プロンプト生成・保存                           │
│                                                                       │
│ spot_aggregators                                                      │
│  ├─ 入力: spot_features (ASR + SED + SER)                            │
│  └─ 出力: prompt (LLM分析用プロンプト) ← ここに保存                     │
│                                                                       │
│ daily_aggregators                                                     │
│  ├─ 入力: spot_results (1日分の複数レコード)                          │
│  └─ 出力: prompt (LLM分析用プロンプト) ← ここに保存                     │
│                                                                       │
│ weekly_aggregators                                                    │
│  ├─ 入力: daily_results (7日分)                                       │
│  └─ 出力: prompt (LLM分析用プロンプト) ← ここに保存                     │
│                                                                       │
│ monthly_aggregators                                                   │
│  ├─ 入力: daily_results (30日分)                                      │
│  └─ 出力: prompt (LLM分析用プロンプト) ← ここに保存                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ LLM分析
┌─────────────────────────────────────────────────────────────────────┐
│ 【Layer 3: Profiling】 LLM分析結果保存                                 │
│                                                                       │
│ spot_results                                                          │
│  ├─ 入力: spot_aggregators.prompt                                    │
│  └─ 出力: LLM分析結果 (vibe_score, summary, behavior等) ← ここに保存   │
│                                                                       │
│ daily_results                                                         │
│  ├─ 入力: daily_aggregators.prompt                                   │
│  └─ 出力: LLM分析結果 (1日の総合評価) ← ここに保存                      │
│                                                                       │
│ weekly_results                                                        │
│  ├─ 入力: weekly_aggregators.prompt                                  │
│  └─ 出力: LLM分析結果 (1週間の総合評価) ← ここに保存                    │
│                                                                       │
│ monthly_results                                                       │
│  ├─ 入力: monthly_aggregators.prompt                                 │
│  └─ 出力: LLM分析結果 (1ヶ月の総合評価) ← ここに保存                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 具体例：Daily（日次）の場合

#### ❌ 間違った理解

```
daily_aggregators (prompt生成)
    ↓
daily_results (LLM分析結果)
    ↓ どこから入力？？？
```

**問題点**: daily_aggregatorsのプロンプトを生成する「入力元」が不明確

---

#### ✅ 正しい理解

```
【前提】spot_results には1日に複数のレコードが存在
例：2025-11-13のspot_results
  - 06:16:34 → vibe_score: -24
  - 06:21:34 → vibe_score: 12
  - 08:30:00 → vibe_score: 35
  ... (その日に録音した分だけ存在)

      ↓ これらを集約してプロンプト生成

daily_aggregators (2025-11-13)
  - prompt: "以下は2025-11-13の3回のスポット録音結果です。
             1回目(06:16): 午後の教室で作業、やや苛立ち (vibe: -24)
             2回目(06:21): フィールド録音中、中立的 (vibe: 12)
             3回目(08:30): 会話、喜び (vibe: 35)
             → 1日の総合的な心理状態を分析してください"

      ↓ このプロンプトをLLMで分析

daily_results (2025-11-13)
  - vibe_score: 10 (1日の平均)
  - summary: "午後は作業で苛立ちがあったが、その後回復。全体的に安定"
  - profile_result: { ... 詳細なJSON ... }
```

### レコード数の関係

| テーブル | 1日あたりのレコード数 | 説明 |
|---------|-------------------|------|
| **spot_results** | **複数** (10件、20件...) | その日に録音した回数分 |
| **daily_aggregators** | **1件** | spot_resultsを集約した1つのプロンプト |
| **daily_results** | **1件** | daily_aggregatorsを分析した1つの結果 |

### 時間軸での理解

```
2025-11-13 の例：

06:16 ─┐
06:21  ├─ spot_results (3件)
08:30 ─┘
         ↓ 集約
       daily_aggregators (1件: 2025-11-13)
         ↓ LLM分析
       daily_results (1件: 2025-11-13)
```

### Weekly/Monthly も同じパターン

```
【Weekly】
daily_results (7日分: 11/11, 11/12, ..., 11/17)
    ↓ 集約
weekly_aggregators (1件: week_start_date=2025-11-11)
    ↓ LLM分析
weekly_results (1件: week_start_date=2025-11-11)

【Monthly】
daily_results (30日分: 11/1〜11/30)
    ↓ 集約
monthly_aggregators (1件: year=2025, month=11)
    ↓ LLM分析
monthly_results (1件: year=2025, month=11)
```

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

### 🤖 自動実行フロー（現在稼働中）

#### Phase 1: 録音 → S3保存 ✅ 自動化済み

```
iOS/Observer Device
  ↓ 音声録音（任意の長さ）
S3 Bucket (watchme-vault)
  ↓ S3イベントトリガー ← ✅ 自動化
Lambda (audio-processor)
  ↓ SQSキュー
Lambda (audio-worker)
  ↓ HTTPリクエスト
Vault API
  ↓ INSERT
audio_files (recorded_at: UTC)

⏱️ 処理時間: 即座
```

---

#### Phase 2: 特徴抽出（並列実行）✅ 自動化済み

```
Lambda (audio-worker) → 3つのAPIを並列実行 ← ✅ 自動化

┌─ Vibe Transcriber (ASR)
│    └─ 出力: spot_features.vibe_transcriber_result
│
├─ Behavior Features (SED)
│    └─ 出力: spot_features.behavior_extractor_result
│
└─ Emotion Features (SER)
     └─ 出力: spot_features.emotion_extractor_result

⏱️ 処理時間: 約5-10秒（並列処理）
✅ トリガー: S3アップロード完了後、Lambda (audio-worker) が自動実行
```

---

#### Phase 3: 統合・プロンプト生成 🚧 実装予定

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
🚧 トリガー設計: Phase 2完了後、Lambda (audio-worker) が自動呼び出し（実装予定）
```

---

#### Phase 4-1: スポット分析（LLM）🚧 実装予定

```
Profiler API - Spot Profiler (/profiler/spot-profiler)

1. spot_aggregators.prompt 取得
2. Groq LLM実行（openai/gpt-oss-120b）
3. spot_results に保存
   - summary (日本語)
   - vibe_score (-100 to +100)
   - behavior (主要行動パターン3つ)
   - profile_result (詳細JSONB)

⏱️ 処理時間: 約3-5秒
🚧 トリガー設計: Phase 3完了後、Lambda (audio-worker) が自動呼び出し（実装予定）
```

---

#### Phase 4-2: 日次累積分析（リアルタイム更新）🚧 実装予定

```
【トリガー】spot_results への新規レコード追加
    ↓
Aggregator API - Daily Aggregator (/aggregator/daily)
1. spot_results（その日の全レコード）取得
   例: 06:16, 06:21, 08:30, 10:15, ... (録音した回数分)
2. 1日分の統合プロンプト生成
3. daily_aggregators に保存（UPSERT）
    ↓
Profiler API - Daily Profiler (/profiler/daily-profiler)
1. daily_aggregators.prompt 取得
2. Groq LLM実行
3. daily_results に保存（UPSERT）
   - その日の最新サマリー
   - 録音が増えるたびに更新

⏱️ 処理時間: 約7-12秒
🚧 トリガー設計: Phase 4-1 (spot-profiler) 完了後に自動実行（実装予定）
📝 重要: 録音のたびにdaily_resultsが更新され、常に最新状態を保つ
```

**リアルタイム更新の例**:
```
06:16 録音 → spot_results(1件) → daily_results更新（1件のデータで分析）
06:21 録音 → spot_results(2件) → daily_results更新（2件のデータで再分析）
08:30 録音 → spot_results(3件) → daily_results更新（3件のデータで再分析）
...
その日の最終録音 → daily_results最終更新
```

---

### 🕐 定期実行フロー（バッチ処理）

#### Phase 4-3: 週次分析（定期バッチ）🚧 実装予定

```
【トリガー】毎週月曜日 00:00 (UTC) - CloudWatch Events / EventBridge
    ↓
Aggregator API - Weekly Aggregator (/aggregator/weekly)
1. daily_results（過去7日分）取得
2. 週次統合プロンプト生成
3. weekly_aggregators に保存
    ↓
Profiler API - Weekly Profiler (/profiler/weekly-profiler)
1. weekly_aggregators.prompt 取得
2. Groq LLM実行
3. weekly_results に保存

⏱️ 処理時間: 約12-20秒
🕐 実行頻度: 週1回（毎週月曜日）
```

---

#### Phase 4-4: 月次分析（定期バッチ）🚧 実装予定

```
【トリガー】毎月1日 00:00 (UTC) - CloudWatch Events / EventBridge
    ↓
Aggregator API - Monthly Aggregator (/aggregator/monthly)
1. daily_results（過去30日分）取得
2. 月次統合プロンプト生成
3. monthly_aggregators に保存
    ↓
Profiler API - Monthly Profiler (/profiler/monthly-profiler)
1. monthly_aggregators.prompt 取得
2. Groq LLM実行
3. monthly_results に保存

⏱️ 処理時間: 約20-30秒
🕐 実行頻度: 月1回（毎月1日）
```

---

### Phase 5: 表示（iOS/Web）

```
iOS/Web Dashboard

1. 各resultsテーブルからデータ取得
   - spot_results: スポット分析結果（リアルタイム）
   - daily_results: 日次分析結果（リアルタイム更新）
   - weekly_results: 週次分析結果（週1回更新）
   - monthly_results: 月次分析結果（月1回更新）

2. devices.timezone 取得

3. UTC → ローカル時間に変換

4. UI表示
   - タイムライン表示（spot_results）
   - 今日のサマリー（daily_results - リアルタイム）
   - 今週のトレンド（weekly_results）
   - 今月の長期トレンド（monthly_results）
```

---

### 📋 トリガー設計まとめ

| Phase | トリガー方式 | 実行タイミング | ステータス |
|-------|------------|--------------|----------|
| Phase 1-2 | S3イベント → Lambda | 録音直後 | ✅ 稼働中 |
| Phase 3 | Lambda (audio-worker) 呼び出し | Phase 2完了後 | 🚧 実装予定 |
| Phase 4-1 (Spot) | Lambda (audio-worker) 呼び出し | Phase 3完了後 | 🚧 実装予定 |
| Phase 4-2 (Daily) | Lambda (audio-worker) 呼び出し | Phase 4-1完了後 | 🚧 実装予定 |
| Phase 4-3 (Weekly) | CloudWatch Events | 毎週月曜日 00:00 UTC | 🚧 実装予定 |
| Phase 4-4 (Monthly) | CloudWatch Events | 毎月1日 00:00 UTC | 🚧 実装予定 |

**重要な設計思想**:
- **リアルタイム**: spot_results と daily_results は録音のたびに自動更新
- **バッチ処理**: weekly_results と monthly_results は定期実行

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

### 5. daily_aggregators - 日次統合プロンプト 🆕

```sql
CREATE TABLE daily_aggregators (
  device_id TEXT NOT NULL,
  date DATE NOT NULL,                -- Local date (based on device timezone)
  prompt TEXT NOT NULL,               -- LLM analysis prompt (aggregated from spot_results)
  context_data JSONB,                 -- Metadata (timezone, spot_count, etc.)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, date)
);
```

**役割**: Layer 2（統合層 - Daily）のプロンプト生成・保存

**⚠️ 重要**:
- **入力元**: `spot_results` (1日分の複数レコード)
- **出力先**: このテーブルの`prompt`を`daily_results`のLLM分析で使用
- **データ構造**: 1日1レコード

**RLS**: 無効（内部API専用テーブル）

---

### 6. daily_results - 日次分析結果（旧 summary_daily）

```sql
CREATE TABLE daily_results (
  device_id TEXT NOT NULL,
  date DATE NOT NULL,

  -- 既存カラム（旧 summary_daily から継承）
  status TEXT NOT NULL,
  prompt JSONB,
  prompt_generated_at TIMESTAMPTZ,
  overall_summary TEXT,
  average_vibe REAL,
  vibe_scores JSONB,
  hourly_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  burst_events JSONB,
  processed_count INTEGER,
  last_time_block TEXT,
  last_updated_at TIMESTAMPTZ,
  error_message TEXT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,

  -- 新規カラム（2025-11-13追加）
  summary TEXT,                       -- Dashboard display summary (Japanese)
  behavior TEXT,                      -- Key behavior patterns (comma-separated)
  llm_model TEXT,                     -- LLM model used

  PRIMARY KEY (device_id, date)
);
```

**役割**: Layer 3（Profiler - Daily）の出力データ保存

**⚠️ 重要**:
- **入力元**: `daily_aggregators.prompt`
- **データ構造**: 1日1レコード（spot_resultsは1日に複数レコード）

---

### 7. weekly_aggregators - 週次統合プロンプト 🆕

```sql
CREATE TABLE weekly_aggregators (
  device_id TEXT NOT NULL,
  week_start_date DATE NOT NULL,      -- Week start (Monday, local date)
  week_end_date DATE NOT NULL,        -- Week end (Sunday, local date)
  prompt TEXT NOT NULL,               -- LLM analysis prompt (aggregated from daily_results)
  context_data JSONB,                 -- Metadata (timezone, active_days, etc.)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, week_start_date)
);
```

**役割**: Layer 2（統合層 - Weekly）のプロンプト生成・保存

**⚠️ 重要**:
- **入力元**: `daily_results` (7日分)
- **出力先**: このテーブルの`prompt`を`weekly_results`のLLM分析で使用

**RLS**: 無効（内部API専用テーブル）

---

### 8. weekly_results - 週次分析結果（旧 summary_weekly）

```sql
CREATE TABLE weekly_results (
  device_id TEXT NOT NULL,
  week_start_date DATE NOT NULL,
  week_end_date DATE NOT NULL,

  -- 既存カラム（旧 summary_weekly から継承）
  status TEXT NOT NULL,
  prompt JSONB,
  prompt_generated_at TIMESTAMPTZ,
  overall_summary TEXT,
  average_vibe REAL,
  daily_scores JSONB,
  daily_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  weekly_highlights JSONB,
  days_processed INTEGER,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,

  -- 新規カラム（2025-11-13追加）
  summary TEXT,
  behavior TEXT,
  llm_model TEXT,

  PRIMARY KEY (device_id, week_start_date)
);
```

**役割**: Layer 3（Profiler - Weekly）の出力データ保存

**⚠️ 重要**:
- **入力元**: `weekly_aggregators.prompt`

---

### 9. monthly_aggregators - 月次統合プロンプト 🆕

```sql
CREATE TABLE monthly_aggregators (
  device_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,             -- 1-12
  prompt TEXT NOT NULL,               -- LLM analysis prompt (aggregated from daily_results)
  context_data JSONB,                 -- Metadata (timezone, active_days, etc.)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (device_id, year, month)
);
```

**役割**: Layer 2（統合層 - Monthly）のプロンプト生成・保存

**⚠️ 重要**:
- **入力元**: `daily_results` (30日分)
- **出力先**: このテーブルの`prompt`を`monthly_results`のLLM分析で使用

**RLS**: 無効（内部API専用テーブル）

---

### 10. monthly_results - 月次分析結果（旧 summary_monthly）

```sql
CREATE TABLE monthly_results (
  device_id TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,

  -- 既存カラム（旧 summary_monthly から継承）
  status TEXT NOT NULL,
  prompt JSONB,
  prompt_generated_at TIMESTAMPTZ,
  overall_summary TEXT,
  average_vibe REAL,
  weekly_scores JSONB,
  weekly_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,
  monthly_highlights JSONB,
  weeks_processed INTEGER,
  days_processed INTEGER,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,

  -- 新規カラム（2025-11-13追加）
  summary TEXT,
  behavior TEXT,
  llm_model TEXT,

  PRIMARY KEY (device_id, year, month)
);
```

**役割**: Layer 3（Profiler - Monthly）の出力データ保存

**⚠️ 重要**:
- **入力元**: `monthly_aggregators.prompt`

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

### ✅ Task 1: Lambda パイプライン再接続（完了 - 2025-11-14）

**ステータス**: ✅ 完了

#### 実施内容:
1. **Lambda関数の修正**
   - `watchme-audio-processor`: `audio_files`テーブルから`recorded_at`を取得してSQSメッセージに含める ✅
   - `watchme-audio-worker`: 新しいパイプライン実装 ✅
     - 特徴抽出 (ASR, SED, SER)
     - Aggregator API (`/aggregator/spot`)
     - Profiler API (`/spot-profiler`)

2. **Behavior Features API修正**
   - `time_block`依存を削除 ✅
   - `recorded_at`ベースのアーキテクチャに対応 ✅

3. **デプロイ結果**
   - 両Lambda関数のデプロイ成功 ✅
   - Behavior Features API再デプロイ成功 ✅
   - EC2ディスク容量問題解決（95%→85%） ✅

---

### 🔴 Task 2: Daily Profiler実装（次の優先事項）

**期間**: 3時間
**ステータス**: 🚧 実装待ち
- profiler-worker ← profiler-queue

#### 1-4. 監視・アラート設定（30分）
- CloudWatch Alarms（DLQメッセージ監視）
- Lambda エラー率監視

#### 1-5. 動作確認（30分）
- エンドツーエンドテスト
- エラーハンドリング確認

#### Daily Profiler実装内容:
- Aggregator API - Daily Aggregator (`/aggregator/daily`)
- Profiler API - Daily Profiler (`/profiler/daily-profiler`)
- `daily_aggregators`テーブルと`daily_results`テーブルの連携

**詳細設計**: このドキュメントの「データフロー全体像」セクション参照

---

### Task 3: 累積分析エンドポイント実装

Phase 4-3以降で実装予定：
- Weekly Profiler: `/weekly-profiler`
- Monthly Profiler: `/monthly-profiler`

---

### Task 4: クライアント側表示実装

各resultsテーブルからデータ取得・表示:
- iOS アプリでの実装
- Web ダッシュボードでの実装（優先度低）

---

## 📝 変更履歴

### 2025-11-14
- ✅ Lambda パイプライン再接続完了
  - `watchme-audio-processor`と`watchme-audio-worker`を`recorded_at`ベースに修正
  - 新しいAggregator (`/aggregator/spot`) とProfiler (`/spot-profiler`) を接続
  - Behavior Features APIの`time_block`依存を削除
  - EC2ディスク容量問題を解決（Docker pruneで2.7GB削減）

### 2025-11-13
- ✅ Profiler API本番稼働開始
- ✅ Spot Profiler実装完了
- ✅ 日本語出力対応完了
- ❌ Step Functions導入却下、SQS + Lambda アーキテクチャ採用決定

### 2025-11-12
- ✅ Phase 3完了：Aggregator API実装
- ✅ Timeline-Synchronized Format実装

### 2025-11-11
- プロジェクト開始
- UTC統一アーキテクチャ設計
- 3レイヤー設計思想の策定

---

## ❌ Step Functions 却下理由

**検討日**: 2025-11-13
**決定**: Step Functions 導入を却下し、SQS + Lambda アーキテクチャで実装

### 却下の背景

当初、ワークフローの可視化・デバッグ効率化を目的に Step Functions の導入を検討しました。しかし、詳細な分析の結果、**プロダクトとしてスケールする際の致命的な問題**が判明したため、却下しました。

---

### 🔥 致命的な問題点

#### 1. **コスト爆発（スケール時）**

WatchMeは **高頻度デバイス処理システム** です。100台、500台、1000台と増えることを前提に設計する必要があります。

| デバイス数 | 録音回数/日 | 月間workflow数 | 遷移数/workflow | 月間遷移数 | Step Functions コスト | SQS + Lambda コスト | **年間削減額** |
|----------|------------|--------------|---------------|-----------|---------------------|-------------------|-------------|
| 100台 | 48回 | 144,000 | 15 | 2,160,000 | **$54/月** | $5/月 | **$588** |
| 300台 | 48回 | 432,000 | 20 | 8,640,000 | **$216/月** | $8/月 | **$2,496** |
| 500台 | 48回 | 720,000 | 20 | 14,400,000 | **$360/月** | $10/月 | **$4,200** |
| 1000台 | 48回 | 1,440,000 | 20 | 28,800,000 | **$720/月** | $15/月 | **$8,460** |

**Step Functions の料金**: $0.025 / 1,000 transitions

**重要な注意点**:
- 遷移数は「表に見える数」の2〜5倍になる（Retry、Catch、Parallel の内部遷移も課金対象）
- Parallel state は「3つの小さなステートマシン」として動作 → 遷移数が3〜5倍に跳ねる
- エラーリトライが発生するたびに遷移数が積み上がる

---

#### 2. **AWS自身が「高頻度イベント処理に非推奨」と明記**

AWS公式ドキュメントより:

> **Step Functions Standard is not recommended for high-volume event processing.**
>
> For IoT, sensor data, and device event processing, use **SQS + Lambda** or **EventBridge**.

WatchMeは明らかに「IoT/デバイス/センサー系」に分類されます。

**Step Functions の設計思想**:
- ✅ 低頻度・高信頼性の業務プロセス向け
  - ユーザー登録の承認フロー
  - 1日1〜2回のデータ集計
  - エンタープライズの社内承認プロセス
  - バッチETL

- ❌ 高頻度イベント処理には不向き
  - IoT デバイス
  - センサーデータ
  - 音声ログ
  - 30分ごとの自動録音

---

#### 3. **アーキテクチャの柔軟性が失われる**

Step Functions を導入すると、**ワークフローが「ステートマシン」に縛られる**:

- ❌ API順番の入れ替えが困難（ステートマシン定義の大規模変更が必要）
- ❌ 新しい分析層の追加が制限される
- ❌ 並列処理の変更（Parallel → Sequential 等）が複雑
- ❌ YAML/JSON の巨大なステートマシンが生成され、バージョニング・デプロイに影響

WatchMeのような **動くAPI前提のシステム** では、この硬直性が致命的です。

---

#### 4. **スケール時の制御が難しい**

Step Functions は突然の大量実行に弱い:

- ❌ `Execution limit exceeded` エラーが発生
- ❌ 一度に大量の workflow を起動すると throttling
- ❌ 実行中ワークフローが積み上がるとタイムアウトしやすい

対して、**SQS + Lambda** は:

- ✅ Lambda 同時実行数でスロットル調整
- ✅ SQS の visibility timeout で自然再試行
- ✅ 自動スケーリング
- ✅ デッドレターキュー（DLQ）で失敗メッセージを自動隔離

---

### ✅ 採用するアーキテクチャ：SQS + Lambda

**設計方針**:
```
S3 Upload
  ↓
Lambda (audio-processor)
  ↓ SQS (feature-extraction-queue) ← 既存
Lambda (audio-worker)
  ↓ 並列実行: ASR + SED + SER
  ↓ 完了後
  ↓ SQS (aggregation-queue) ← NEW
Lambda (aggregation-worker) ← NEW
  ↓ Aggregator API呼び出し
  ↓ SQS (profiler-queue) ← NEW
Lambda (profiler-worker) ← NEW
  ↓ Spot Profiler API呼び出し
  ↓ Daily Profiler API呼び出し（条件付き）
  ↓ 完了
```

**メリット**:
- ✅ **コスト**: 1000台でも月$15（Step Functionsの $720 に対して **48倍安い**）
- ✅ **スケーラビリティ**: デバイス数が増えても線形コスト
- ✅ **柔軟性**: API順番の変更、新規API追加が容易
- ✅ **エラーハンドリング**: DLQで失敗メッセージを自動隔離
- ✅ **AWS推奨**: 高頻度イベント処理に最適

**デメリット**:
- ⚠️ 可視化が Step Functions より劣る
  - 対策: CloudWatch Logs Insights でフロー追跡
  - 対策: X-Ray でトレーシング（必要に応じて）

---

### 📊 コスト比較（最終版）

| 項目 | Step Functions | SQS + Lambda | 削減率 |
|-----|---------------|-------------|-------|
| 100台 | $54/月 | $5/月 | **91%** |
| 300台 | $216/月 | $8/月 | **96%** |
| 500台 | $360/月 | $10/月 | **97%** |
| 1000台 | $720/月 | $15/月 | **98%** |

**1000台での年間削減額**: **$8,460**

---

### 📝 検討プロセスの教訓

1. **「現在1台だから安い」という議論は無意味**
   - プロダクトは常にスケールを前提に設計すべき
   - 初期コストではなく、**100台、500台、1000台での運用コスト**を評価

2. **AWS公式ドキュメントの「推奨・非推奨」は重要**
   - Step Functions の「高頻度イベント処理に非推奨」は見逃せない

3. **遷移数の誤算は致命的**
   - 表面的な遷移数（8個）ではなく、**Parallel、Retry、Catch を含めた実際の遷移数（20〜30個）**を計算すべき

4. **検討した上での却下は前進**
   - 検討せずに実装するより、検討した上で却下する方が価値が高い
   - この判断により、将来の大規模な手戻りを回避

---

## 🔍 trace_id ベース可視化戦略

**検討日**: 2025-11-13
**決定**: Step Functions を使わずに、trace_id + Supabase `pipeline_status` テーブルで運用性を最大化

### 基本方針

```python
trace_id = f"{device_id}_{recorded_at}"
# 例: "9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93_2025-11-13T06:16:34+00:00"
```

この**ユニークなID**を全てのLambda・API・データベースで共有し、パイプライン全体を追跡可能にします。

---

### 🎯 実現できること

| 項目 | Step Functions | trace_id + Supabase | 優位性 |
|-----|---------------|---------------------|-------|
| **コスト（1000台）** | $720/月 | **$0** | **無限大** |
| **可視化** | AWS Console | **Supabaseダッシュボード（リアルタイム）** | ✅ |
| **デバッグ** | 実行履歴を手動で確認 | **trace_id で即座検索** | ✅ |
| **柔軟性** | ステートマシン変更が必要 | **Lambda・API追加が容易** | ✅ |
| **スケール** | Execution limit | **無制限** | ✅ |

#### ✅ 5つの効果

1. **どこで止まっているか完全にわかる**
   - `pipeline_status` テーブルを見れば一目瞭然
   - リアルタイム更新（Supabase Realtime）

2. **デバッグ・障害調査時間が 1/10**
   - trace_id で CloudWatch Logs Insights 検索
   - エラー発生箇所を即座特定

3. **Step Functions よりシンプル**
   - ステートマシン定義不要
   - Lambda関数だけで完結

4. **コストほぼ0円**
   - Supabase: 無料枠内（pipeline_status は軽量）
   - CloudWatch Logs: 標準料金のみ

5. **将来 Weekly/Monthly 追加も簡単**
   - `pipeline_status` に新しいカラムを追加するだけ
   - Lambda関数は同じパターンで実装

---

### 📋 実装タスク（5つ）

#### Task 1: trace_id の一本化

全Lambda関数・APIで同じ trace_id を使用。

**Lambda: audio-worker（拡張）**:
```python
# trace_id 生成
trace_id = f"{device_id}_{recorded_at}"

# 構造化ログ
logger.info(json.dumps({
    "trace_id": trace_id,
    "phase": "feature_extraction",
    "status": "started"
}))
```

**SQSメッセージに trace_id を含める**:
```python
sqs.send_message(
    QueueUrl=os.environ['AGGREGATION_QUEUE_URL'],
    MessageBody=json.dumps({
        'device_id': device_id,
        'recorded_at': recorded_at,
        'trace_id': trace_id  # ← 追加
    })
)
```

---

#### Task 2: Supabase `pipeline_status` テーブル ✅ 完了

**ステータス**: ✅ 2025-11-13 作成完了

テーブル構造:
```sql
CREATE TABLE pipeline_status (
  trace_id TEXT PRIMARY KEY,
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,

  -- フェーズごとのステータス
  feature_extraction_status TEXT DEFAULT 'pending',
  feature_extraction_started_at TIMESTAMPTZ,
  feature_extraction_completed_at TIMESTAMPTZ,

  aggregation_status TEXT DEFAULT 'pending',
  aggregation_started_at TIMESTAMPTZ,
  aggregation_completed_at TIMESTAMPTZ,

  profiling_status TEXT DEFAULT 'pending',
  profiling_started_at TIMESTAMPTZ,
  profiling_completed_at TIMESTAMPTZ,

  daily_profiling_status TEXT DEFAULT 'pending',
  daily_profiling_started_at TIMESTAMPTZ,
  daily_profiling_completed_at TIMESTAMPTZ,

  -- エラー情報
  error_phase TEXT,
  error_message TEXT,
  error_occurred_at TIMESTAMPTZ,

  -- メタ情報
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**マイグレーション**: `/supabase/migrations/20251113100000_create_pipeline_status_table.sql`

---

#### Task 3: 全Lambda・APIから status を PATCH

**共通関数**（全Lambda関数に実装）:
```python
import requests
import os
from datetime import datetime, timezone

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_SERVICE_ROLE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']

def update_pipeline_status(trace_id, device_id, recorded_at, phase, status, error_message=None):
    """Update pipeline_status table via Supabase REST API"""
    headers = {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
    }

    payload = {
        'trace_id': trace_id,
        'device_id': device_id,
        'recorded_at': recorded_at,
        f'{phase}_status': status,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }

    # Add timestamp for status change
    if status == 'started':
        payload[f'{phase}_started_at'] = datetime.now(timezone.utc).isoformat()
    elif status == 'completed':
        payload[f'{phase}_completed_at'] = datetime.now(timezone.utc).isoformat()
    elif status == 'failed':
        payload['error_phase'] = phase
        payload['error_message'] = error_message
        payload['error_occurred_at'] = datetime.now(timezone.utc).isoformat()

    # UPSERT (trace_id がなければ作成、あれば更新)
    response = requests.post(
        f'{SUPABASE_URL}/rest/v1/pipeline_status',
        json=payload,
        headers=headers,
        params={'on_conflict': 'trace_id'}
    )

    if response.status_code not in [200, 201]:
        logger.error(f"Failed to update pipeline_status: {response.text}")
```

**Lambda関数での使用例**:
```python
def lambda_handler(event, context):
    for record in event['Records']:
        body = json.loads(record['body'])
        trace_id = body['trace_id']
        device_id = body['device_id']
        recorded_at = body['recorded_at']

        try:
            # 開始
            update_pipeline_status(trace_id, device_id, recorded_at, 'aggregation', 'started')

            # API呼び出し
            response = requests.post(API_URL, ...)

            # 完了
            update_pipeline_status(trace_id, device_id, recorded_at, 'aggregation', 'completed')

        except Exception as e:
            # エラー
            update_pipeline_status(trace_id, device_id, recorded_at, 'aggregation', 'failed', str(e))
            raise
```

---

#### Task 4: CloudWatch Logs Insights で trace_id 検索

**構造化ログの出力**:
```python
logger.info(json.dumps({
    "trace_id": trace_id,
    "phase": "aggregation",
    "status": "completed",
    "duration_ms": 1234,
    "device_id": device_id,
    "recorded_at": recorded_at
}))
```

**CloudWatch Logs Insights クエリ例**:

```sql
-- 特定の trace_id の全ログを取得
fields @timestamp, @message
| filter @message like /9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93_2025-11-13T06:16:34/
| sort @timestamp asc

-- 失敗したパイプラインを検索
fields @timestamp, trace_id, phase, status, error_message
| parse @message /"trace_id":"(?<trace_id>[^"]+)"/
| parse @message /"phase":"(?<phase>[^"]+)"/
| parse @message /"status":"(?<status>[^"]+)"/
| filter status = "failed"
| sort @timestamp desc
| limit 100

-- 処理時間の分析（各フェーズ）
fields @timestamp, trace_id, phase, duration_ms
| parse @message /"trace_id":"(?<trace_id>[^"]+)"/
| parse @message /"phase":"(?<phase>[^"]+)"/
| parse @message /"duration_ms":(?<duration_ms>[0-9]+)/
| stats avg(duration_ms) as avg_duration by phase
```

---

#### Task 5: Supabase リアルタイム可視化ダッシュボード

**管理ツール（Admin）に追加**: `/Users/kaya.matsumoto/projects/watchme/admin/pipeline_monitor.html`

**機能**:
- リアルタイム更新（Supabase Realtime）
- device_id でフィルタリング
- ステータス別カラーコーディング
- エラーメッセージ表示

**実装イメージ**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Pipeline Monitor - WatchMe</title>
    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
</head>
<body>
    <h1>Pipeline Status Monitor</h1>
    <div id="pipeline-list"></div>

    <script>
        const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

        // リアルタイム更新
        supabase
            .channel('pipeline-changes')
            .on('postgres_changes',
                { event: '*', schema: 'public', table: 'pipeline_status' },
                (payload) => loadPipelines()
            )
            .subscribe();

        async function loadPipelines() {
            const { data } = await supabase
                .from('pipeline_status')
                .select('*')
                .order('recorded_at', { ascending: false })
                .limit(50);

            displayPipelines(data);
        }
    </script>
</body>
</html>
```

---

### 📊 実装優先度

| タスク | 優先度 | 推定時間 | ステータス |
|-------|-------|---------|----------|
| Task 2: pipeline_status テーブル作成 | 🔴 最優先 | 15分 | ✅ 完了 |
| Task 1: trace_id 一本化 | 🔴 最優先 | 2時間 | 🚧 次セッション |
| Task 3: status PATCH実装 | 🔴 最優先 | 2時間 | 🚧 次セッション |
| Task 4: Logs Insights設定 | 🟡 中 | 30分 | 🚧 次セッション |
| Task 5: ダッシュボード作成 | 🟢 低 | 1時間 | ⏳ 後回し |

**合計推定時間**: 5.5時間（Task 2完了済みのため残り5時間）

---

## 📂 既存Lambda関数の流用方針

**決定日**: 2025-11-13
**方針**: 既存のLambda関数を最大限流用し、既存の場所で拡張・新規作成

### 背景

既に `/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/` に以下のLambda関数が存在：

```
lambda-functions/
├── watchme-audio-processor          # S3イベント → SQS送信
├── watchme-audio-worker             # 特徴抽出（ASR + SED + SER）
├── watchme-dashboard-summary-worker # プロンプト生成（累積分析用）
└── watchme-dashboard-analysis-worker# ChatGPT分析（累積分析用）
```

この場所が最適な理由：
1. ✅ **一元管理**: サーバー設定とインフラコードが1箇所にまとまる
2. ✅ **デプロイスクリプト再利用**: `deploy-dashboard-lambdas.sh`, `create-sqs-queues.sh` が既存
3. ✅ **本番環境との対応が明確**: `production/` = 本番環境専用
4. ✅ **ドキュメントも同じ場所**: `DEPLOYMENT_GUIDE.md` が既にある

---

### 🔄 Lambda関数の流用・新規作成計画

| Lambda関数 | 状態 | 作業内容 | Phase | 推定時間 |
|-----------|------|---------|-------|---------|
| **audio-processor** | ✅ 既存 | 変更なし | Phase 1-2 | - |
| **audio-worker** | 🔧 拡張 | trace_id生成、pipeline_status更新、SQS送信追加 | Phase 1-2 | 30分 |
| **aggregation-worker** | 🆕 新規 | dashboard-summary-worker をテンプレートに作成 | Phase 3 | 1時間 |
| **profiler-worker** | 🆕 新規 | dashboard-analysis-worker をテンプレートに作成 | Phase 4-1 | 1時間 |
| **dashboard-summary-worker** | 📦 保留 | Phase 4-2（Daily Profiler）で使用予定 | Phase 4-2 | - |
| **dashboard-analysis-worker** | 📦 保留 | Phase 4-2（Daily Profiler）で使用予定 | Phase 4-2 | - |

---

### 📋 ディレクトリ構造（最終形）

```
/Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/
├── watchme-audio-processor/          # 既存（変更なし）
│   ├── lambda_function.py
│   ├── requirements.txt
│   └── deploy.sh
│
├── watchme-audio-worker/             # 既存（拡張）
│   ├── lambda_function.py            # trace_id生成、pipeline_status更新、SQS送信追加
│   ├── requirements.txt              # requests追加（Supabase REST API用）
│   └── deploy.sh
│
├── watchme-aggregation-worker/       # 新規作成
│   ├── lambda_function.py            # Aggregator API呼び出し
│   ├── requirements.txt              # requests, boto3
│   ├── deploy.sh
│   └── README.md
│
├── watchme-profiler-worker/          # 新規作成
│   ├── lambda_function.py            # Spot Profiler API呼び出し
│   ├── requirements.txt              # requests, boto3
│   ├── deploy.sh
│   └── README.md
│
├── watchme-dashboard-summary-worker/ # 既存（Phase 4-2で使用）
├── watchme-dashboard-analysis-worker/# 既存（Phase 4-2で使用）
│
├── create-sqs-queues.sh              # 既存（拡張：新規キュー2つ追加）
├── deploy-dashboard-lambdas.sh       # 既存（拡張：新規Lambda追加）
└── DEPLOYMENT_GUIDE.md               # 既存（更新）
```

---

### 🎯 作業フロー

#### Step 1: 既存Lambda確認（10分）
```bash
# audio-worker の現在の実装を確認
cat /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-audio-worker/lambda_function.py

# dashboard-summary-worker をテンプレートとして確認
cat /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-dashboard-summary-worker/lambda_function.py
```

#### Step 2: audio-worker 拡張（30分）
- trace_id生成ロジック追加
- `update_pipeline_status()` 共通関数追加
- 特徴抽出完了後にSQS送信追加
- requirements.txt に `requests` 追加

#### Step 3: 新規Lambda作成（2時間）
- `aggregation-worker/` ディレクトリ作成
- `profiler-worker/` ディレクトリ作成
- 各ディレクトリにファイル作成（lambda_function.py, requirements.txt, deploy.sh, README.md）

#### Step 4: SQSキュー追加（15分）
- `create-sqs-queues.sh` に以下を追加：
  - `watchme-aggregation-queue`
  - `watchme-aggregation-dlq`
  - `watchme-profiler-queue`
  - `watchme-profiler-dlq`

#### Step 5: デプロイスクリプト更新（15分）
- `deploy-dashboard-lambdas.sh` に新規Lambda追加

#### Step 6: 動作確認（30分）
- エンドツーエンドテスト
- trace_id追跡確認
- pipeline_status 更新確認

**合計推定時間**: 3.5時間（5時間から短縮）

---

## 🏗️ SQS + Lambda アーキテクチャ設計

### 全体フロー

```
┌─────────────────────────────────────────────────────────────────┐
│ Phase 1-2: 録音 → 特徴抽出（既存）                                 │
└─────────────────────────────────────────────────────────────────┘
S3 Upload
  ↓ S3 Event
Lambda (audio-processor)
  ↓ SQS (feature-extraction-queue)
Lambda (audio-worker)
  ↓ 並列実行: Vibe Transcriber + Behavior Features + Emotion Features
  ↓ 3つ完了
┌─────────────────────────────────────────────────────────────────┐
│ Phase 3: 統合・プロンプト生成（NEW）                                │
└─────────────────────────────────────────────────────────────────┘
  ↓ SQS (aggregation-queue) ← NEW
Lambda (aggregation-worker) ← NEW
  ↓ POST https://api.hey-watch.me/aggregator/spot
  ↓ spot_aggregators テーブルに保存
┌─────────────────────────────────────────────────────────────────┐
│ Phase 4-1: スポット分析（NEW）                                     │
└─────────────────────────────────────────────────────────────────┘
  ↓ SQS (profiler-queue) ← NEW
Lambda (profiler-worker) ← NEW
  ↓ POST https://api.hey-watch.me/profiler/spot-profiler
  ↓ spot_results テーブルに保存
┌─────────────────────────────────────────────────────────────────┐
│ Phase 4-2: 日次累積分析（NEW - Phase 4-2で実装）                   │
└─────────────────────────────────────────────────────────────────┘
  ↓ 条件付き: その日の最初/追加録音
  ↓ POST https://api.hey-watch.me/aggregator/daily
  ↓ daily_aggregators テーブルに保存（UPSERT）
  ↓ POST https://api.hey-watch.me/profiler/daily-profiler
  ↓ daily_results テーブルに保存（UPSERT）
  ↓ 完了
```

---

### Lambda関数詳細

#### Lambda 1: `audio-worker`（既存・拡張）

**役割**: 3つの特徴抽出API呼び出し完了後、次のキューに送信

**変更点**:
```python
# 既存コード（3つのAPI並列実行）
# ... 省略 ...

# 新規追加：3つのAPI呼び出し完了後
import boto3
import os
import json

sqs = boto3.client('sqs', region_name='ap-southeast-2')

def send_to_aggregation_queue(device_id, recorded_at):
    """Send message to aggregation queue after feature extraction completes"""
    sqs.send_message(
        QueueUrl=os.environ['AGGREGATION_QUEUE_URL'],
        MessageBody=json.dumps({
            'device_id': device_id,
            'recorded_at': recorded_at
        })
    )
```

**環境変数**:
- `AGGREGATION_QUEUE_URL`: `https://sqs.ap-southeast-2.amazonaws.com/.../watchme-aggregation-queue`

**タイムアウト**: 60秒（変更なし）

---

#### Lambda 2: `aggregation-worker`（NEW）

**役割**: Aggregator API呼び出し、プロンプト生成

**コード**: `/Users/kaya.matsumoto/projects/watchme/lambda/aggregation-worker/lambda_function.py`

```python
import boto3
import requests
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sqs = boto3.client('sqs', region_name='ap-southeast-2')

AGGREGATOR_API_URL = 'https://api.hey-watch.me/aggregator/spot'
PROFILER_QUEUE_URL = os.environ['PROFILER_QUEUE_URL']

def lambda_handler(event, context):
    """Process aggregation for each audio recording"""

    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            device_id = body['device_id']
            recorded_at = body['recorded_at']

            logger.info(f"Processing aggregation: device_id={device_id}, recorded_at={recorded_at}")

            # Call Aggregator API
            response = requests.post(
                AGGREGATOR_API_URL,
                json={
                    'device_id': device_id,
                    'recorded_at': recorded_at
                },
                timeout=30
            )

            if response.status_code == 200:
                logger.info(f"Aggregation successful: {response.json()}")

                # Send to profiler queue
                sqs.send_message(
                    QueueUrl=PROFILER_QUEUE_URL,
                    MessageBody=json.dumps({
                        'device_id': device_id,
                        'recorded_at': recorded_at
                    })
                )
                logger.info(f"Sent to profiler queue: device_id={device_id}")
            else:
                error_msg = f"Aggregator API failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except Exception as e:
            logger.error(f"Error processing record: {str(e)}")
            raise  # Re-raise to trigger SQS retry

    return {
        'statusCode': 200,
        'body': json.dumps('Aggregation processing completed')
    }
```

**requirements.txt**:
```
requests==2.31.0
boto3==1.34.0
```

**環境変数**:
- `PROFILER_QUEUE_URL`: `https://sqs.ap-southeast-2.amazonaws.com/.../watchme-profiler-queue`

**設定**:
- タイムアウト: 30秒
- メモリ: 256 MB
- リトライ: SQS visibility timeout（30秒 × 3回）
- 同時実行数: 10

---

#### Lambda 3: `profiler-worker`（NEW）

**役割**: Spot Profiler API呼び出し、LLM分析実行

**コード**: `/Users/kaya.matsumoto/projects/watchme/lambda/profiler-worker/lambda_function.py`

```python
import boto3
import requests
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SPOT_PROFILER_API_URL = 'https://api.hey-watch.me/profiler/spot-profiler'
# TODO Phase 4-2: Daily Profiler API URL
# DAILY_AGGREGATOR_API_URL = 'https://api.hey-watch.me/aggregator/daily'
# DAILY_PROFILER_API_URL = 'https://api.hey-watch.me/profiler/daily-profiler'

def lambda_handler(event, context):
    """Process profiling for each audio recording"""

    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            device_id = body['device_id']
            recorded_at = body['recorded_at']

            logger.info(f"Processing profiling: device_id={device_id}, recorded_at={recorded_at}")

            # 1. Call Spot Profiler API
            spot_response = requests.post(
                SPOT_PROFILER_API_URL,
                json={
                    'device_id': device_id,
                    'recorded_at': recorded_at
                },
                timeout=60  # LLM call may take time
            )

            if spot_response.status_code == 200:
                logger.info(f"Spot Profiler successful: {spot_response.json()}")
            else:
                error_msg = f"Spot Profiler API failed: {spot_response.status_code} - {spot_response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

            # TODO Phase 4-2: Daily Aggregator/Profiler logic
            # - Check if this is the first recording of the day
            # - If yes: create daily_aggregator
            # - If no: update daily_aggregator + run daily_profiler

        except Exception as e:
            logger.error(f"Error processing record: {str(e)}")
            raise  # Re-raise to trigger SQS retry

    return {
        'statusCode': 200,
        'body': json.dumps('Profiling processing completed')
    }
```

**requirements.txt**:
```
requests==2.31.0
boto3==1.34.0
```

**設定**:
- タイムアウト: 60秒（LLM呼び出しあり）
- メモリ: 512 MB
- リトライ: SQS visibility timeout（60秒 × 3回）
- 同時実行数: 5（LLM APIレート制限考慮）

---

### SQSキュー設計

#### Queue 1: `watchme-aggregation-queue`

```yaml
QueueName: watchme-aggregation-queue
VisibilityTimeout: 30  # Lambda実行時間 + バッファ
MessageRetentionPeriod: 86400  # 1日（24時間）
ReceiveMessageWaitTimeSeconds: 20  # Long polling
RedrivePolicy:
  deadLetterTargetArn: arn:aws:sqs:ap-southeast-2:xxx:watchme-processing-dlq
  maxReceiveCount: 3  # 3回失敗でDLQへ
```

#### Queue 2: `watchme-profiler-queue`

```yaml
QueueName: watchme-profiler-queue
VisibilityTimeout: 60  # Lambda実行時間（LLM呼び出しあり）
MessageRetentionPeriod: 86400
ReceiveMessageWaitTimeSeconds: 20
RedrivePolicy:
  deadLetterTargetArn: arn:aws:sqs:ap-southeast-2:xxx:watchme-processing-dlq
  maxReceiveCount: 3
```

#### Queue 3: `watchme-processing-dlq` (Dead Letter Queue)

```yaml
QueueName: watchme-processing-dlq
MessageRetentionPeriod: 1209600  # 14日間保持
```

**用途**: 3回リトライしても失敗したメッセージを自動隔離

---

### エラーハンドリング戦略

#### 1. **SQSの自動リトライ**
- Lambda関数が例外をraiseすると、SQSが自動的にメッセージを再配信
- `maxReceiveCount: 3` → 3回失敗でDLQへ

#### 2. **Dead Letter Queue (DLQ) 監視**
- CloudWatch Alarms でDLQメッセージ数を監視
- メッセージが1つでも入ったらアラート通知

#### 3. **CloudWatch Logs**
- すべてのLambda関数でロギング
- エラー発生時は `logger.error()` でスタックトレース記録

#### 4. **手動リトライ**
- DLQのメッセージを確認し、問題解決後に手動で元のキューに戻す

---

### 監視・アラート設定

#### CloudWatch Alarms

```bash
# DLQメッセージ監視
aws cloudwatch put-metric-alarm \
  --alarm-name watchme-dlq-messages-alarm \
  --alarm-description "Alert when messages appear in DLQ" \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS \
  --dimensions Name=QueueName,Value=watchme-processing-dlq \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --region ap-southeast-2

# aggregation-worker エラー率監視
aws cloudwatch put-metric-alarm \
  --alarm-name aggregation-worker-error-rate \
  --alarm-description "Alert when aggregation-worker error rate > 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --dimensions Name=FunctionName,Value=aggregation-worker \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --region ap-southeast-2

# profiler-worker エラー率監視
aws cloudwatch put-metric-alarm \
  --alarm-name profiler-worker-error-rate \
  --alarm-description "Alert when profiler-worker error rate > 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --dimensions Name=FunctionName,Value=profiler-worker \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.05 \
  --comparison-operator GreaterThanThreshold \
  --region ap-southeast-2
```

---

### デプロイ手順

#### Step 1: SQSキュー作成

```bash
# aggregation-queue
aws sqs create-queue \
  --queue-name watchme-aggregation-queue \
  --region ap-southeast-2 \
  --attributes file://aggregation-queue-attributes.json

# profiler-queue
aws sqs create-queue \
  --queue-name watchme-profiler-queue \
  --region ap-southeast-2 \
  --attributes file://profiler-queue-attributes.json

# DLQ
aws sqs create-queue \
  --queue-name watchme-processing-dlq \
  --region ap-southeast-2 \
  --attributes MessageRetentionPeriod=1209600
```

**aggregation-queue-attributes.json**:
```json
{
  "VisibilityTimeout": "30",
  "MessageRetentionPeriod": "86400",
  "ReceiveMessageWaitTimeSeconds": "20",
  "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:xxx:watchme-processing-dlq\",\"maxReceiveCount\":3}"
}
```

**profiler-queue-attributes.json**:
```json
{
  "VisibilityTimeout": "60",
  "MessageRetentionPeriod": "86400",
  "ReceiveMessageWaitTimeSeconds": "20",
  "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:xxx:watchme-processing-dlq\",\"maxReceiveCount\":3}"
}
```

#### Step 2: Lambda関数作成・デプロイ

各Lambda関数のディレクトリで実行:

```bash
# aggregation-worker
cd /Users/kaya.matsumoto/projects/watchme/lambda/aggregation-worker
./deploy.sh

# profiler-worker
cd /Users/kaya.matsumoto/projects/watchme/lambda/profiler-worker
./deploy.sh
```

#### Step 3: Lambda トリガー設定

```bash
# aggregation-worker にトリガー追加
aws lambda create-event-source-mapping \
  --function-name aggregation-worker \
  --event-source-arn arn:aws:sqs:ap-southeast-2:xxx:watchme-aggregation-queue \
  --batch-size 1 \
  --region ap-southeast-2

# profiler-worker にトリガー追加
aws lambda create-event-source-mapping \
  --function-name profiler-worker \
  --event-source-arn arn:aws:sqs:ap-southeast-2:xxx:watchme-profiler-queue \
  --batch-size 1 \
  --region ap-southeast-2
```

#### Step 4: 監視設定

上記の「監視・アラート設定」セクションのコマンドを実行。

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

### 2025-11-13 深夜 - 既存Lambda関数の流用方針決定 + 実装計画確定 🎯

**重要な決定**: 既存のLambda関数を最大限流用し、既存の場所（`server-configs/production/lambda-functions/`）で拡張・新規作成

**背景**:
- 既に4つのLambda関数が `/server-configs/production/lambda-functions/` に存在
- デプロイスクリプト（`deploy-dashboard-lambdas.sh`, `create-sqs-queues.sh`）も既に整備済み
- 新規ディレクトリを作るより、既存の場所で一元管理するほうが合理的

**流用・新規作成計画**:
1. **audio-processor** ✅ 既存（変更なし）
2. **audio-worker** 🔧 拡張（trace_id生成、pipeline_status更新、SQS送信追加）
3. **aggregation-worker** 🆕 新規作成（dashboard-summary-worker をテンプレートに使用）
4. **profiler-worker** 🆕 新規作成（dashboard-analysis-worker をテンプレートに使用）
5. **dashboard-summary-worker** 📦 保留（Phase 4-2で使用予定）
6. **dashboard-analysis-worker** 📦 保留（Phase 4-2で使用予定）

**推定作業時間**: 3.5時間（当初5時間から短縮）
- Step 1: 既存Lambda確認（10分）
- Step 2: audio-worker 拡張（30分）
- Step 3: 新規Lambda作成（2時間）
- Step 4: SQSキュー追加（15分）
- Step 5: デプロイスクリプト更新（15分）
- Step 6: 動作確認（30分）

**次のセッション**: Step 1-6 の実装

---

### 2025-11-13 深夜 - trace_id ベース可視化戦略決定 + pipeline_status テーブル作成 🎯

**重要な決定**: Step Functions を使わずに、trace_id + Supabase で運用性を最大化

**背景**:
- Step Functions 却下後、「可視化・デバッグをどうするか」が課題
- エンジニアから trace_id ベース戦略の提案
- **コスト0円、運用性最高、スケーラブル** な解決策として採用

**実装内容**:
1. **基本方針**: `trace_id = f"{device_id}_{recorded_at}"` で全パイプラインを追跡
2. **Supabase pipeline_status テーブル作成** ✅ 完了
   - フェーズごとのステータス管理（feature_extraction/aggregation/profiling/daily_profiling）
   - エラー情報の記録
   - リアルタイム更新対応
3. **5つの実装タスク**を定義
   - Task 1: trace_id 一本化（全Lambda・API）
   - Task 2: pipeline_status テーブル作成 ✅ 完了
   - Task 3: 全Lambda・APIから status を PATCH
   - Task 4: CloudWatch Logs Insights で trace_id 検索
   - Task 5: Supabaseリアルタイム可視化ダッシュボード

**効果**:
- ✅ **どこで止まっているか完全にわかる**
- ✅ **デバッグ・障害調査時間が 1/10**
- ✅ **Step Functions よりシンプル**
- ✅ **コストほぼ0円**
- ✅ **将来の拡張が容易**

---

### 2025-11-13 夜 - Step Functions 導入却下、SQS + Lambda 採用決定 🎯

**重要な決定**: Step Functions 導入を検討したが、詳細分析の結果、却下。

**却下理由**:
1. **コスト爆発**: 1000台で月$720（SQS + Lambda は $15 で48倍のコスト差）
2. **AWS非推奨**: 高頻度イベント処理（IoT/デバイス/センサー）には不向き
3. **柔軟性の喪失**: ステートマシンに縛られ、API変更が困難
4. **スケール制御の困難**: Execution limit exceeded、throttling のリスク

**採用アーキテクチャ**: SQS + Lambda
- ✅ コスト効率: デバイス数が増えても線形コスト
- ✅ AWS推奨: 高頻度イベント処理に最適
- ✅ 柔軟性: API順番の変更、新規追加が容易
- ✅ エラーハンドリング: DLQ で失敗メッセージを自動隔離

**教訓**: 「現在1台だから安い」ではなく、「100台、500台、1000台での運用コスト」で評価すべき。検討した上での却下は、大規模な手戻りを回避する価値ある判断。

**次のタスク**: Task 1（Lambda + SQS ワークフロー実装）を最優先で実施。

---

### 2025-11-13 夕方 - データベーステーブル命名規則統一 + aggregatorsテーブル作成 🎉

**目的**: データベーステーブル名を統一し、累積分析用のaggregatorsテーブルを作成

**変更内容**:

1. **テーブル名変更**
   - `summary_daily` → `daily_results`
   - `summary_weekly` → `weekly_results`
   - `summary_monthly` → `monthly_results`
   - 理由: `spot_results`と命名規則を統一

2. **新規テーブル作成**
   - `daily_aggregators` (Layer 2): spot_resultsから1日分のプロンプト生成
   - `weekly_aggregators` (Layer 2): daily_resultsから7日分のプロンプト生成
   - `monthly_aggregators` (Layer 2): daily_resultsから30日分のプロンプト生成

3. **スキーマ修正**
   - `*_results`テーブルに新カラム追加: `summary`, `behavior`, `llm_model`
   - `device_id`の型を`UUID`→`TEXT`に統一（spot_resultsと同じ）

4. **ドキュメント更新**
   - `ARCHITECTURE_AND_MIGRATION_GUIDE.md`に「データフローの理解」セクション追加
   - 具体例と間違いやすいポイントを明記
   - テーブル間の関係性（入力元・出力先）を明確化

**データフローの明確化**:
```
spot_results (1日に複数) → daily_aggregators (1日1プロンプト) → daily_results (1日1結果)
daily_results (7日分) → weekly_aggregators (1週1プロンプト) → weekly_results (1週1結果)
daily_results (30日分) → monthly_aggregators (1月1プロンプト) → monthly_results (1月1結果)
```

**マイグレーション**: `/supabase/migrations/20251113060000_rename_summary_tables_and_create_aggregators.sql`

---

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
