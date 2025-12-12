# マイグレーション適用手順

## 📋 最新のマイグレーション: 20251125000000_add_auth_provider_to_users.sql

### ✅ Supabaseダッシュボードで適用する手順

1. **Supabaseダッシュボードを開く**
   - https://supabase.com/dashboard/project/qvtlwotzuzbavrzqhyvt

2. **SQL Editorに移動**
   - 左メニュー: `SQL Editor` をクリック

3. **マイグレーションSQLをコピー**
   ```bash
   cat /Users/kaya.matsumoto/projects/watchme/server-configs/database/migrations/20251125000000_add_auth_provider_to_users.sql
   ```

4. **新しいクエリを作成**
   - `+ New query` ボタンをクリック
   - マイグレーションSQLを貼り付け

5. **実行**
   - `RUN` ボタンをクリック
   - エラーがないことを確認

6. **結果を確認**
   - `Table Editor` → `users` テーブルを開く
   - `auth_provider` カラムが追加されていることを確認
   - 既存のデータに `email` または `anonymous` が設定されていることを確認

---

## 🔄 マイグレーション内容

### 追加されるカラム
- **auth_provider** (TEXT, NOT NULL)
  - デフォルト値: `'email'`
  - CHECK制約: `anonymous`, `email`, `google`, `apple`, `microsoft`, `github`, `facebook`, `twitter`
  - インデックス: `idx_users_auth_provider`

### 既存データの更新
- `email = 'anonymous'` → `auth_provider = 'anonymous'`
- その他すべて → `auth_provider = 'email'`

---

## 🚨 トラブルシューティング

### エラー: "column already exists"
```sql
-- auth_providerがすでに存在する場合はスキップ
ALTER TABLE public.users DROP COLUMN IF EXISTS auth_provider;
-- その後、マイグレーションを再実行
```

### ロールバックが必要な場合
```sql
DROP INDEX IF EXISTS idx_users_auth_provider;
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_auth_provider_check;
ALTER TABLE public.users DROP COLUMN IF EXISTS auth_provider;
```

---

## 📝 適用後のタスク

1. ✅ マイグレーション実行
2. ✅ `current_schema.sql` の更新
3. ✅ iOSアプリのコード更新（auth_provider を保存するロジック追加）
4. ✅ Git commit & push
