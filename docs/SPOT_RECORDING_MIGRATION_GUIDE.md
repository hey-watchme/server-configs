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

## 📋 進捗状況（2025-11-11 最終更新）

### ✅ Phase 1完了: サーバー側API修正（UTC統一アーキテクチャ）

#### 1. データベース修正
- ✅ `audio_files.local_datetime` カラム削除
- ✅ `spot_features.local_datetime` カラム削除
- ✅ `devices.timezone` カラム存在確認（例: `Asia/Tokyo`）

#### 2. iOSアプリ修正
- ✅ `UploaderService.swift`: `recorded_at` をUTCで送信
- ✅ コミット・プッシュ・ビルド成功確認

#### 3. Vault API修正（完全完了）
- ✅ `local_datetime` 保存処理を削除
- ✅ S3パス構造を変更: `{HH-MM}` → `{HH-MM-SS}` (秒単位精度)
  - 理由: 30分以内の複数録音が上書きされる問題を解決
  - 旧: `files/{device_id}/{YYYY-MM-DD}/{HH-MM}/audio.wav`
  - 新: `files/{device_id}/{YYYY-MM-DD}/{HH-MM-SS}/audio.wav`
- ✅ README.md完全更新（UTC統一・HH-MM-SS形式を反映）
- ✅ コミット: 2件（app.py + README.md）

#### 4. Vibe Transcriber修正
- ✅ `audio_features` → `spot_features` に変更
- ✅ キー変更: `(device_id, date, time_block)` → `(device_id, recorded_at)`
- ✅ コミット完了

#### 5. Behavior Features修正
- ✅ `audio_features` → `spot_features` に変更
- ✅ `audio_files` テーブルから `recorded_at` を取得
- ✅ コミット完了

#### 6. Emotion Features修正
- ✅ `supabase_service.py`: `audio_features` → `spot_features` に変更
- ✅ `main.py`: `audio_files` から `recorded_at` を取得
- ✅ 完全移行完了、コミット: 2件

---

### 🚧 残タスク（Phase 2-3）

#### Phase 2: Aggregator API修正
- ⏳ `devices.timezone` を使ってUTC→ローカル時間に変換
- ⏳ プロンプト生成時にローカル時間情報を含める

#### Phase 3: クライアント側修正
- ⏳ iOSアプリ: 表示時にUTC→ローカル時間変換
- ⏳ Webダッシュボード: 同様

---

## 🎯 次セッションの TODO

### ✅ Phase 1完了: サーバー側API修正

**完了した内容**:
1. ✅ Vault API: `local_datetime` 削除 + S3パス秒単位精度化
2. ✅ Vibe Transcriber: `spot_features` 移行
3. ✅ Behavior Features: `spot_features` 移行
4. ✅ Emotion Features: `spot_features` 移行（完全）

**重要な追加修正**:
- ✅ S3パス構造変更: `{HH-MM-SS}` 形式（30分以内の上書き問題を解決）

---

### 🚀 Phase 2: Aggregator API修正（次のタスク）

#### Task 1: Vibe Aggregator - devices.timezone取得
**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/aggregator/services/data_fetcher.py`

**修正内容**:
```python
import pytz

# Get device timezone
device = supabase.table('devices').select('timezone').eq('device_id', device_id).single().execute()
timezone = pytz.timezone(device.data['timezone'])  # "Asia/Tokyo"

# Convert UTC to local time
recorded_at_utc = spot_feature['recorded_at']  # UTC
local_time = recorded_at_utc.astimezone(timezone)

# Use local_time for prompt generation
hour = local_time.hour
date_str = local_time.strftime('%Y-%m-%d')
time_str = local_time.strftime('%H:%M:%S')
```

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
