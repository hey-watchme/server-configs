# Database Migrations

このディレクトリには、WatchMeプロジェクトのデータベースマイグレーションファイルが含まれています。

## 📋 マイグレーション一覧

### Phase 1: 新テーブル作成（2025-11-09）

| ファイル | 説明 | ステータス |
|---------|------|----------|
| `001_create_timeblock_vibe.sql` | timeblock_vibeテーブル作成（気分分析3ステップ統合） | 未実行 |
| `002_alter_dashboard_summary.sql` | dashboard_summaryにステータス・タイムスタンプ追加 | 未実行 |

## 🚀 実行手順

### 1. Supabaseへアクセス

```
https://supabase.com/dashboard/project/qvtlwotzuzbavrzqhyvt
```

### 2. SQL Editorを開く

左メニュー → SQL Editor → New query

### 3. マイグレーションを順番に実行

```bash
# 001_create_timeblock_vibe.sql の内容をコピー＆ペースト
# Run をクリック

# 002_alter_dashboard_summary.sql の内容をコピー＆ペースト
# Run をクリック
```

### 4. 実行結果を確認

```sql
-- テーブル作成確認
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('timeblock_vibe', 'dashboard_summary');

-- カラム確認
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'timeblock_vibe'
ORDER BY ordinal_position;

-- 制約確認
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'timeblock_vibe';
```

## ✅ テストデータ挿入

マイグレーション成功後、以下のテストデータで動作確認：

```sql
-- テストデータ1: 正常な完了データ
INSERT INTO timeblock_vibe (
  device_id, date, time_block, status,
  transcription, prompt, vibe_score, summary
) VALUES (
  '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93',
  '2025-11-09',
  '09-00',
  'completed',
  'おはよう。今日は良い天気だね。',
  'テスト用プロンプト内容',
  75,
  'ポジティブな会話が多く、穏やかな雰囲気。'
);

-- テストデータ2: SKIPデータ
INSERT INTO timeblock_vibe (
  device_id, date, time_block, status, summary
) VALUES (
  '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93',
  '2025-11-09',
  '00-00',
  'skipped',
  '夜間休止時間（23:00-05:59）'
);

-- テストデータ3: 失敗データ
INSERT INTO timeblock_vibe (
  device_id, date, time_block, status,
  failure_reason, error_message
) VALUES (
  '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93',
  '2025-11-09',
  '10-00',
  'failed',
  'quota_exceeded',
  'Azure Speech API quota exceeded'
);

-- データ確認
SELECT
  time_block, status, vibe_score,
  LEFT(summary, 30) as summary_preview
FROM timeblock_vibe
WHERE device_id = '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93'
  AND date = '2025-11-09'
ORDER BY time_block;
```

## 🚨 CHECK制約のテスト

以下のSQLは**エラーになるはず**（制約が正しく動作している証拠）：

```sql
-- ❌ completed状態なのにsummaryがない（エラーになるはず）
INSERT INTO timeblock_vibe (
  device_id, date, time_block, status,
  transcription, prompt, vibe_score
) VALUES (
  '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93',
  '2025-11-09',
  '11-00',
  'completed',
  'テスト',
  'テスト',
  75
  -- summary がない → CHECK制約違反
);

-- ❌ failed状態なのにfailure_reasonがない（エラーになるはず）
INSERT INTO timeblock_vibe (
  device_id, date, time_block, status
) VALUES (
  '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93',
  '2025-11-09',
  '12-00',
  'failed'
  -- failure_reason がない → CHECK制約違反
);

-- ❌ skipped状態なのにvibe_scoreがある（エラーになるはず）
INSERT INTO timeblock_vibe (
  device_id, date, time_block, status, vibe_score
) VALUES (
  '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93',
  '2025-11-09',
  '13-00',
  'skipped',
  75
  -- skippedなのにvibe_scoreがある → CHECK制約違反
);
```

## 📝 マイグレーション実行後のチェックリスト

- [ ] `001_create_timeblock_vibe.sql` 実行完了
- [ ] `002_alter_dashboard_summary.sql` 実行完了
- [ ] テーブル作成確認クエリで存在確認
- [ ] テストデータ3件挿入成功
- [ ] CHECK制約テストで適切にエラーが発生
- [ ] updated_atトリガー動作確認（UPDATEして確認）

## 🔄 ロールバック

万が一、ロールバックが必要な場合：

```sql
-- 順番を逆にして削除
DROP TABLE IF EXISTS timeblock_vibe CASCADE;

ALTER TABLE dashboard_summary
  DROP COLUMN IF EXISTS status,
  DROP COLUMN IF EXISTS prompt_generated_at,
  DROP COLUMN IF EXISTS analyzed_at;

DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
```

## 📚 参考資料

詳細な設計思想とデータフロー：
- `/server-configs/docs/DATABASE_REFACTORING_PLAN.md`
