# Database Schema & Migrations

WatchMeプロジェクトのデータベーススキーマとマイグレーションファイル

---

## 📁 ディレクトリ構造

```
database/
├── README.md              # このファイル
├── current_schema.sql     # 現在のデータベーススキーマ全体
└── migrations/            # マイグレーションファイル（時系列順）
    ├── 20251109000002_rename_columns_for_consistency.sql
    ├── 20251109080000_fix_audio_aggregator_schema.sql
    └── ...
```

---

## 🗄️ データベース: Supabase (PostgreSQL)

**接続情報**:
- URL: `https://qvtlwotzuzbavrzqhyvt.supabase.co`
- リージョン: ap-southeast-2 (Sydney)

---

## 📊 主要テーブル

### Spot分析（録音ごと）
- `audio_files`: 録音メタデータ
- `spot_features`: 音響・感情・文字起こし特徴量
- `spot_aggregators`: Spot分析用プロンプト
- `spot_results`: Spot分析結果（LLM出力）

### Daily分析（1日の累積）
- `daily_aggregators`: Daily分析用プロンプト
- `daily_results`: Daily分析結果（LLM出力）

### メタデータ
- `devices`: デバイス情報（timezone含む）
- `subjects`: 観測対象者情報（年齢・性別・メモ）

---

## 🚀 マイグレーション実行方法

### 1. Supabase SQLエディタで実行（推奨）

1. https://supabase.com/dashboard にログイン
2. プロジェクト選択: `watchme`
3. 左メニュー「SQL Editor」を開く
4. `migrations/`から該当するSQLファイルの内容をコピー
5. SQLエディタに貼り付けて実行

### 2. ローカルから実行（psqlを使う場合）

```bash
# Supabaseの接続文字列を取得（Dashboard > Settings > Database）
psql "postgresql://postgres:[YOUR-PASSWORD]@[HOST]:5432/postgres" \
  -f migrations/20251115000000_recreate_daily_results_table.sql
```

---

## 📝 マイグレーションファイルの命名規則

**形式**: `YYYYMMDDHHmmss_description.sql`

**例**:
- `20251115000000_recreate_daily_results_table.sql`
- `20251113060000_rename_summary_tables_and_create_aggregators.sql`

---

## 🔄 新しいマイグレーションの作成手順

### 1. ファイル作成

```bash
cd /Users/kaya.matsumoto/projects/watchme/server-configs/database/migrations/

# 現在のタイムスタンプで新しいファイルを作成
touch $(date +%Y%m%d%H%M%S)_add_new_column.sql
```

### 2. SQLを記述

```sql
-- Migration: Add new column to spot_results
-- Date: 2025-11-16

ALTER TABLE spot_results
ADD COLUMN IF NOT EXISTS new_column TEXT;

COMMENT ON COLUMN spot_results.new_column IS 'Description of new column';
```

### 3. Supabaseで実行

SQLエディタで実行して動作確認

### 4. コミット

```bash
git add migrations/20251116000000_add_new_column.sql
git commit -m "db: add new_column to spot_results"
git push origin main
```

---

## 🗂️ current_schema.sql の更新

スキーマ全体が変更された場合、`current_schema.sql`を更新：

```bash
# Supabase Dashboard > Database > Schema Visualizer
# または pg_dump で取得

# 手動でcurrent_schema.sqlを編集
# コミット
git add current_schema.sql
git commit -m "db: update current schema"
git push origin main
```

---

## ⚠️ 重要な注意事項

### RLS (Row Level Security)

**内部API専用テーブル（RLS無効）**:
- `spot_features`
- `spot_aggregators`
- `spot_results`
- `daily_aggregators`
- `daily_results`

**ユーザーアクセステーブル（RLS有効）**:
- `audio_files` (device_idでフィルタ)
- `devices` (user_idでフィルタ)
- `subjects` (user_idでフィルタ)

### 外部キー制約

- `devices.subject_id` → `subjects.subject_id`
- `audio_files.device_id` → `devices.device_id`
- `spot_features.device_id, recorded_at` → `audio_files.device_id, recorded_at`

---

## 📚 関連ドキュメント

- **システム概要**: [../docs/README.md](../docs/README.md)
- **処理フロー**: [../docs/PROCESSING_ARCHITECTURE.md](../docs/PROCESSING_ARCHITECTURE.md)
- **技術仕様**: [../docs/TECHNICAL_REFERENCE.md](../docs/TECHNICAL_REFERENCE.md)

---

**最終更新**: 2025-11-16
