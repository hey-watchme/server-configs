# 🔄 セッション引き継ぎメモ

**作成日時**: 2025-11-09 (最終更新)
**コンテキスト使用率**: 176k/200k tokens (88%)

---

## 📍 次回の開始地点

**Phase 3 開始！Vibe Scorer API の修正**

### 次の作業対象: Vibe Scorer API
**ディレクトリ**: `/Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/scorer`

### ⚠️ Vibe Aggregatorの特殊性（重要）

このAPIは**3つの異なる責務**を持つエンドポイントで構成されています：

| エンドポイント | 役割 | 現在の保存先 | 新しい保存先 | 作業順序 |
|---------------|------|------------|------------|---------|
| `/generate-timeblock-prompt` | 30分単位プロンプト生成 | `dashboard` | `audio_aggregator.vibe_aggregator_result` | **1. 最初** |
| `/generate-dashboard-summary` | 累積分析プロンプト生成 | `dashboard_summary` | （後で検討） | 2. 次 |
| `/create-failed-record` | 失敗/スキップレコード作成 | `dashboard` | Vibe Scorer APIへ移動予定 | 3. 最後 |

### 📋 作業計画（Step by Step）

#### Step 1: `/generate-timeblock-prompt`の修正（最優先）
1. ✅ マイグレーション作成：`audio_aggregator.vibe_aggregator_result`カラムを復活
2. ✅ 読み込み元変更：`vibe_whisper.transcription` → `audio_features.transcriber_result`
3. ✅ 保存先変更：`dashboard.prompt` → `audio_aggregator.vibe_aggregator_result`
4. ✅ README.md更新
5. ✅ デプロイ・動作確認

#### Step 2: `/generate-dashboard-summary`の分離（次のフェーズ）
- 新しいAPI「Dashboard Summary API」を作成
- `/generate-dashboard-summary`エンドポイントを移動
- Lambda summary-workerの呼び出し先を更新

#### Step 3: `/create-failed-record`の移動（最後）
- Vibe Scorer APIに移動
- Lambda audio-workerのエラーハンドリングを更新

### 🎯 設計方針の決定事項（2025-11-09）

**前提**：ユーザー数ゼロ、ダウンタイム無制限、**理想的なアーキテクチャを優先**

**決定事項**：
1. **妥協なし**：既存システムとの互換性よりも理想的な設計を優先
2. **マイクロサービス分離**：責務ごとにAPIを分割する方針
3. **段階的移行**：1エンドポイントずつ確実に移行
4. **テーブル設計の復活**：削除した`audio_aggregator.vibe_aggregator_result`カラムを復活させる

### 🔤 命名規則の統一（2025-11-09 決定）

**確定した命名パターン**: `{domain}_{technology}_result`

#### audio_features テーブル
- ✅ `vibe_transcriber_result` (domain: vibe, tech: transcriber) ← **修正完了！**
- `behavior_extractor_result` (domain: behavior, tech: extractor)
- `emotion_extractor_result` (domain: emotion, tech: extractor)

#### audio_aggregator テーブル
- `vibe_aggregator_result` (domain: vibe, tech: aggregator)
- `behavior_aggregator_result` (domain: behavior, tech: aggregator)
- `emotion_aggregator_result` (domain: emotion, tech: aggregator)

**3つのドメイン**: vibe, behavior, emotion
**3つの技術層**: transcriber/extractor, aggregator, scorer

---

## ✅ 今回のセッション（Session 7）で完了したこと

### 1. カラム名の命名規則統一完了 🎉

**マイグレーション**:
- ✅ `20251109231856_rename_transcriber_to_vibe_transcriber.sql` 実行完了
- ✅ `audio_features.transcriber_result` → `vibe_transcriber_result`
- ✅ `audio_features.transcriber_status` → `vibe_transcriber_status`
- ✅ `audio_features.transcriber_processed_at` → `vibe_transcriber_processed_at`

**Vibe Transcriber API修正**:
- ✅ `app/services.py`: 書き込み先カラム名変更
- ✅ `README.md`: v2.1.0として変更履歴追記
- ✅ GitHub push完了（デプロイ成功、実行時間: 5分22秒）

**Vibe Aggregator API修正**:
- ✅ `timeblock_endpoint.py`: 読み込み元カラム名変更
- ✅ `README.md`: v7.1.0として変更履歴追記
- ✅ GitHub push完了（デプロイ成功、実行時間: 3分39秒）

**重要な成果**:
- ✅ 命名規則 `{domain}_{technology}_result` への完全移行完了
- ✅ すべてのカラム名が統一され、一貫性が確保された

---

## ✅ 前回のセッション（Session 6）で完了したこと

### 1. Vibe Aggregator API（`/generate-timeblock-prompt`エンドポイント）完了 🎉

**マイグレーション**:
- ✅ `20251109222311_restore_vibe_aggregator_columns.sql` 実行完了
- ✅ `audio_aggregator.vibe_aggregator_result` カラムを復活（TEXT型）
- ✅ `audio_aggregator.vibe_aggregator_processed_at` カラムを追加

**コード修正**:
- ✅ `timeblock_endpoint.py` 修正完了
  - `get_whisper_data()`: `vibe_whisper.transcription` → `audio_features.transcriber_result`
  - `get_sed_data()`: `behavior_yamnet.events` → `audio_features.behavior_extractor_result`
  - `get_opensmile_data()`: `emotion_opensmile.selected_features_timeline` → `audio_features.emotion_extractor_result`
  - `save_prompt_to_dashboard()`: `dashboard.prompt` → `audio_aggregator.vibe_aggregator_result`
- ✅ `timeblock_endpoint_v2.py` 修正完了
  - ステータス更新関数呼び出しを削除（Features APIが既に管理しているため）
- ✅ README.md更新完了（v7.0.0として変更履歴追記）
- ✅ GitHub push完了（デプロイ成功確認済み）

**重要な設計決定**:
- **1日1レコード**：`audio_aggregator`のPrimary Key `(device_id, date)`で累積更新
- **ステータス管理の責務分離**：Features APIが自分でステータスを管理、Aggregatorは不要
- **段階的移行**：`/generate-timeblock-prompt`のみ修正、他のエンドポイントは次フェーズ

---

## ✅ 前回のセッション（Session 5）で完了したこと

### 1. Emotion Aggregator API 完了 🎉
- ✅ `supabase_service.py`修正完了
- ✅ 読み込み元変更: `emotion_opensmile` → `audio_features.emotion_extractor_result`
- ✅ 保存先変更: `emotion_opensmile_summary` → `audio_aggregator.emotion_aggregator_result`
- ✅ `opensmile_aggregator.py`修正完了
- ✅ README.md更新完了（v6.0.0として変更履歴追記）
- ✅ GitHub push完了（デプロイ成功、実行時間: 4分25秒）

---

## ✅ 前回のセッション（Session 4）で完了したこと

### 1. audio_aggregatorテーブルの設計修正 🎉
- ✅ **設計ミス修正**: `time_block`カラムを削除（30分単位は不要）
- ✅ **Primary Key変更**: `(device_id, date, time_block)` → `(device_id, date)`
- ✅ **1日1レコード**で累積更新する設計に修正
- ✅ 不要カラム削除: `behavior_aggregator_summary`, `vibe_aggregator_*`, `context_data`, `status`, `error_message`
- ✅ マイグレーション実行完了: `20251109080000_fix_audio_aggregator_schema.sql`

**重要な設計変更**:
- `summary_ranking`はDBに保存せず、アプリ側で`time_blocks`から計算する
- タイムブロック単位のデータは`audio_features`に保存（素材）
- 累積分析結果は`audio_aggregator`に保存（最終成果物、1日1レコード）

### 2. Behavior Aggregator API 完了 🎉
- ✅ `sed_aggregator.py`修正完了
- ✅ 読み込み元変更: `behavior_yamnet` → `audio_features.behavior_extractor_result`
- ✅ 保存先変更: `behavior_summary` → `audio_aggregator.behavior_aggregator_result`
- ✅ `time_blocks`のみ保存（`summary_ranking`は保存しない）
- ✅ README.md更新完了
- ✅ GitHub push完了（デプロイ済み、実行時間: 5分8秒）

### 3. GitHub CLI セットアップ完了
- ✅ GitHub CLI (gh) インストール・認証完了
- ✅ `~/.zshrc`にトークン永続化
- ✅ `gh run list`, `gh run watch`でデプロイ監視可能に
- ✅ CLAUDE.mdにCLIツール使用方針を追加

---

## ✅ 前回のセッション（Session 3）で完了したこと

### 1. Vibe Transcriber API (v2) 完了 🎉
- ✅ `app/services.py`修正完了
- ✅ テーブル変更: `vibe_whisper` → `audio_features`
- ✅ 新カラム: `transcriber_result`（TEXT型）, `transcriber_status`, `transcriber_processed_at`
- ✅ README.md更新完了
- ✅ GitHub push完了（デプロイ済み）

**重要**: Transcriber APIはTEXT型を使用（Behavior/EmotionはJSONB型）

### 2. Phase 1（Features API群）完了！
- ✅ Behavior Features API (v3)
- ✅ Emotion Features API (v3)
- ✅ Vibe Transcriber API (v2)

**次はPhase 2（Aggregator API群）に進みます**

---

## ✅ 前回のセッション（Session 2）で完了したこと

### 1. Behavior Features API (v3) 完了
- ✅ `main_supabase.py`修正完了
- ✅ テーブル変更: `behavior_yamnet` → `audio_features`
- ✅ 新カラム: `behavior_extractor_result`, `behavior_extractor_status`, `behavior_extractor_processed_at`
- ✅ README.md更新完了
- ✅ GitHub push完了（デプロイ済み）

### 2. Emotion Features API (v3) 完了
- ✅ `supabase_service.py`修正完了
- ✅ テーブル変更: `emotion_opensmile` → `audio_features`
- ✅ 新カラム: `emotion_extractor_result`, `emotion_extractor_status`, `emotion_extractor_processed_at`
- ✅ README.md更新完了
- ✅ GitHub push完了（デプロイ済み）

### 3. ドキュメント改善
- ✅ HANDOVER_MEMO.md修正（ローカルテスト不要を明記）

---

## ✅ 前回のセッション（Session 1）で完了したこと

### 1. データベーススキーマ変更（完了）
- ✅ `002_rename_columns_for_consistency.sql` 作成・実行完了
- ✅ Supabase CLI経由でマイグレーション実行
- ✅ カラム名を統一（`sed_result` → `behavior_extractor_result` 等）

### 2. Supabase CLI環境構築（完了）
- ✅ Supabase CLIインストール（`brew install supabase/tap/supabase`）
- ✅ プロジェクトリンク完了（`supabase link --project-ref qvtlwotzuzbavrzqhyvt`）
- ✅ マイグレーション実行手順確立

### 3. ドキュメント整備（完了）
- ✅ `NAMING_CONVENTIONS.md` 作成（ネーミング規則の統一）
- ✅ `TABLE_SCHEMA_REFERENCE.md` 作成（テーブル構造リファレンス）
- ✅ `OPERATIONS_GUIDE.md` にSupabase CLI使用方法を追加
- ✅ `README.md` にデータベース管理セクション追加
- ✅ 不要なマイグレーションファイルを削除（7ファイル → 5ファイルに整理）

---

## 📊 現在のmigrationsディレクトリ構成

```
/Users/kaya.matsumoto/projects/watchme/server-configs/migrations/
├── 001_create_audio_features_tables.sql      # テーブル作成（参照用）
├── 002_rename_columns_for_consistency.sql    # カラム名統一（実行済み）
├── 007_status_management_design.md           # ステータス管理設計
├── API_MIGRATION_PLAN.md                     # API修正計画
├── NAMING_CONVENTIONS.md                     # ★ ネーミング規則（必読）
├── TABLE_SCHEMA_REFERENCE.md                 # ★ テーブル構造リファレンス
└── HANDOVER_MEMO.md                          # このファイル
```

---

## 🎯 次回やること

### Phase 1: Vibe Transcriber API (v2) の修正

#### 作業内容
1. **データベース書き込み先の変更**
   - 現在：`vibe_whisper`テーブル
   - 変更後：`audio_features.transcriber_result` カラム（TEXT型）
   - **旧テーブルへの書き込みは削除**（並行運用なし）

2. **ステータス管理**
   - `audio_features.transcriber_status = 'completed'` に更新
   - `audio_features.transcriber_processed_at = NOW()` を設定

3. **データ型の違いに注意**
   - Behavior/Emotion: JSONB型
   - **Transcriber: TEXT型**（文字起こし結果はシンプルなテキスト）

#### 修正箇所
```bash
cd /Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/transcriber-v2
```

**確認すべきファイル**:
1. Supabase接続部分
2. `vibe_whisper`テーブルへの書き込み処理
3. エンドポイント定義（FastAPI）

**修正パターン**:
```python
# 旧コード（削除）
supabase.table('vibe_whisper').upsert({...})

# 新コード（追加）
supabase.table('audio_features').upsert({
    'device_id': device_id,
    'date': date,
    'time_block': time_block,
    'transcriber_result': transcription_text,  # TEXT形式（注意：JSONBではない）
    'transcriber_status': 'completed',
    'transcriber_processed_at': datetime.now().isoformat()
})
```

---

## 🚀 その後の作業計画

### Phase 2: Emotion Features API (v2)
- エンドポイント：`/emotion-analysis/feature-extractor/`
- 新テーブル：`audio_features.emotion_extractor_result`

### Phase 3: Vibe Transcriber API (v2)
- エンドポイント：`/vibe-analysis/transcriber/`
- 新テーブル：`audio_features.transcriber_result`（TEXT型）

### Phase 4: Nginx設定更新
- エンドポイント名を統一

### Phase 5: Lambda関数更新
- 環境変数のエンドポイントURL更新

---

## 📚 必読ドキュメント

### 開始前に必ず読むこと
1. **NAMING_CONVENTIONS.md** - 命名規則の統一（最重要）
2. **TABLE_SCHEMA_REFERENCE.md** - テーブル構造の理解
3. **API_MIGRATION_PLAN.md** - 全体の修正計画

### 参考資料
- **007_status_management_design.md** - ステータス管理の設計思想
- **OPERATIONS_GUIDE.md - データベースマイグレーション** - Supabase CLI使用方法

---

## ⚠️ 重要な決定事項

### 1. ネーミング規則の統一
- **APIエンドポイント**: `-er`形式（`feature-extractor`, `transcriber`, `aggregator`, `scorer`）
- **データベースカラム**: `{api役割}_result`（`behavior_extractor_result`）
- **詳細**: `NAMING_CONVENTIONS.md`

### 2. データ型の選択
- **TEXT**: シンプルなテキスト（`transcriber_result`, `vibe_aggregator_result`）
- **JSONB**: 構造化データ（`behavior_extractor_result`, `emotion_extractor_result`）
- **DOUBLE PRECISION**: 頻繁に検索する数値（`vibe_score`）
- **詳細**: `TABLE_SCHEMA_REFERENCE.md`

### 3. 並行運用の廃止
- **旧方針**: 新旧テーブルに両方書き込み
- **新方針**: 直接置き換え（ユーザーがいないため）
- **理由**: 実装コスト削減、切り替えタイミング不要

### 4. Supabase CLI活用
- **スキーマ変更**: Supabase CLI（`supabase db push`）
- **データ確認**: Supabaseダッシュボード（SQL Editor）
- **詳細**: `OPERATIONS_GUIDE.md - データベースマイグレーション`

---

## 🔧 Supabase CLI使用方法（クイックリファレンス）

### マイグレーション実行
```bash
cd /Users/kaya.matsumoto/projects/watchme

# Dry Run（確認のみ）
SUPABASE_ACCESS_TOKEN=sbp_b859dc85180b5434daf2381b525147bb9d0a637d supabase db push --dry-run

# 実行
SUPABASE_ACCESS_TOKEN=sbp_b859dc85180b5434daf2381b525147bb9d0a637d supabase db push --yes
```

### マイグレーションファイル配置
```
supabase/migrations/
└── 20251109HHMMSS_{説明}.sql  # タイムスタンプ付き
```

---

## 📊 進捗状況

```
✅ Phase 0: データベーステーブル設計・作成
✅ Phase 0.5: Supabase CLI環境構築
✅ Phase 0.6: ドキュメント整備

✅ Phase 1: Features API群 (3/3 完了) 🎉
✅ Behavior Features API (v3)
✅ Emotion Features API (v3)
✅ Vibe Transcriber API (v2)

Phase 2: Aggregator API群 (3/3 完了) 🎉
✅ Behavior Aggregator API - 完了！
✅ Emotion Aggregator API - 完了！
✅ Vibe Aggregator API - `/generate-timeblock-prompt`のみ完了
   ⚠️ `/generate-dashboard-summary` - 次のフェーズで新API分離
   ⚠️ `/create-failed-record` - Vibe Scorer APIへ移動予定

Phase 3: Scorer API (0/1 完了) ← 次はここから
[ ] Vibe Scorer API

Phase 4: Infrastructure (0/3 完了)
[ ] Nginx設定更新
[ ] Lambda関数更新
[ ] 動作確認・デプロイ
```

---

## 💡 次回セッション開始時のチェックリスト

1. [ ] このメモを読む
2. [ ] `NAMING_CONVENTIONS.md`を確認（命名規則の理解）
3. [ ] `TABLE_SCHEMA_REFERENCE.md`を確認（テーブル構造の理解）
4. [ ] 対象APIのディレクトリに移動
5. [ ] Supabase接続部分を確認
6. [ ] 旧テーブル書き込み処理を特定
7. [ ] 新テーブル書き込みに置き換え
8. [ ] デプロイ（git push origin main）
9. [ ] GitHub Actionsで自動デプロイを確認
10. [ ] 本番環境でテスト（ユーザー不在のため直接本番でOK）

---

## 🎓 学んだこと

### Supabase CLIの役割
- **できること**: スキーマ変更（マイグレーション管理）
- **できないこと**: 任意のSQLクエリ実行（データ確認）
- **理由**: Git的な役割（履歴管理）であり、SQLクライアントではない

### 効率的な進め方
- **ユーザーがいない状況では並行運用不要**
- **ローカルテスト不要：直接本番デプロイでOK**
- エンドポイント名は変えず中身を直接置き換え
- ネーミングの整合性が最優先

---

**メモ**: 次回セッションでは、このディレクトリ内のドキュメントを参照すれば、スムーズに作業を継続できます。
