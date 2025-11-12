# 🏗️ WatchMe アーキテクチャ・移行ガイド

**プロジェクト**: 心理・感情モニタリングプラットフォーム
**作成日**: 2025-11-11
**最終更新**: 2025-11-12 午後
**ステータス**: ✅ Phase 3完了（80%） / 🚧 Phase 4 進行中（残り20%）

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
│ /api/profiler 🚧 新規作成予定                                 │
│                                                               │
│   ├─ POST /spot-profiler                                     │
│   │  ├─ 入力: spot_aggregators.aggregated_prompt             │
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

**prompt の内容**（約4700文字）:
- ASR（文字起こし）
- SED（音響イベント）統計
- SER（感情）タイムライン
- 時間コンテキスト（季節、曜日、時間帯、祝日）
- subject_info（年齢、性別、メモ）
- LLM分析用スコアリングガイドライン

---

### 4. spot_results - スポット分析結果

```sql
CREATE TABLE spot_results (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC

  -- 基本スコア
  vibe_score INTEGER CHECK (vibe_score >= -100 AND vibe_score <= 100),
  vibe_summary TEXT,                  -- 2-3文の要約
  vibe_behavior TEXT,                 -- 行動パターン

  -- 詳細分析
  psychological_analysis JSONB,       -- 心理分析詳細
  behavioral_analysis JSONB,          -- 行動分析詳細
  acoustic_metrics JSONB,             -- 音響メトリクス
  key_observations JSONB,             -- 重要な観察事項

  -- メタ情報
  vibe_scorer_result JSONB,           -- LLMの完全レスポンス
  vibe_analyzed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),

  PRIMARY KEY (device_id, recorded_at)
);
```

**役割**: Layer 3（Profiler - Spot）の出力データ保存

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

### ✅ Phase 3完了: 統合・プロンプト生成（2025-11-12 完了）

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
- ✅ 本番動作確認済み 🎉
  - URL: https://api.hey-watch.me/aggregator/spot
  - プロンプト長: 4700文字程度
  - 処理時間: 1-2秒

---

### 🚧 Phase 4進行中: Profiler API新規作成（残り20%）

#### 現状の課題

- ❌ Profiler API (`/api/profiler`) が未作成
- ⚠️ 既存Scorer API (`/api/vibe-analysis/scorer`) が旧アーキテクチャのまま
  - 保存先: `audio_scorer` テーブル（旧）
  - 入力元: `audio_aggregator.vibe_aggregator_result`（旧）

#### 必要な作業

**1. Profiler API新規作成**（最優先）

ディレクトリ: `/Users/kaya.matsumoto/projects/watchme/api/profiler`

```
/api/profiler/
├── main.py
├── endpoints/
│   ├── spot_profiler.py       # 既存Scorerから移植
│   ├── daily_profiler.py      # 既存Scorerから移植
│   ├── weekly_profiler.py     # 新規実装
│   └── monthly_profiler.py    # 新規実装
├── services/
│   ├── llm_client.py          # 既存Scorerから移植
│   └── supabase_client.py
├── docker-compose.prod.yml
├── Dockerfile.prod
├── requirements.txt
└── README.md
```

**推定作業時間**: 3-4時間

---

**2. 4つのエンドポイント実装**

| エンドポイント | 入力 | 出力 | 説明 | 作業 |
|-------------|------|------|------|------|
| `/spot-profiler` | `spot_aggregators` | `spot_results` | スポット録音の心理分析 | 既存Scorerから移植 |
| `/daily-profiler` | `spot_results`（1日分） | `summary_daily` | 日次累積分析 | 既存Scorerから移植 |
| `/weekly-profiler` | `summary_daily`（7日分） | `summary_weekly` | 週次トレンド分析 | 🆕新規実装 |
| `/monthly-profiler` | `summary_daily`（30日分） | `summary_monthly` | 月次長期分析 | 🆕新規実装 |

---

**3. Lambda関数の修正**

`audio-worker` Lambda関数:
- エンドポイント変更: `/analyze-timeblock` → `/spot-profiler`
- URL変更: `https://api.hey-watch.me/vibe-analysis/scorer/` → `https://api.hey-watch.me/profiler/`

**推定作業時間**: 30分

---

### ⏳ Phase 5未着手: クライアント側表示

- ⏳ iOS アプリ: 各resultsテーブルからデータ取得・表示
- ⏳ Web ダッシュボード: 同様（優先度低・休止中）

**推定作業時間**: 3-4時間

---

## 🚀 次のタスク（優先度順）

### Task 1: Profiler API新規作成（最優先）

**ステップ1: ディレクトリ・基本構造作成**

```bash
cd /Users/kaya.matsumoto/projects/watchme/api
mkdir -p profiler/{endpoints,services}
cd profiler
```

---

**ステップ2: 既存Scorerからロジックを移植**

参考ファイル:
- `/Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/scorer/main.py`
- `/Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/scorer/llm_providers.py`
- `/Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/scorer/supabase_client.py`

移植内容:
1. `llm_providers.py` → `services/llm_client.py`
2. `supabase_client.py` → `services/supabase_client.py`
3. `/analyze-timeblock` → `endpoints/spot_profiler.py`
4. `/analyze-dashboard-summary` → `endpoints/daily_profiler.py`

---

**ステップ3: 新規エンドポイント実装**

`endpoints/weekly_profiler.py`:
```python
@router.post("/weekly-profiler")
async def analyze_weekly(request: WeeklyProfilerRequest):
    """
    1週間分のsummary_dailyを取得
    週次分析プロンプト生成
    LLM実行
    summary_weeklyに保存
    """
```

`endpoints/monthly_profiler.py`:
```python
@router.post("/monthly-profiler")
async def analyze_monthly(request: MonthlyProfilerRequest):
    """
    1ヶ月分のsummary_dailyを取得
    月次分析プロンプト生成
    LLM実行
    summary_monthlyに保存
    """
```

---

**ステップ4: Docker・CI/CD設定**

1. `docker-compose.prod.yml` 作成
2. `Dockerfile.prod` 作成
3. `.github/workflows/deploy-to-ecr.yml` 作成
4. systemdサービスファイル作成

---

**ステップ5: デプロイ・動作確認**

```bash
# ローカルテスト
docker-compose up --build

# 本番デプロイ
git add .
git commit -m "feat: Create Profiler API with 4 endpoints"
git push origin main
```

---

### Task 2: Lambda関数修正

`audio-worker` の修正:
- Scorer API呼び出し → Profiler API呼び出しに変更
- エンドポイント: `/spot-profiler`
- URL: `https://api.hey-watch.me/profiler/spot-profiler`

---

### Task 3: iOS表示ロジック実装

各resultsテーブルからデータ取得:
- `spot_results`: スポット分析結果
- `summary_daily`: 日次分析結果
- `summary_weekly`: 週次分析結果
- `summary_monthly`: 月次分析結果

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

### 2025-11-12 午後セッション - Phase 3完了 🎉

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
