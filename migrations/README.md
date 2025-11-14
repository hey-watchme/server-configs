# WatchMe Migrations ディレクトリ

**最終更新**: 2025-11-10

---

## 📂 ディレクトリ構成

```
migrations/
├── README.md                # このファイル
├── HANDOVER_MEMO.md        # セッション引き継ぎメモ（最重要）
├── archive/                # 古いSQL設計ドキュメント（参考用）
└── docs/                   # 技術ドキュメント（参考用）
```

---

## 🎯 重要なファイル

### **HANDOVER_MEMO.md**
- **目的**: セッション間の引き継ぎ情報
- **内容**:
  - 次回の作業開始地点
  - 完了したタスク
  - 進捗状況
  - 重要な決定事項
- **更新**: 各セッション終了時

---

## 📚 その他のファイル

### `archive/` - 古い設計ドキュメント
- ❌ **これらは実行されていません**
- ❌ **参考用として保存されているだけです**
- 初期の設計案や、手動で実行したSQLの記録

### `docs/` - 技術ドキュメント
- 参考用のドキュメント
- 古い情報の可能性あり
- 最新情報は実際のコードを確認すること

---

## ⚠️ 重要な注意事項

### 実際のマイグレーション履歴はこちら：
```
/Users/kaya.matsumoto/projects/watchme/supabase/migrations/
```

**Supabase CLIが管理する正式なマイグレーション履歴**：
- `20251109000002_rename_columns_for_consistency.sql`
- `20251109080000_fix_audio_aggregator_schema.sql`
- `20251109222311_restore_vibe_aggregator_columns.sql`
- `20251109231856_rename_transcriber_to_vibe_transcriber.sql`

### このディレクトリ（server-configs/migrations/）の役割
- ✅ セッション引き継ぎ情報の保存
- ✅ 参考ドキュメントの保管
- ❌ 実際のマイグレーション管理ではない

---

## 🔍 マイグレーション実行方法

```bash
cd /Users/kaya.matsumoto/projects/watchme

# マイグレーションファイルを作成
supabase migration new [description]

# ドライラン（確認のみ）
supabase db push --dry-run

# 実行
supabase db push
```

---

**新しいマイグレーションは必ず `/supabase/migrations/` に作成してください。**
