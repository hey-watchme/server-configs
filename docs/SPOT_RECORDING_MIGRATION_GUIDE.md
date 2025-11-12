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

### ✅ Phase 1完了: サーバー側API修正（UTC統一アーキテクチャ）

#### 1. データベース修正
- ✅ `audio_files.local_datetime` カラム削除
- ✅ `spot_features.local_datetime` カラム削除
- ✅ `spot_features` テーブルに不足カラム追加:
  - `behavior_extractor_status`, `behavior_extractor_processed_at`
  - `emotion_extractor_status`, `emotion_extractor_processed_at`
  - `vibe_transcriber_status`, `vibe_transcriber_processed_at`
- ✅ `spot_features` テーブルのRLS無効化（内部API専用テーブルのため）
- ✅ `devices.timezone` カラム存在確認（例: `Asia/Tokyo`）

#### 2. iOSアプリ修正
- ✅ `UploaderService.swift`: `recorded_at` をUTCで送信
- ✅ コミット・プッシュ・ビルド成功確認

#### 3. Vault API修正（完全完了）
- ✅ `local_datetime` 保存処理を削除
- ✅ S3パス構造を変更: `{HH-MM}` → `{HH-MM-SS}` (秒単位精度)
- ✅ README.md完全更新

#### 4. Vibe Transcriber修正（完了）
- ✅ `audio_features` → `spot_features` に変更
- ✅ キー変更: `(device_id, date, time_block)` → `(device_id, recorded_at)`
- ✅ コミット完了

#### 5. Behavior Features修正（完了・動作確認済み）
- ✅ `audio_features` → `spot_features` に変更
- ✅ `save_to_spot_features()` 関数実装
- ✅ `audio_files` ステータス更新処理追加
- ✅ **本番動作確認済み**: spot_featuresにデータ保存成功 🎉

#### 6. Aggregator API修正（完了）
- ✅ `data_fetcher.py`: `get_device_timezone()` 実装
- ✅ `prompt_generator.py`: pytzでUTC→ローカル時間変換実装
- ✅ `spot_aggregator.py`: timezone_str引数に変更
- ✅ `requirements.txt`: pytz追加
- ✅ Dockerビルド・ローカルテスト成功
- ✅ コミット・プッシュ・本番デプロイ完了

---

### 🚧 残タスク（Phase 2-3）

#### Phase 2: Feature Extractor API修正（残り2つ）
- ⏳ **Emotion Feature Extractor v2**: `spot_features` 対応が必要
  - 現状: `emotion_opensmile` テーブル使用（旧テーブル）
  - 修正: Behavior Features v3と同様の実装に変更
- ⏳ **Vibe Transcriber**: 動作確認が必要
  - コードは修正済みだが本番動作未確認

#### Phase 2: Aggregator API修正（残り2つ）
- ⏳ **Behavior Aggregator**: `devices.timezone` 対応
- ⏳ **Emotion Aggregator**: `devices.timezone` 対応

#### Phase 3: クライアント側修正
- ⏳ iOSアプリ: 表示時にUTC→ローカル時間変換
- ⏳ Webダッシュボード: 同様

---

## 🎯 次セッションの TODO

### ✅ 完了済み

1. ✅ Vault API: `local_datetime` 削除 + S3パス秒単位精度化
2. ✅ Vibe Transcriber: `spot_features` 移行（コード修正済み、動作未確認）
3. ✅ Behavior Features: `spot_features` 移行 + 本番動作確認済み 🎉
4. ✅ Aggregator API: devices.timezone対応 + UTC→ローカル時間変換

---

### 🚀 次のタスク（優先度順）

#### 1. Emotion Feature Extractor v2の修正（最優先）

**現状**: 旧アーキテクチャ（タイムブロック方式）のまま
- `emotion_opensmile` テーブル使用（旧テーブル）
- `date`, `time_block` ベースの保存

**修正内容**: Behavior Features v3と同様の実装に変更
- `supabase_service.py`: 完全書き換え（`spot_features`対応）
- `main.py`: `process_emotion_features()` を修正
- `audio_files`: ステータス更新処理追加

**参考実装**: `/Users/kaya.matsumoto/projects/watchme/api/behavior-analysis/feature-extractor-v3/main_supabase.py`

#### 2. Vibe Transcriberの動作確認

**現状**: コード修正済みだが本番動作未確認

**確認手順**:
1. 録音を実行
2. audio_filesの`transcriptions_status`を確認
3. spot_featuresの`vibe_transcriber_result`を確認

#### 3. Behavior Aggregator修正

**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/behavior-analysis/aggregator`

**修正内容**: Aggregator APIと同様に`devices.timezone`対応

#### 4. Emotion Aggregator修正

**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/emotion-analysis/aggregator`

**修正内容**: Aggregator APIと同様に`devices.timezone`対応

---

### Phase 3: クライアント側の修正

#### ✅ Task 6: iOSアプリ表示ロジック
**対象**:
- ダッシュボード画面
- 録音履歴画面

**修正内容**:
```swift
// Get device timezone
let device = // Supabaseから取得
let timezone = TimeZone(identifier: device.timezone)  // "Asia/Tokyo"

// Convert UTC to local time
let recordedAtUTC = // Supabaseから取得
let localTime = recordedAtUTC.convertTo(timezone: timezone)

// Display
Text(localTime.formatted())
```

---

## 🗄️ データベーススキーマ（最終版）

### audio_files
```sql
CREATE TABLE audio_files (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC
  file_path TEXT NOT NULL,
  transcriptions_status TEXT DEFAULT 'pending',
  behavior_features_status TEXT DEFAULT 'pending',
  emotion_features_status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (device_id, recorded_at)
);
```

### spot_features
```sql
CREATE TABLE spot_features (
  device_id TEXT NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,  -- UTC
  vibe_transcriber_result TEXT,
  behavior_extractor_result JSONB,
  emotion_extractor_result JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (device_id, recorded_at)
);
```

### devices（既存）
```sql
-- timezone カラムを使用
SELECT device_id, timezone FROM devices;
-- 例: 9f7d6e27-..., Asia/Tokyo
```

---

## 📊 データフロー（最終版）

```
【録音】
iOS → recorded_at (UTC) → Vault API → audio_files (UTC保存)

【分析】
Lambda → 3つのFeatures API → spot_features (UTC保存)

【集計】
Aggregator API:
  1. spot_features から recorded_at (UTC) 取得
  2. devices.timezone 取得
  3. UTC → ローカル時間に変換
  4. プロンプト生成（時間情報を含む）
  5. spot_aggregators に保存

【表示】
iOS/Web:
  1. recorded_at (UTC) 取得
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

### 2025-11-12 00:00-01:00（このセッション）
- **Aggregator API修正完了**: devices.timezone対応 + UTC→ローカル時間変換
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
- Aggregator API実装完了
- データベーススキーマ作成
- 上流API修正の必要性を特定
