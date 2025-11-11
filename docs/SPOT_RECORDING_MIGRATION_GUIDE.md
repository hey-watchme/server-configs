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

## 📋 進捗状況（2025-11-11 22:30）

### ✅ 完了した作業

#### 1. データベース修正
- ✅ `audio_files.local_datetime` カラム削除
- ✅ `spot_features.local_datetime` カラム削除

#### 2. iOSアプリ修正
- ✅ `UploaderService.swift`: `recorded_at` をUTCで送信するように変更
- ✅ コミット・プッシュ完了
- ✅ ビルド成功確認

#### 3. 確認済み
- ✅ `devices` テーブルに `timezone` カラムが存在（例: `Asia/Tokyo`）

---

### 🚧 進行中・未完了

#### 4. Vault API修正（次のタスク）
- ⏳ `local_datetime` の保存処理を削除
- ⏳ README.md更新（UTC統一を反映）

#### 5. 3つのFeatures API修正
- ⏳ Vibe Transcriber: `audio_features` → `spot_features` に変更
- ⏳ Behavior Features: `audio_features` → `spot_features` に変更
- ⏳ Emotion Features: `audio_features` → `spot_features` に変更

#### 6. Aggregator API修正
- ⏳ `devices.timezone` を取得してローカル時間に変換
- ⏳ プロンプト生成時に時間情報を正しく反映

#### 7. 表示ロジック修正
- ⏳ iOSアプリ: UTCをローカル時間に変換して表示
- ⏳ Webダッシュボード: 同様

---

## 🎯 次セッションの TODO

### Phase 1: サーバー側の修正（優先）

#### ✅ Task 1: Vault API修正
**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/vault/app.py`

**修正内容**:
```python
# Before:
audio_file_data = {
    "device_id": device_id,
    "recorded_at": recorded_at.isoformat(),
    "local_datetime": recorded_at.isoformat(),  # ← 削除
    "file_path": s3_key,
    ...
}

# After:
audio_file_data = {
    "device_id": device_id,
    "recorded_at": recorded_at.isoformat(),  # UTC
    "file_path": s3_key,
    ...
}
```

**確認方法**:
```bash
cd /Users/kaya.matsumoto/projects/watchme/api/vault
git diff app.py
python3 -m py_compile app.py
git commit && git push
```

---

#### ✅ Task 2: Vibe Transcriber修正
**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/transcriber-v2/app/services.py`

**修正内容**:
```python
# audio_features → spot_features に変更
# キー: (device_id, recorded_at)

data = {
    "device_id": device_id,
    "recorded_at": audio_file['recorded_at'],  # UTC
    "vibe_transcriber_result": transcription_text,
    "vibe_transcriber_status": "completed",
    "vibe_transcriber_processed_at": datetime.now(timezone.utc).isoformat()
}

response = self.supabase.table('spot_features').upsert(data).execute()
```

**テスト**:
1. iOSアプリで録音
2. Supabase確認: `spot_features.vibe_transcriber_result` にデータがあるか

---

#### ✅ Task 3: Behavior Features修正
**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/behavior-analysis/features/`

同様のパターン:
- `audio_features` → `spot_features`
- `behavior_extractor_result` カラムに保存

---

#### ✅ Task 4: Emotion Features修正
**ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/emotion-analysis/features/`

同様のパターン:
- `audio_features` → `spot_features`
- `emotion_extractor_result` カラムに保存

---

### Phase 2: Aggregator API修正

#### ✅ Task 5: devices.timezone取得
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

### 2025-11-11 22:30
- **方針転換**: `local_datetime` 廃止、UTC統一アーキテクチャに移行
- データベース修正: `local_datetime` カラム削除
- iOSアプリ修正: UTC送信に変更
- 次セッション用のTODOリスト作成

### 2025-11-11 17:00
- Aggregator API実装完了
- データベーススキーマ作成
- 上流API修正の必要性を特定
