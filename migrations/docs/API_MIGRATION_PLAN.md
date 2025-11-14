# API Migration Plan - 新テーブル対応実装計画

## 🎯 概要

WatchMeの7つのAPIを新テーブル構造（イベントステップベース）に対応させる実装計画。

## 📊 新テーブル構造（簡潔版）

```
audio_files（既存・基準）→ audio_features → audio_aggregator → audio_scorer → summary_daily
```

各APIが書き込むテーブル：
- **Features API群**（3つ） → `audio_features`
- **Aggregator API群**（3つ） → `audio_aggregator`
- **Scorer API**（1つ） → `audio_scorer`

## 🔄 API修正リスト（優先順位順）

### Phase 1: Features API群（基礎データ処理）
1. **Behavior Features API**（SED）- 最もシンプル、最初に着手
2. **Emotion Features API**（SER）- SEDと同様のパターン
3. **Vibe Transcriber API**（ASR）- 最も複雑、SKIPロジックあり

### Phase 2: Aggregator API群（集約処理）
4. **Behavior Aggregator API** - behavior_yamnet → behavior_summary
5. **Emotion Aggregator API** - emotion_opensmile → emotion_summary
6. **Vibe Aggregator API** - プロンプト生成、最も複雑

### Phase 3: Scorer API（最終分析）
7. **Vibe Scorer API** - ChatGPT連携

## 📝 各APIの修正方針

### 1. Behavior Features API（SED）
**現状**: `behavior_yamnet`テーブルに書き込み
**修正後**:
- `audio_features.sed_result`（JSONB）に保存
- `audio_features.sed_status`を更新
- 既存の`behavior_yamnet`への書き込みも継続（並行運用）

**修正ファイル**: `/api/behavior-analysis/features/`内の保存処理部分

**基本方針**:
```python
# 新テーブルへの書き込み（追加）
supabase.table('audio_features').upsert({
    'device_id': device_id,
    'date': date,
    'time_block': time_block,
    'sed_result': events_json,
    'sed_status': 'completed'
})

# 既存テーブルも継続（並行運用期間）
supabase.table('behavior_yamnet').upsert(...)
```

### 2. Emotion Features API（SER）
**現状**: `emotion_opensmile`テーブルに書き込み
**修正後**:
- `audio_features.ser_result`（JSONB）に保存
- `audio_features.ser_status`を更新

**修正ファイル**: `/api/emotion-analysis/features/`内の保存処理部分

### 3. Vibe Transcriber API（ASR）
**現状**: `vibe_whisper`テーブルに書き込み、`audio_files`のステータス更新
**修正後**:
- `audio_features.asr_result`（JSONB）に保存
- `audio_features.asr_transcription`（TEXT）に直接テキスト保存
- `audio_features.asr_status`を更新
- SKIPロジックの確認が必要

**特記事項**:
- Azure quota超過処理あり
- SKIP判定ロジック（23:00-05:59）あり

### 4-5. Behavior/Emotion Aggregator API
**現状**: 各summaryテーブルに書き込み
**修正後**:
- `audio_aggregator.behavior_aggregated`（JSONB）
- `audio_aggregator.emotion_aggregated`（JSONB）

### 6. Vibe Aggregator API
**現状**: `dashboard`テーブルにプロンプト保存
**修正後**:
- `audio_aggregator.vibe_prompt`（TEXT）
- `audio_aggregator.scorer_status = 'pending'`

### 7. Vibe Scorer API
**現状**: `dashboard`テーブルに結果保存
**修正後**:
- `audio_scorer.vibe_score`
- `audio_scorer.vibe_summary`
- `audio_scorer.daily_summary_status = 'pending'`

## 🚀 実装手順

### Step 1: 各APIのDB接続部分を確認
```bash
# 例：Behavior Features APIの場合
cd /api/behavior-analysis/features/
grep -r "supabase" .
grep -r "behavior_yamnet" .
```

### Step 2: 並行書き込みコードを追加
新旧両方のテーブルに書き込む（データ整合性確認のため）

### Step 3: 個別テスト
各API単体でテスト実行、新テーブルへの書き込み確認

### Step 4: 既存テーブルへの書き込み停止（2週間後）
並行運用で問題なければ、旧テーブルへの書き込みを削除

## ⚠️ 重要な注意点

1. **device_id の型変換**
   - Features/Aggregator/Scorer: TEXT型
   - Summary系: UUID型
   - 適切な変換が必要

2. **audio_files との関係**
   - `local_date`と`time_block`は`audio_files`から取得
   - 新規作成ではなく、既存レコードの参照が基本

3. **ステータス管理**
   - 各APIは自分の処理結果ステータスを更新
   - 次工程のステータスも`pending`に設定

## 📋 チェックリスト

### API修正完了チェック
- [ ] Behavior Features API
- [ ] Emotion Features API
- [ ] Vibe Transcriber API
- [ ] Behavior Aggregator API
- [ ] Emotion Aggregator API
- [ ] Vibe Aggregator API
- [ ] Vibe Scorer API

### 動作確認チェック
- [ ] 新テーブルへのデータ書き込み確認
- [ ] 既存テーブルとの並行書き込み確認
- [ ] ステータス更新の確認
- [ ] エラー処理の確認

## 🔍 進捗確認クエリ

```sql
-- 新テーブルのデータ確認
SELECT
    'audio_features' as table_name,
    COUNT(*) as total,
    COUNT(CASE WHEN sed_status = 'completed' THEN 1 END) as sed_completed,
    COUNT(CASE WHEN ser_status = 'completed' THEN 1 END) as ser_completed,
    COUNT(CASE WHEN asr_status = 'completed' THEN 1 END) as asr_completed
FROM audio_features

UNION ALL

SELECT
    'audio_aggregator',
    COUNT(*),
    COUNT(CASE WHEN vibe_prompt IS NOT NULL THEN 1 END),
    COUNT(CASE WHEN behavior_aggregated IS NOT NULL THEN 1 END),
    COUNT(CASE WHEN emotion_aggregated IS NOT NULL THEN 1 END)
FROM audio_aggregator

UNION ALL

SELECT
    'audio_scorer',
    COUNT(*),
    COUNT(CASE WHEN vibe_score IS NOT NULL THEN 1 END),
    0,
    0
FROM audio_scorer;
```

## 📚 関連ドキュメント

- [テーブル作成SQL](./001_create_audio_features_tables.sql)
- [ステータス管理設計](./007_status_management_design.md)
- [データフロー設計](./005_correct_data_flow_design.md)

---

**最終更新**: 2025-11-09
**次のアクション**: Behavior Features API から着手