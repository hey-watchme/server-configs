# WatchMe ネーミング規則

**最終更新**: 2025-11-09

## 🎯 基本原則

**統一性を最優先**：エンドポイント名、テーブル名、カラム名は全て整合性を保つ

---

## 📡 APIエンドポイント命名規則

### パターン：`/{分析種別}/{役割}/`

| 分析種別 | 役割 | エンドポイント | コンテナ名 |
|---------|------|--------------|-----------|
| `behavior-analysis` | `feature-extractor` | `/behavior-analysis/feature-extractor/` | `behavior-analysis-feature-extractor-v3` |
| `emotion-analysis` | `feature-extractor` | `/emotion-analysis/feature-extractor/` | `emotion-analysis-feature-extractor-v2` |
| `vibe-analysis` | `transcriber` | `/vibe-analysis/transcriber/` | `vibe-analysis-transcriber-v2` |
| `behavior-analysis` | `aggregator` | `/behavior-analysis/aggregator/` | `behavior-analysis-aggregator` |
| `emotion-analysis` | `aggregator` | `/emotion-analysis/aggregator/` | `emotion-analysis-aggregator` |
| `vibe-analysis` | `aggregator` | `/vibe-analysis/aggregator/` | `vibe-analysis-aggregator` |
| `vibe-analysis` | `scorer` | `/vibe-analysis/scorer/` | `vibe-analysis-scorer` |

### 重要ポイント
- **役割は `-er` 形式**（動作主体を表す）
  - `feature-extractor`（抽出者）
  - `transcriber`（文字起こし者）
  - `aggregator`（集約者）
  - `scorer`（スコアリング者）

---

## 🗄️ データベーステーブル命名規則

### テーブル名

| テーブル名 | 用途 | 複数形 |
|-----------|------|--------|
| `audio_features` | 特徴抽出結果 | ✅ 複数形 |
| `audio_aggregator` | 集約データ | ❌ 単数形（処理単位） |
| `audio_scorer` | スコアリング結果 | ❌ 単数形（処理単位） |
| `summary_daily` | 日次サマリー | ❌ 単数形（集約単位） |

### カラム名パターン

#### パターン1: `{api役割}_result`
```sql
-- audio_features テーブル
behavior_extractor_result JSONB
emotion_extractor_result JSONB
transcriber_result TEXT

-- audio_aggregator テーブル
behavior_aggregator_result JSONB
emotion_aggregator_result JSONB
vibe_aggregator_result TEXT

-- audio_scorer テーブル
vibe_scorer_result JSONB
```

#### パターン2: `{api役割}_status`
```sql
behavior_extractor_status TEXT
emotion_extractor_status TEXT
transcriber_status TEXT
```

#### パターン3: `{api役割}_processed_at`
```sql
behavior_extractor_processed_at TIMESTAMP
emotion_extractor_processed_at TIMESTAMP
transcriber_processed_at TIMESTAMP
```

---

## 🔗 命名の整合性マップ

| API名 | エンドポイント | カラム名（結果） | カラム名（ステータス） |
|-------|--------------|----------------|---------------------|
| Behavior Features API (v3) | `/behavior-analysis/feature-extractor/` | `behavior_extractor_result` | `behavior_extractor_status` |
| Emotion Features API (v2) | `/emotion-analysis/feature-extractor/` | `emotion_extractor_result` | `emotion_extractor_status` |
| Vibe Transcriber API (v2) | `/vibe-analysis/transcriber/` | `transcriber_result` | `transcriber_status` |
| Behavior Aggregator API | `/behavior-analysis/aggregator/` | `behavior_aggregator_result` | - |
| Emotion Aggregator API | `/emotion-analysis/aggregator/` | `emotion_aggregator_result` | - |
| Vibe Aggregator API | `/vibe-analysis/aggregator/` | `vibe_aggregator_result` | - |
| Vibe Scorer API | `/vibe-analysis/scorer/` | `vibe_scorer_result` | - |

---

## 📊 データ型の選択基準

| データの性質 | 型 | 例 |
|------------|----|----|
| **単純なテキスト** | `TEXT` | `transcriber_result`, `vibe_aggregator_result` |
| **検索・ソート対象の数値** | `DOUBLE PRECISION` | `vibe_score` |
| **構造化データ（配列・オブジェクト）** | `JSONB` | `behavior_extractor_result`, `emotion_extractor_result` |
| **頻繁にアクセスする値** | 個別カラム | `vibe_score`, `vibe_summary` |
| **詳細データ** | JSONB | `vibe_scorer_result` |

### 実例：audio_scorer テーブル

```sql
-- ✅ 良い例：頻繁に使う値は個別カラム + 詳細はJSONB
vibe_score DOUBLE PRECISION          -- 検索・ソート用
vibe_summary TEXT                    -- 表示用
vibe_behavior TEXT                   -- 分類用
vibe_scorer_result JSONB             -- 全詳細データ

-- ❌ 悪い例：全てJSONBに詰め込む
vibe_result JSONB  -- {score: 85, summary: "...", behavior: "..."}
```

---

## 🚫 旧命名との対応表（非推奨）

| 旧命名 | 新命名 | 理由 |
|--------|--------|------|
| `sed_result` | `behavior_extractor_result` | API名との整合性 |
| `ser_result` | `emotion_extractor_result` | API名との整合性 |
| `asr_result` | `transcriber_result` | API名との整合性 |
| `vibe_prompt` | `vibe_aggregator_result` | 命名規則の統一 |
| `behavior_aggregated` | `behavior_aggregator_result` | 命名規則の統一 |

**旧命名は使用しないでください**。新しいコードでは必ず新命名を使用。

---

## 📁 ディレクトリ・ファイル命名

### マイグレーションファイル
```
supabase/migrations/
├── 20251109000001_create_audio_features_tables.sql
└── 20251109000002_rename_columns_for_consistency.sql
```

**フォーマット**: `YYYYMMDDHHMMSS_{説明}.sql`

### ドキュメントファイル
```
server-configs/migrations/
├── 001_create_audio_features_tables.sql
├── 002_rename_columns_for_consistency.sql
├── NAMING_CONVENTIONS.md（このファイル）
└── HANDOVER_MEMO.md
```

**フォーマット**: `{連番}_{説明}.{拡張子}`

---

## ✅ チェックリスト

新しいAPI/テーブル/カラムを追加する時：

- [ ] エンドポイント名は `-er` 形式か？
- [ ] カラム名は `{api役割}_result` パターンか？
- [ ] データ型は適切か？（TEXT/JSONB/DOUBLE PRECISION）
- [ ] 既存の命名規則と整合性があるか？
- [ ] ドキュメントを更新したか？

---

**次のセッションでこのドキュメントを参照して、一貫性のある命名を維持してください。**
