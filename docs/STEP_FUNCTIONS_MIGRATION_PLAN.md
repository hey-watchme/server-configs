# 🔄 Step Functions 導入計画

**プロジェクト**: WatchMe - ワークフロー自動化強化
**作成日**: 2025-11-13
**ステータス**: 🚧 計画中 → 即座に実装開始
**優先度**: 高（Phase 4-2実装前に導入）

---

## 📋 目次

1. [導入の目的](#導入の目的)
2. [現在のアーキテクチャと課題](#現在のアーキテクチャと課題)
3. [Step Functions導入後のアーキテクチャ](#step-functions導入後のアーキテクチャ)
4. [導入のメリット](#導入のメリット)
5. [移行計画](#移行計画)
6. [コスト分析](#コスト分析)
7. [実装タスク](#実装タスク)

---

## 🎯 導入の目的

### 主要な目的

1. **ワークフローの可視化**: 録音から分析までの全プロセスをリアルタイムで監視
2. **エラーハンドリングの簡素化**: リトライ・エラー分岐を宣言的に管理
3. **運用コストの削減**: デバッグ時間の大幅短縮
4. **スケーラビリティの向上**: 今後のWeekly/Monthly分析への拡張を容易に

### 導入タイミング

**🚨 今すぐ導入（Phase 4-2実装前）**

**理由**:
- Phase 4-2（Daily Profiler）実装により、ワークフローがさらに複雑化
- 既存のSQS + Lambdaコードを整理する良いタイミング
- 新規エンドポイント追加前にインフラを整備

---

## 📊 現在のアーキテクチャと課題

### 現在の構成（SQS + Lambda）

```
S3 Upload
  ↓ S3 Event Notification
Lambda (audio-processor)
  ↓ SQS Message
Lambda (audio-worker)
  ├─ HTTP Call → Vibe Transcriber API
  ├─ HTTP Call → Behavior Features API
  ├─ HTTP Call → Emotion Features API
  └─ (並列処理を自前実装)
  ↓ 全て完了後
  ├─ HTTP Call → Aggregator API (/spot)
  └─ HTTP Call → Profiler API (/spot-profiler)

※ Phase 4-2実装後は Daily Aggregator/Profiler も追加予定
```

### 現在の課題

| 課題 | 影響 | 深刻度 |
|------|------|--------|
| **並列処理の複雑さ** | asyncio/concurrent.futuresを自前実装 | 🟡 中 |
| **エラーハンドリング** | try-except + 自前リトライロジック | 🟡 中 |
| **可視化の欠如** | CloudWatch Logsでログ追跡が必要 | 🔴 高 |
| **デバッグの困難さ** | どこで失敗したか特定に時間がかかる | 🔴 高 |
| **部分的な再実行不可** | 失敗時は全体を再実行するしかない | 🟡 中 |
| **タイムアウトリスク** | Lambda 15分制限（LLM遅延時に問題） | 🟡 中 |

---

## ⚡ Step Functions導入後のアーキテクチャ

### 新しい構成（Step Functions）

```
S3 Upload
  ↓ S3 Event Notification
Lambda (audio-processor-trigger) ← 軽量化（State Machine起動のみ）
  ↓ StartExecution
┌─────────────────────────────────────────────────────────────┐
│ Step Functions State Machine: "WatchMeAudioPipeline"        │
│                                                              │
│ State 1: RegisterAudioFile                                  │
│   └─ Task: Lambda (register-audio) → Vault API             │
│   ↓                                                          │
│                                                              │
│ State 2: ExtractFeatures (Parallel)                         │
│   ├─ Branch 1: Lambda → Vibe Transcriber API               │
│   ├─ Branch 2: Lambda → Behavior Features API              │
│   └─ Branch 3: Lambda → Emotion Features API               │
│   ↓ 全ブランチ完了を自動待機                                  │
│                                                              │
│ State 3: AggregateSpotData                                  │
│   └─ Task: Lambda → Aggregator API (/spot)                 │
│   ↓                                                          │
│                                                              │
│ State 4: ProfileSpotData                                    │
│   └─ Task: Lambda → Profiler API (/spot-profiler)          │
│   ↓                                                          │
│                                                              │
│ State 5: AggregateDailyData                                 │
│   └─ Task: Lambda → Aggregator API (/daily)                │
│   ↓                                                          │
│                                                              │
│ State 6: ProfileDailyData                                   │
│   └─ Task: Lambda → Profiler API (/daily-profiler)         │
│   ↓                                                          │
│                                                              │
│ State 7: Success (完了通知)                                  │
│   └─ Task: Lambda → SNS/CloudWatch Metrics                 │
│                                                              │
│ ※ 各Stateで自動リトライ・エラーハンドリング設定              │
└─────────────────────────────────────────────────────────────┘
```

### Lambda関数の役割変更

| Lambda関数 | 旧役割 | 新役割 |
|-----------|--------|--------|
| audio-processor | SQS送信 | Step Functions起動のみ |
| audio-worker | 全処理を実行 | **削除** → 各Stateで個別Lambda実行 |
| **register-audio** (新規) | - | Vault API呼び出し |
| **call-transcriber** (新規) | - | Transcriber API呼び出し |
| **call-behavior** (新規) | - | Behavior API呼び出し |
| **call-emotion** (新規) | - | Emotion API呼び出し |
| **call-aggregator-spot** (新規) | - | Aggregator API (/spot) 呼び出し |
| **call-profiler-spot** (新規) | - | Profiler API (/spot) 呼び出し |
| **call-aggregator-daily** (新規) | - | Aggregator API (/daily) 呼び出し |
| **call-profiler-daily** (新規) | - | Profiler API (/daily) 呼び出し |

**設計思想**: 各Lambdaは単一責任（1つのAPI呼び出しのみ）

---

## 🎯 導入のメリット

### 1. 可視化・モニタリング

**Before（現在）**:
- CloudWatch Logsで各Lambdaのログを個別に確認
- 「今どの段階？」が不明
- 失敗箇所の特定に時間がかかる

**After（Step Functions）**:
- ✅ AWS Consoleでワークフロー全体を視覚的に確認
- ✅ リアルタイムで進行状況が一目瞭然
- ✅ 失敗したStateを即座に特定
- ✅ 実行履歴が自動保存（最大90日）

**具体例**:
```
Visual Flow in AWS Console:

RegisterAudioFile ✅ (1.2s)
    ↓
ExtractFeatures ⚠️ (8.5s)
    ├─ Transcriber ✅ (3.2s)
    ├─ Behavior ✅ (4.1s)
    └─ Emotion ❌ (failed - API timeout)
        ↓ Auto Retry 1/3
        ✅ (3.8s)
    ↓
AggregateSpotData → 現在実行中...
```

---

### 2. エラーハンドリング・リトライ

**Before（現在）**:
```python
# Lambda内で自前実装
def call_api_with_retry(url, data, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

**After（Step Functions）**:
```json
{
  "Type": "Task",
  "Resource": "arn:aws:lambda:...:function:call-transcriber",
  "Retry": [
    {
      "ErrorEquals": ["States.TaskFailed", "States.Timeout"],
      "IntervalSeconds": 2,
      "MaxAttempts": 3,
      "BackoffRate": 2.0
    }
  ],
  "Catch": [
    {
      "ErrorEquals": ["States.ALL"],
      "ResultPath": "$.error",
      "Next": "NotifyError"
    }
  ],
  "TimeoutSeconds": 60
}
```

**メリット**:
- ✅ 宣言的な設定（コード不要）
- ✅ 指数バックオフ自動対応
- ✅ タイムアウトを個別に設定可能
- ✅ エラー時の分岐処理が簡単

---

### 3. 並列処理の管理

**Before（現在）**:
```python
import asyncio

async def process_features(device_id, recorded_at):
    # 並列実行を自前実装
    transcriber_task = call_transcriber_api(device_id, recorded_at)
    behavior_task = call_behavior_api(device_id, recorded_at)
    emotion_task = call_emotion_api(device_id, recorded_at)

    results = await asyncio.gather(
        transcriber_task,
        behavior_task,
        emotion_task,
        return_exceptions=True  # 1つ失敗しても継続
    )

    # エラーチェックを手動実装
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # エラーハンドリング...
```

**After（Step Functions）**:
```json
{
  "Type": "Parallel",
  "Branches": [
    {
      "StartAt": "CallTranscriber",
      "States": {
        "CallTranscriber": {
          "Type": "Task",
          "Resource": "arn:aws:lambda:...:function:call-transcriber",
          "End": true
        }
      }
    },
    {
      "StartAt": "CallBehavior",
      "States": {
        "CallBehavior": {
          "Type": "Task",
          "Resource": "arn:aws:lambda:...:function:call-behavior",
          "End": true
        }
      }
    },
    {
      "StartAt": "CallEmotion",
      "States": {
        "CallEmotion": {
          "Type": "Task",
          "Resource": "arn:aws:lambda:...:function:call-emotion",
          "End": true
        }
      }
    }
  ],
  "Next": "AggregateSpotData"
}
```

**メリット**:
- ✅ 並列実行を宣言するだけ
- ✅ 全ブランチ完了を自動的に待機
- ✅ 各ブランチで個別リトライ設定可能
- ✅ 1つ失敗しても他は継続（設定次第）

---

### 4. デバッグ・再実行

**Before（現在）**:
- 失敗したら全体を最初から再実行
- どのAPIで失敗したか特定に時間がかかる
- 入力データを変えて再実行が困難

**After（Step Functions）**:
- ✅ 特定のStateから再実行可能
- ✅ 入力データを変えて再実行可能
- ✅ 実行履歴から過去の成功パターンをコピー

**具体例**:
```
失敗シナリオ: Profiler APIでタイムアウト

現在:
1. CloudWatch Logsを確認 (5分)
2. audio-worker全体を再実行 (10秒)
   → 不要な特徴抽出も再実行される

Step Functions:
1. AWS Consoleで失敗箇所を確認 (10秒)
2. "ProfileSpotData" Stateのみ再実行 (3秒)
   → 特徴抽出はスキップ

時間短縮: 約5分 → 約15秒
```

---

### 5. タイムアウト対応

**Before（現在）**:
- Lambda最大タイムアウト: 15分
- LLM分析が遅い場合に問題

**After（Step Functions）**:
- State Machine最大実行時間: 1年
- ✅ 個別のLambdaは短時間で完了
- ✅ 全体の処理時間制限なし
- ✅ LLM分析が遅くても問題なし

---

### 6. コードの保守性向上

**Before（現在）**:
- 1つのLambda (audio-worker) に全ロジックが集中
- 約500行のコード
- 変更時の影響範囲が大きい

**After（Step Functions）**:
- 各Lambdaは50-100行程度
- 単一責任原則に従う
- ✅ テストが容易
- ✅ 変更時の影響範囲が小さい
- ✅ 新しいステップの追加が簡単

---

## 💰 コスト分析

### Step Functions料金

**State Transition課金**: $0.025 / 1,000 transitions

**1回の録音あたりのTransitions**:
1. RegisterAudioFile (1)
2. ExtractFeatures - Parallel (1)
   - Transcriber (1)
   - Behavior (1)
   - Emotion (1)
3. AggregateSpotData (1)
4. ProfileSpotData (1)
5. AggregateDailyData (1)
6. ProfileDailyData (1)
7. Success (1)

**合計**: 10 transitions / 録音

**月間コスト試算**:

| 録音回数/月 | Transitions | コスト |
|------------|-------------|--------|
| 1,000回 | 10,000 | $0.25 |
| 10,000回 | 100,000 | $2.50 |
| 100,000回 | 1,000,000 | $25.00 |

**WatchMeの想定**:
- 1ユーザーあたり: 1日10回録音 = 月300回
- 100ユーザー: 月30,000回 = **$7.50/月**

### Lambda料金（変化なし）

- 実行時間は変わらず
- 実行回数は若干増加（State毎に1 Lambda）
- 各Lambdaは軽量なので影響は微小

**試算**:
- 現在: audio-worker 1回実行 (10秒)
- 導入後: 9回の軽量Lambda実行 (各1秒) = 合計9秒
- **削減**: 約10%のLambda実行時間削減

### 総コスト

**月間追加コスト**: 約$7.50 (100ユーザー想定)

**費用対効果**:
- デバッグ時間削減: 1回あたり5分 → 15秒（4分45秒削減）
- 月10回のデバッグで約50分の時間節約
- エンジニア時給$50と仮定: **$40/月の節約**
- **ROI**: 533% (投資$7.50 → リターン$40)

---

## 📅 移行計画

### フェーズ1: Step Functions導入（今すぐ開始）

**期間**: 2-3日

**タスク**:
1. State Machine定義作成
2. 各Lambda関数の実装（9個）
3. IAMロール・ポリシー設定
4. テスト実行（開発環境）

**完了条件**:
- テスト録音でState Machineが正常終了
- 各Stateのリトライ動作確認
- エラー時の分岐動作確認

---

### フェーズ2: 本番環境デプロイ（フェーズ1完了後）

**期間**: 1日

**タスク**:
1. 本番環境にState Machineデプロイ
2. S3イベント通知先を変更
   - 旧: Lambda (audio-processor) → SQS
   - 新: Lambda (audio-processor-trigger) → Step Functions
3. 旧Lambda (audio-worker) は保持（ロールバック用）
4. モニタリング設定（CloudWatch Alarms）

**完了条件**:
- 本番録音でState Machineが正常終了
- 24時間の安定稼働確認

---

### フェーズ3: Phase 4-2実装（Step Functions稼働後）

**期間**: 2-3日

**タスク**:
1. Aggregator API: `/daily` エンドポイント実装
2. Profiler API: `/daily-profiler` エンドポイント実装
3. State Machineに2つのStateを追加
   - AggregateDailyData
   - ProfileDailyData
4. テスト・デプロイ

**完了条件**:
- daily_results がリアルタイム更新される

---

### フェーズ4: 旧システム削除（2週間後）

**期間**: 1日

**タスク**:
1. 旧Lambda (audio-worker) 削除
2. SQS削除
3. ドキュメント更新

---

## 🛠️ 実装タスク

### Task 1: State Machine定義作成

**ファイル**: `/watchme/lambda/step-functions/audio-pipeline.asl.json`

**内容**:
- State Machine定義（Amazon States Language）
- 各Stateの設定
- リトライ・エラーハンドリング設定

**所要時間**: 2-3時間

---

### Task 2: Lambda関数実装

**ディレクトリ**: `/watchme/lambda/audio-pipeline/`

**実装する関数**:
1. `audio-processor-trigger/` - State Machine起動
2. `register-audio/` - Vault API呼び出し
3. `call-transcriber/` - Transcriber API呼び出し
4. `call-behavior/` - Behavior API呼び出し
5. `call-emotion/` - Emotion API呼び出し
6. `call-aggregator-spot/` - Aggregator API (/spot)
7. `call-profiler-spot/` - Profiler API (/spot-profiler)
8. `call-aggregator-daily/` - Aggregator API (/daily)
9. `call-profiler-daily/` - Profiler API (/daily-profiler)

**各Lambda共通構造**:
```python
import json
import requests
import os

def lambda_handler(event, context):
    """
    Single responsibility: Call one API endpoint
    """
    # Extract input from Step Functions
    device_id = event['device_id']
    recorded_at = event['recorded_at']

    # Call API
    api_url = os.environ['API_URL']
    response = requests.post(
        api_url,
        json={'device_id': device_id, 'recorded_at': recorded_at},
        timeout=30
    )
    response.raise_for_status()

    # Return result to Step Functions
    return {
        'statusCode': 200,
        'device_id': device_id,
        'recorded_at': recorded_at,
        'result': response.json()
    }
```

**所要時間**: 4-5時間

---

### Task 3: IAMロール・ポリシー設定

**必要なロール**:
1. Step Functions実行ロール
   - Lambda呼び出し権限
   - CloudWatch Logs書き込み
2. 各Lambda実行ロール
   - API呼び出し権限（既存と同じ）

**所要時間**: 1時間

---

### Task 4: デプロイ・テスト

**テスト項目**:
- [ ] 正常系: 全Stateが成功
- [ ] 異常系: Transcriber API失敗 → リトライ → 成功
- [ ] 異常系: Profiler API失敗 → エラー通知
- [ ] 並列処理: 3つのAPIが同時実行
- [ ] タイムアウト: 30秒以上かかるAPIでタイムアウト

**所要時間**: 3-4時間

---

## 📋 チェックリスト

### 実装前

- [ ] ARCHITECTURE_AND_MIGRATION_GUIDE.md更新（Step Functions導入を記載）
- [ ] Lambda関数のディレクトリ構造設計
- [ ] IAMポリシー設計

### 実装中

- [ ] State Machine定義作成
- [ ] 9つのLambda関数実装
- [ ] IAMロール作成
- [ ] 開発環境でテスト

### 実装後

- [ ] 本番環境デプロイ
- [ ] S3イベント通知先変更
- [ ] 24時間の安定稼働確認
- [ ] ドキュメント更新
- [ ] 旧システム削除（2週間後）

---

## 📚 参考資料

- [AWS Step Functions公式ドキュメント](https://docs.aws.amazon.com/step-functions/)
- [Amazon States Language仕様](https://states-language.net/spec.html)
- [Step Functionsベストプラクティス](https://docs.aws.amazon.com/step-functions/latest/dg/best-practices.html)

---

**最終更新**: 2025-11-13
**ステータス**: 🚧 即座に実装開始
**次のアクション**: Task 1（State Machine定義作成）から着手
