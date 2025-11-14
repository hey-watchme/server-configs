# ステータス管理設計（最終版）

## 📊 階層的ステータス管理

各テーブルが異なる責務でステータスを管理します：

### 1️⃣ audio_files（既存・維持）
**責務：処理対象の判定**

```sql
audio_files
├── transcriptions_status    -- ASRを実行すべきか？
├── behavior_features_status -- SEDを実行すべきか？
├── emotion_features_status  -- SERを実行すべきか？
└── 値: pending, skipped, completed, failed, quota_exceeded
```

**判定ロジック**：
- `skipped` → 夜間時間帯（23:00-05:59）、処理しない
- `pending` → 処理待ち
- `completed` → 処理済み

### 2️⃣ audio_features（新規）
**責務：API処理結果 + 次工程への引き渡し**

```sql
audio_features
├── asr_result (JSONB)      -- ASR処理結果
├── asr_status              -- ASR処理状態
├── sed_result (JSONB)      -- SED処理結果
├── sed_status              -- SED処理状態
├── ser_result (JSONB)      -- SER処理結果
├── ser_status              -- SER処理状態
└── aggregator_status       -- 次工程（Aggregator）への引き渡し状態
    値: pending（待ち）, processing（処理中）, completed（完了）
```

### 3️⃣ audio_aggregator（新規）
**責務：集約処理 + 次工程への引き渡し**

```sql
audio_aggregator
├── vibe_prompt             -- 生成されたプロンプト
├── behavior_aggregated     -- 集約された行動データ
├── emotion_aggregated      -- 集約された感情データ
└── scorer_status          -- 次工程（Scorer）への引き渡し状態
    値: pending, processing, completed
```

### 4️⃣ audio_scorer（新規）
**責務：最終分析 + 累積への反映**

```sql
audio_scorer
├── vibe_score             -- 最終スコア
├── vibe_summary           -- 最終サマリー
└── daily_summary_status   -- 累積分析への反映状態
    値: pending, processing, completed
```

## 🔄 処理フロー

```python
# Step 0: audio_filesでSKIP判定
audio_file = get_from_audio_files(file_path)
if audio_file.transcriptions_status == 'skipped':
    # 全テーブルにSKIPレコード作成
    propagate_skip_status(device_id, date, time_block)
    return

# Step 1: API実行（ASR/SED/SER）
if audio_file.transcriptions_status == 'pending':
    results = execute_apis(file_path)

    # audio_featuresに結果保存
    save_to_audio_features({
        'asr_result': results.asr,
        'sed_result': results.sed,
        'ser_result': results.ser,
        'aggregator_status': 'pending'  # 次工程待ち
    })

    # audio_filesのステータス更新
    update_audio_files_status('completed')

# Step 2: Aggregator処理
if audio_features.aggregator_status == 'pending':
    # 集約処理実行
    save_to_audio_aggregator({
        'vibe_prompt': generate_prompt(),
        'behavior_aggregated': aggregate_behavior(),
        'emotion_aggregated': aggregate_emotion(),
        'scorer_status': 'pending'  # 次工程待ち
    })

    # audio_featuresのステータス更新
    update_audio_features({'aggregator_status': 'completed'})

# Step 3: Scorer処理
if audio_aggregator.scorer_status == 'pending':
    # ChatGPT分析実行
    save_to_audio_scorer({
        'vibe_score': chatgpt_result.score,
        'vibe_summary': chatgpt_result.summary,
        'daily_summary_status': 'pending'  # 次工程待ち
    })

    # audio_aggregatorのステータス更新
    update_audio_aggregator({'scorer_status': 'completed'})

# Step 4: 日次累積更新
if audio_scorer.daily_summary_status == 'pending':
    update_daily_summary()
    update_audio_scorer({'daily_summary_status': 'completed'})
```

## 📈 処理状況の可視化

```sql
-- 全体の処理状況を見るビュー
CREATE VIEW v_processing_pipeline AS
SELECT
  af.device_id,
  af.local_date,
  af.time_block,

  -- Level 0: ファイル状態
  af.transcriptions_status as file_status,

  -- Level 1: API処理
  feat.asr_status,
  feat.aggregator_status,

  -- Level 2: 集約処理
  agg.scorer_status,

  -- Level 3: 最終分析
  scr.daily_summary_status,
  scr.vibe_score

FROM audio_files af
LEFT JOIN audio_features feat ON ...
LEFT JOIN audio_aggregator agg ON ...
LEFT JOIN audio_scorer scr ON ...
```

## 🎯 メリット

1. **責務の明確化**
   - 各テーブルが明確な役割を持つ
   - ステータス管理が階層的で理解しやすい

2. **処理の追跡可能性**
   - どこまで処理が進んだか一目瞭然
   - エラー時の再処理ポイントが明確

3. **並列処理の実現**
   - 各ステップが独立して動作可能
   - キューベースの処理が容易

## ⚠️ 注意点

1. **SKIPの伝播**
   - audio_filesでSKIPと判定されたら全テーブルにSKIPレコード作成
   - 関数 `propagate_skip_status()` を使用

2. **ステータスの整合性**
   - 前工程が完了していない場合は処理しない
   - トランザクションで一貫性を保証

3. **device_id の型**
   - audio_files: TEXT型
   - summary_daily等: UUID型
   - 適切な型変換が必要