# WatchMe テーブルスキーマリファレンス

**最終更新**: 2025-11-09
**マイグレーション適用済み**: 002_rename_columns_for_consistency.sql

## 🗄️ テーブル一覧

| テーブル名 | 用途 | Primary Key |
|-----------|------|-------------|
| `audio_features` | 3つのAPI（Transcriber/Behavior/Emotion）の処理結果 | (device_id, date, time_block) |
| `audio_aggregator` | 3つのAggregatorの集約結果 | (device_id, date, time_block) |
| `audio_scorer` | Vibe ScorerのChatGPT分析結果 | (device_id, date, time_block) |
| `summary_daily` | 日次累積分析 | (device_id, date) |
| `summary_weekly` | 週次累積分析 | (device_id, week_start_date) |
| `summary_monthly` | 月次累積分析 | (device_id, year, month) |

---

## 1️⃣ audio_features（特徴抽出結果）

### 概要
3つのFeatures API（Transcriber, Behavior Extractor, Emotion Extractor）の処理結果を格納。

### スキーマ

```sql
CREATE TABLE audio_features (
  -- Primary Key
  device_id TEXT NOT NULL,
  date DATE NOT NULL,
  time_block TEXT NOT NULL,

  -- Vibe Transcriber (ASR)
  transcriber_result TEXT,                      -- 文字起こしテキスト
  transcriber_status TEXT DEFAULT 'pending',
  transcriber_processed_at TIMESTAMP WITH TIME ZONE,
  transcriber_error_message TEXT,

  -- Behavior Features (SED)
  behavior_extractor_result JSONB,              -- 527種類の音響イベント
  behavior_extractor_status TEXT DEFAULT 'pending',
  behavior_extractor_processed_at TIMESTAMP WITH TIME ZONE,
  behavior_extractor_error_message TEXT,

  -- Emotion Features (SER)
  emotion_extractor_result JSONB,               -- 8つの感情スコア
  emotion_extractor_status TEXT DEFAULT 'pending',
  emotion_extractor_processed_at TIMESTAMP WITH TIME ZONE,
  emotion_extractor_error_message TEXT,

  -- References
  audio_file_path TEXT,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  PRIMARY KEY (device_id, date, time_block)
);
```

### ステータス値
```sql
CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'skipped', 'quota_exceeded'))
```

### データ例

```json
{
  "device_id": "9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93",
  "date": "2025-11-09",
  "time_block": "14-30",

  "transcriber_result": "今日はとても良い天気ですね。",
  "transcriber_status": "completed",

  "behavior_extractor_result": {
    "events": [
      {"label": "Speech", "score": 0.95},
      {"label": "Music", "score": 0.05}
    ]
  },
  "behavior_extractor_status": "completed",

  "emotion_extractor_result": {
    "happy": 0.8,
    "sad": 0.1,
    "angry": 0.05,
    "neutral": 0.05
  },
  "emotion_extractor_status": "completed"
}
```

---

## 2️⃣ audio_aggregator（集約データ）

### 概要
Aggregator API（Behavior, Emotion）の集約結果を格納。**1日1レコード**で累積更新。

### スキーマ

```sql
CREATE TABLE audio_aggregator (
  -- Primary Key（1日1レコード）
  device_id TEXT NOT NULL,
  date DATE NOT NULL,

  -- Behavior Aggregator
  behavior_aggregator_result JSONB,             -- time_blocks（30分スロット別集計）
  behavior_aggregator_processed_at TIMESTAMP WITH TIME ZONE,

  -- Emotion Aggregator
  emotion_aggregator_result JSONB,              -- 感情推移集約
  emotion_aggregator_processed_at TIMESTAMP WITH TIME ZONE,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  PRIMARY KEY (device_id, date)  -- time_block削除済み
);
```

**重要な設計変更（2025-11-09）**:
- ❌ `time_block`カラム削除（30分単位は不要、たまたまそうなっているだけ）
- ❌ 不要カラム削除（`*_summary`, `vibe_aggregator_*`, `context_data`, `status`, `error_message`）
- ✅ Primary Key: `(device_id, date)` のみ
- ✅ 1日1レコードで累積更新（30分ごとに上書き）
- ✅ `summary_ranking`はDBに保存せず、アプリ側で計算

---

## 3️⃣ audio_scorer（スコアリング結果）

### 概要
Vibe Scorer APIのChatGPT分析結果を格納。

### スキーマ

```sql
CREATE TABLE audio_scorer (
  -- Primary Key
  device_id TEXT NOT NULL,
  date DATE NOT NULL,
  time_block TEXT NOT NULL,

  -- Vibe Score Results（個別カラム：頻繁にアクセス）
  vibe_score DOUBLE PRECISION CHECK (vibe_score >= -100 AND vibe_score <= 100),
  vibe_summary TEXT,
  vibe_behavior TEXT,

  -- Full ChatGPT Response（詳細データ）
  vibe_scorer_result JSONB,

  -- Timestamps
  vibe_analyzed_at TIMESTAMP WITH TIME ZONE,

  -- Status
  status TEXT NOT NULL DEFAULT 'pending',
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  PRIMARY KEY (device_id, date, time_block)
);
```

### データ例

```json
{
  "vibe_score": 85,
  "vibe_summary": "非常にポジティブな会話が多く、リラックスした雰囲気でした。",
  "vibe_behavior": "会議",
  "vibe_scorer_result": {
    "detailed_analysis": "...",
    "keywords": ["ポジティブ", "リラックス"],
    "confidence": 0.9
  }
}
```

---

## 4️⃣ summary_daily（日次累積分析）

### 概要
その日の累積分析結果。30分ごとに更新される。

### スキーマ

```sql
CREATE TABLE summary_daily (
  -- Primary Key
  device_id UUID NOT NULL,           -- ⚠️ UUID型（audio_featuresはTEXT型）
  date DATE NOT NULL,

  -- Prompt & Analysis
  prompt JSONB,
  prompt_generated_at TIMESTAMP WITH TIME ZONE,

  -- Results
  overall_summary TEXT,
  average_vibe REAL,
  vibe_scores JSONB,                  -- 48個のスコア配列

  -- Aggregated Insights
  hourly_summaries JSONB,
  emotion_trends JSONB,
  behavioral_patterns JSONB,

  -- Statistics
  processed_count INTEGER DEFAULT 0,
  last_time_block VARCHAR(5),
  last_updated_at TIMESTAMP WITH TIME ZONE,

  -- Status
  status TEXT NOT NULL DEFAULT 'pending',
  error_message TEXT,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  PRIMARY KEY (device_id, date)
);
```

---

## 📊 データフロー図

```
audio_files（既存）
    ↓
audio_features（Phase 1: Features API群）
    ├── transcriber_result
    ├── behavior_extractor_result
    └── emotion_extractor_result
    ↓
audio_aggregator（Phase 2: Aggregator API群）
    ├── vibe_aggregator_result
    ├── behavior_aggregator_result
    └── emotion_aggregator_result
    ↓
audio_scorer（Phase 3: Scorer API）
    ├── vibe_score
    ├── vibe_summary
    └── vibe_scorer_result
    ↓
summary_daily（累積分析）
    ├── overall_summary
    └── average_vibe
```

---

## 🔄 ステータス管理の階層

| テーブル | 責務 | ステータス管理 |
|---------|------|--------------|
| `audio_files` | 処理対象の判定 | `transcriptions_status`, `behavior_features_status`, `emotion_features_status` |
| `audio_features` | API処理結果 | 各API単位（`transcriber_status`等） |
| `audio_aggregator` | 集約処理 | `status` |
| `audio_scorer` | 最終分析 | `status` |
| `summary_daily` | 累積分析 | `status` |

詳細は `007_status_management_design.md` を参照。

---

## ⚠️ 重要な注意点

### 1. device_idの型変換
```sql
-- audio_features, audio_aggregator, audio_scorer: TEXT型
device_id TEXT

-- summary_daily, summary_weekly, summary_monthly: UUID型
device_id UUID

-- 変換が必要
INSERT INTO summary_daily (device_id, ...)
VALUES (device_id::UUID, ...);
```

### 2. Primary Keyの一貫性
全テーブルで `(device_id, date, time_block)` を基準とする（summary系を除く）。

### 3. JSONBカラムのクエリ例
```sql
-- behavior_extractor_resultから特定のイベントを検索
SELECT *
FROM audio_features
WHERE behavior_extractor_result @> '{"events": [{"label": "Speech"}]}';

-- emotion_extractor_resultからhappyスコアを取得
SELECT
  device_id,
  date,
  time_block,
  emotion_extractor_result->>'happy' AS happy_score
FROM audio_features
WHERE (emotion_extractor_result->>'happy')::float > 0.8;
```

---

## 📚 関連ドキュメント

- [NAMING_CONVENTIONS.md](./NAMING_CONVENTIONS.md) - ネーミング規則
- [007_status_management_design.md](./007_status_management_design.md) - ステータス管理設計
- [API_MIGRATION_PLAN.md](./API_MIGRATION_PLAN.md) - API修正計画

---

**このリファレンスは、次のセッションでAPI修正時に参照してください。**
