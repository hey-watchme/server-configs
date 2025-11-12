# 🎙️ タイムスタンプ統一・UTC移行ガイド

**作成日**: 2025-11-11
**最終更新**: 2025-11-11 22:30
**ステータス**: 🚧 進行中

---

## ⚠️ 重要な方針転換（2025-11-11 22:30）

### 🎯 新しい方針: UTC統一アーキテクチャ

**タイムブロック方式（30分集約）から個別タイムスタンプ方式（UTC統一）に移行**

#### 移行の理由
1. **旧方式の問題**: 30分以内に複数回録音すると、最新データで上書きされる
2. **設計の複雑さ**: `local_datetime` カラムを管理するのは冗長
3. **業界標準**: 全てUTCで保存し、表示時にローカル変換

#### 新しい設計
```
【データ保存】
全てUTCで統一
- audio_files.recorded_at (TIMESTAMPTZ, UTC)
- spot_features.recorded_at (TIMESTAMPTZ, UTC)
- local_datetime カラムは削除

【表示時】
devices.timezone を使ってクライアント側で変換
- iOS: devices.timezone を取得 → UTCをローカル時間に変換して表示
- Web: 同様
- Aggregator API: プロンプト生成時にローカル時間に変換
```

---

## 📋 進捗状況（2025-11-12 最終更新）

### ✅ Phase 1完了: 録音（iOS → S3 → Vault API）

#### 1. データベース修正
- ✅ `audio_files.local_datetime` カラム削除
- ✅ `spot_features.local_datetime` カラム削除
- ✅ `spot_features` テーブルに不足カラム追加
- ✅ `spot_features` テーブルのRLS無効化
- ✅ `spot_results` テーブル作成（新規）
- ✅ `spot_aggregators` テーブル作成（新規）
- ✅ `devices.timezone` カラム存在確認

#### 2. iOSアプリ修正
- ✅ `UploaderService.swift`: `recorded_at` をUTCで送信
- ✅ コミット・プッシュ・ビルド成功確認

#### 3. Vault API修正
- ✅ `local_datetime` 保存処理を削除
- ✅ S3パス構造を変更: `{HH-MM}` → `{HH-MM-SS}` (秒単位精度)
- ✅ README.md完全更新

---

### ✅ Phase 2完了: 特徴抽出（ASR + SED + SER → spot_features）

#### 4. Vibe Transcriber（ASR）修正
- ✅ `audio_files` テーブルから `device_id`, `recorded_at` 取得
- ✅ `spot_features` テーブルに保存
- ✅ キー変更: `(device_id, date, time_block)` → `(device_id, recorded_at)`
- ✅ 本番動作確認済み 🎉

#### 5. Behavior Features（SED）修正
- ✅ `spot_features` に保存
- ✅ `save_to_spot_features()` 関数実装
- ✅ 本番動作確認済み 🎉

#### 6. Emotion Feature Extractor v2（SER）修正
- ✅ `emotion_opensmile` → `spot_features` に完全移行
- ✅ 本番動作確認済み 🎉

---

### ✅ Phase 3完了: 統合・プロンプト生成（Aggregator API）

#### 7. Aggregator API修正
- ✅ `spot_features` からASR+SED+SERデータ取得
- ✅ `devices.timezone` 対応
- ✅ UTC→ローカル時間変換（pytz使用）
- ✅ 統合プロンプト生成
- ✅ `spot_aggregators` に保存
- ✅ 本番動作確認済み 🎉

---

### 🚧 Phase 4進行中: LLM分析（Scorer API）- 残り10%

#### 8. Scorer API修正（進行中）
**現状**:
- ✅ プロンプト形式は完成（`/api/aggregator/services/prompt_generator.py`）
- ✅ LLM呼び出しロジック完成（`/api/vibe-analysis/scorer/main.py`）
- ❌ 保存先テーブルが `audio_scorer` のまま（旧アーキテクチャ）

**必要な修正**:
- 🚧 入力元変更: `audio_aggregator.vibe_aggregator_result` → `spot_aggregators.aggregated_prompt`
- 🚧 保存先変更: `audio_scorer` → `spot_results`
- 🚧 リクエストパラメータ変更: `(device_id, date, time_block)` → `(device_id, recorded_at)`
- 🚧 動作確認

**参考**:
- 既存エンドポイント: `/analyze-timeblock`（行299-496）
- 新エンドポイント: `/analyze-spot`（新規作成が必要）

---

### ⏳ Phase 5未着手: クライアント側表示

#### 9. iOS アプリ表示ロジック
- ⏳ `spot_results` からデータ取得
- ⏳ UTC → ローカル時間変換
- ⏳ ダッシュボード画面の実装

#### 10. Web ダッシュボード
- ⏳ 同様の修正（優先度低・休止中）

---

## 🎯 次セッションの TODO

### ✅ 完了済み（Phase 1-3）

1. ✅ Vault API: `local_datetime` 削除 + S3パス秒単位精度化
2. ✅ Vibe Transcriber（ASR）: `spot_features` 移行 + 本番動作確認済み 🎉
3. ✅ Behavior Features（SED）: `spot_features` 移行 + 本番動作確認済み 🎉
4. ✅ Emotion Feature Extractor v2（SER）: `spot_features` 移行 + 本番動作確認済み 🎉
5. ✅ Aggregator API: `spot_features` からASR+SED+SER統合 + 本番動作確認済み 🎉

---

### 🚀 次のタスク（優先度順）- 残り10%

#### 1. Scorer API修正（最優先）

**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/scorer/main.py`

**必要な修正**:

1. **新エンドポイント作成**: `/analyze-spot`
   - リクエスト: `(device_id, recorded_at)`
   - 入力元: `spot_aggregators.aggregated_prompt`
   - 保存先: `spot_results`

2. **既存エンドポイント参考**: `/analyze-timeblock`（行388-496）
   - 同様のロジックをコピーして修正

3. **保存処理の変更**:
   ```python
   # 旧
   supabase.table('audio_scorer').upsert({...})

   # 新
   supabase.table('spot_results').upsert({
     'device_id': request.device_id,
     'recorded_at': request.recorded_at,
     'vibe_score': analysis_result.get('vibe_score'),
     'vibe_summary': analysis_result.get('summary'),
     'vibe_behavior': analysis_result.get('behavioral_analysis', {}).get('behavior_pattern'),
     'psychological_analysis': analysis_result.get('psychological_analysis'),
     'behavioral_analysis': analysis_result.get('behavioral_analysis'),
     'acoustic_metrics': analysis_result.get('acoustic_metrics'),
     'key_observations': analysis_result.get('key_observations'),
     'vibe_scorer_result': analysis_result,
     'vibe_analyzed_at': datetime.now().isoformat()
   })
   ```

4. **プロンプト取得の変更**:
   ```python
   # 旧
   result = supabase.table('audio_aggregator').select('vibe_aggregator_result')...

   # 新
   result = supabase.table('spot_aggregators').select('aggregated_prompt')...
   ```

**推定作業時間**: 30-60分

---

#### 2. Lambda関数の修正（Scorer API呼び出し）

**ファイル**: Lambda関数 `audio-worker` のコード

**必要な修正**:
- エンドポイント変更: `/analyze-timeblock` → `/analyze-spot`
- リクエストパラメータ: `(device_id, date, time_block)` → `(device_id, recorded_at)`

**推定作業時間**: 15-30分

---

#### 3. iOS アプリ表示ロジック（Phase 5）

**対象**:
- ダッシュボード画面
- 録音履歴画面

**修正内容**:
```swift
// 1. Get spot_results from Supabase
let results = supabase
  .from("spot_results")
  .select("*")
  .eq("device_id", deviceId)
  .order("recorded_at", ascending: false)
  .execute()

// 2. Get device timezone
let device = supabase.from("devices").select("timezone").eq("device_id", deviceId).single().execute()
let timezone = TimeZone(identifier: device.timezone)  // "Asia/Tokyo"

// 3. Convert UTC to local time
for result in results {
  let recordedAtUTC = result.recorded_at  // UTC timestamp
  let localTime = recordedAtUTC.convertTo(timezone: timezone)

  // Display
  Text(localTime.formatted())
  Text(result.vibe_summary)
  Text("Score: \(result.vibe_score)")
}
```

**推定作業時間**: 2-3時間

---

## 🗄️ データベーススキーマ（最終版）

### 1. audio_files - 録音ファイル情報（Phase 1: 録音）
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

### 2. spot_features - 特徴抽出結果（Phase 2: 分析）
```sql
CREATE TABLE spot_features (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC
  vibe_transcriber_result TEXT,          -- ASR: 文字起こし
  behavior_extractor_result JSONB,       -- SED: 527種類の音響イベント
  emotion_extractor_result JSONB,        -- SER: 8感情スコア
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

### 3. spot_aggregators - 統合プロンプト（Phase 3: 統合）
```sql
CREATE TABLE spot_aggregators (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC
  aggregated_prompt TEXT,             -- LLM分析用プロンプト（ASR+SED+SER統合）
  context_data JSONB,                 -- メタデータ（timezone, subject_infoなど）
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (device_id, recorded_at)
);
```

### 4. spot_results - LLM分析結果（Phase 4: スコアリング）
```sql
CREATE TABLE spot_results (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC
  vibe_score INTEGER,                 -- -100〜+100
  vibe_summary TEXT,                  -- 2-3文の要約
  vibe_behavior TEXT,                 -- 行動パターン
  psychological_analysis JSONB,       -- 心理分析詳細
  behavioral_analysis JSONB,          -- 行動分析詳細
  acoustic_metrics JSONB,             -- 音響メトリクス
  key_observations JSONB,             -- 重要な観察事項
  vibe_scorer_result JSONB,           -- LLMの完全レスポンス
  vibe_analyzed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (device_id, recorded_at)
);
```

### 5. devices（既存テーブル）
```sql
-- timezone カラムを使用
SELECT device_id, timezone FROM devices;
-- 例: 9f7d6e27-..., Asia/Tokyo
```

---

## 📊 データフロー（最終版）

```
【Phase 1: 録音】
iOS/Observer → S3 → Vault API → audio_files (UTC保存)

【Phase 2: 特徴抽出（並列実行）】
Lambda (audio-worker) → 3つの分析APIを並列実行:
  ├─ ASR (Vibe Transcriber)     → spot_features.vibe_transcriber_result
  ├─ SED (Behavior Features)    → spot_features.behavior_extractor_result
  └─ SER (Emotion Features)     → spot_features.emotion_extractor_result

【Phase 3: 統合・プロンプト生成】
Aggregator API (/api/aggregator):
  1. spot_features から ASR+SED+SER データ取得
  2. devices.timezone 取得
  3. UTC → ローカル時間に変換
  4. subject_info（年齢・性別）取得
  5. 統合プロンプト生成（時間コンテキスト含む）
  6. spot_aggregators に保存

【Phase 4: LLM分析】
Scorer API (/api/vibe-analysis/scorer):
  1. spot_aggregators.aggregated_prompt 取得
  2. ChatGPT/Groq でLLM分析実行
  3. spot_results に保存

【Phase 5: 表示】
iOS/Web:
  1. spot_results から分析結果取得
  2. devices.timezone 取得
  3. UTC → ローカル時間に変換
  4. ユーザーに表示
```

---

## 🔧 開発メモ

### タイムゾーン変換の例

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

### 2025-11-12 最終セッション - アーキテクチャ整理完了 🎉
- **認識の統一**:
  - 旧Behavior/Emotion Aggregator APIは使用しない（個別集計は不要）
  - 統合Aggregator API (`/api/aggregator`) が3つの分析結果を統合
  - Scorer API (`/api/vibe-analysis/scorer`) が既存のLLM処理を担当
- **ドキュメント全面更新**:
  - SPOT_RECORDING_MIGRATION_GUIDE.md を正しいアーキテクチャに修正
  - データフローを5フェーズで明確化（録音→特徴抽出→統合→LLM分析→表示）
  - データベーススキーマを4テーブル構成に整理
  - 残タスクを明確化（Scorer API修正が最優先）
- **進捗**: Phase 1-3 完了（90%）、Phase 4 進行中（残り10%）

### 2025-11-12 13:00-13:50 - Phase 2-3 完了 🎉
- **Emotion Feature Extractor v2修正完了**
- **Vibe Transcriber修正完了**（バグ修正2回）
- **Aggregator API修正完了**（ASR+SED+SER統合）

### 2025-11-12 00:00-01:00
- **Vibe Aggregator API修正完了**: devices.timezone対応 + UTC→ローカル時間変換
- **Behavior Features動作確認**: spot_featuresへのデータ保存成功 🎉
- **データベース修正**: spot_featuresテーブルに不足カラム追加 + RLS無効化
- **トラブルシューティング**:
  - `behavior_extractor_processed_at` カラム不足エラーを発見・修正
  - Row-Level Security (RLS) エラーを発見・無効化
- **次のタスク特定**: Emotion Features v2とVibe Transcriberの修正が必要

### 2025-11-11 最終セッション
- **Phase 1完全完了**: サーバー側API修正を完了
- Vault API: `local_datetime` 削除 + S3パス秒単位精度化（`{HH-MM-SS}` 形式）
- Vibe Transcriber, Behavior Features, Emotion Features: `spot_features` 移行完了
- **重要な発見と修正**: S3パス構造を30分ブロックから秒単位精度に変更（上書き問題を解決）
- 全APIのコミット・プッシュ完了（計8コミット）

### 2025-11-11 22:30
- **方針転換**: `local_datetime` 廃止、UTC統一アーキテクチャに移行
- データベース修正: `local_datetime` カラム削除
- iOSアプリ修正: UTC送信に変更
- 次セッション用のTODOリスト作成

### 2025-11-11 17:00
- Vibe Aggregator API実装完了
- データベーススキーマ作成
- 上流API修正の必要性を特定
