# Lambda関数分割デプロイガイド

## 概要
既存の単一Lambda関数を、SQSを使用した2つのLambda関数に分割します。

## アーキテクチャ
```
S3イベント → Lambda (watchme-audio-trigger) → SQS → Lambda (watchme-audio-worker) → 各種API
    1秒                                              最大15分（SQSリトライ付き）
```

## メリット
- **タイムアウト問題の解消**: トリガーは1秒で終了
- **自動リトライ**: SQSの機能で失敗時に自動再試行
- **エラー追跡**: どの処理で失敗したか明確
- **同時実行制御**: ワーカーLambdaの同時実行数を制限可能

## セットアップ手順

### 1. SQSキューの作成（AWSコンソール）

1. AWS Console → SQS → Create queue
2. 設定:
   - **Queue name**: `watchme-audio-processing`
   - **Visibility timeout**: `900` (15分)
   - **Message retention period**: `1209600` (14日)
   - **Maximum message size**: `256 KB`
   - **Dead letter queue**: 
     - Create new queue: `watchme-audio-processing-dlq`
     - Maximum receives: `3`

### 2. Lambda関数のビルド

```bash
# トリガーLambda
cd watchme-audio-trigger
./build.sh

# ワーカーLambda  
cd ../watchme-audio-worker
./build.sh
```

### 3. Lambda関数の作成とデプロイ

#### A. watchme-audio-trigger（新規作成）

1. AWS Console → Lambda → Create function
2. 設定:
   - **Function name**: `watchme-audio-trigger`
   - **Runtime**: Python 3.11
   - **Architecture**: x86_64
   - **Timeout**: 10 seconds
   - **Memory**: 128 MB
   
3. 環境変数:
   - `SQS_QUEUE_URL`: (作成したSQSのURL)

4. IAMロール権限:
   - S3 読み取り
   - SQS SendMessage

5. S3トリガー設定:
   - Bucket: `watchme-vault`
   - Prefix: `files/`
   - Suffix: `.wav`

6. コードアップロード:
   ```bash
   aws lambda update-function-code \
     --function-name watchme-audio-trigger \
     --zip-file fileb://watchme-audio-trigger/function.zip \
     --region ap-southeast-2
   ```

#### B. watchme-audio-worker（新規作成）

1. AWS Console → Lambda → Create function
2. 設定:
   - **Function name**: `watchme-audio-worker`
   - **Runtime**: Python 3.11
   - **Architecture**: x86_64
   - **Timeout**: 15 minutes (900秒)
   - **Memory**: 512 MB
   - **Reserved concurrent executions**: 5（同時実行を制限）
   
3. 環境変数:
   - `API_BASE_URL`: `https://api.hey-watch.me`

4. IAMロール権限:
   - SQS ReceiveMessage, DeleteMessage
   - CloudWatch Logs

5. SQSトリガー設定:
   - Queue: `watchme-audio-processing`
   - Batch size: 1
   - Batch window: 0

6. コードアップロード:
   ```bash
   aws lambda update-function-code \
     --function-name watchme-audio-worker \
     --zip-file fileb://watchme-audio-worker/function.zip \
     --region ap-southeast-2
   ```

### 4. 既存Lambda関数の無効化

1. `watchme-audio-processor`のS3トリガーを削除
2. または関数を一時的に無効化

## テスト手順

1. 小さな音声ファイルをS3にアップロード
2. CloudWatchログで確認:
   - `watchme-audio-trigger`のログ（1-2秒で完了）
   - SQSキューにメッセージが入ったことを確認
   - `watchme-audio-worker`のログ（処理実行）

## 監視

### CloudWatch メトリクス
- SQS: `ApproximateNumberOfMessagesVisible`（待機中のメッセージ）
- SQS: `ApproximateNumberOfMessagesNotVisible`（処理中のメッセージ）
- Lambda: Duration, Errors, Throttles

### アラート設定
- Dead Letter Queueにメッセージが入ったらアラート
- SQSキューのメッセージが100以上になったらアラート

## ロールバック手順

問題が発生した場合:
1. `watchme-audio-trigger`のS3トリガーを削除
2. `watchme-audio-processor`のS3トリガーを再有効化

## 次のステップ

将来的にStep Functionsに移行する場合:
- `watchme-audio-worker`をさらに分割（Azure、AST、SUPERB別）
- Step Functionsでオーケストレーション