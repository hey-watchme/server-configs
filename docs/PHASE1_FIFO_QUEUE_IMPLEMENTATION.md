# Phase 1: FIFO Queue移行 実装ガイド

最終更新: 2025-12-12

このドキュメントは、Standard QueueからFIFO Queueへの移行手順を記載しています。
**コピー&ペーストで実行可能**な形式になっています。

---

## 🎯 目的

- **順序保証**: 同一デバイスの録音を時系列順に処理
- **重複排除**: 同じ録音を2回処理しない
- **並列数制御**: デバイス単位で並列実行を制御

---

## 📋 前提条件

- Phase 0が完了していること
  - Lambda並列数制限（SED:2, SER:2, ASR:10）
  - Lambda Timeout 60秒
  - SQS可視性タイムアウト 300秒

---

## 🚀 実装手順

### Step 1: FIFO Queue作成（3つ）

```bash
# 1-1. SED用FIFO Queue作成
aws sqs create-queue \
  --queue-name watchme-sed-queue-v2.fifo \
  --region ap-southeast-2 \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "ReceiveMessageWaitTimeSeconds": "0"
  }'

# 1-2. SER用FIFO Queue作成
aws sqs create-queue \
  --queue-name watchme-ser-queue-v2.fifo \
  --region ap-southeast-2 \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "ReceiveMessageWaitTimeSeconds": "0"
  }'

# 1-3. ASR用FIFO Queue作成
aws sqs create-queue \
  --queue-name watchme-asr-queue-v2.fifo \
  --region ap-southeast-2 \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "ReceiveMessageWaitTimeSeconds": "0"
  }'
```

**確認**:
```bash
# 作成されたキューのURLを取得
aws sqs get-queue-url --queue-name watchme-sed-queue-v2.fifo --region ap-southeast-2
aws sqs get-queue-url --queue-name watchme-ser-queue-v2.fifo --region ap-southeast-2
aws sqs get-queue-url --queue-name watchme-asr-queue-v2.fifo --region ap-southeast-2
```

**期待される出力**:
```json
{
    "QueueUrl": "https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue-v2.fifo"
}
```

---

### Step 2: Dead Letter Queue（DLQ）作成（3つ）

```bash
# 2-1. SED用DLQ作成
aws sqs create-queue \
  --queue-name watchme-sed-dlq-v2.fifo \
  --region ap-southeast-2 \
  --attributes '{
    "FifoQueue": "true",
    "MessageRetentionPeriod": "1209600"
  }'

# 2-2. SER用DLQ作成
aws sqs create-queue \
  --queue-name watchme-ser-dlq-v2.fifo \
  --region ap-southeast-2 \
  --attributes '{
    "FifoQueue": "true",
    "MessageRetentionPeriod": "1209600"
  }'

# 2-3. ASR用DLQ作成
aws sqs create-queue \
  --queue-name watchme-asr-dlq-v2.fifo \
  --region ap-southeast-2 \
  --attributes '{
    "FifoQueue": "true",
    "MessageRetentionPeriod": "1209600"
  }'
```

**DLQのARNを取得**:
```bash
# 後で使うのでメモしておく
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-dlq-v2.fifo \
  --attribute-names QueueArn \
  --region ap-southeast-2 \
  --query 'Attributes.QueueArn' \
  --output text

aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-dlq-v2.fifo \
  --attribute-names QueueArn \
  --region ap-southeast-2 \
  --query 'Attributes.QueueArn' \
  --output text

aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-dlq-v2.fifo \
  --attribute-names QueueArn \
  --region ap-southeast-2 \
  --query 'Attributes.QueueArn' \
  --output text
```

**期待される出力**:
```
arn:aws:sqs:ap-southeast-2:754724220380:watchme-sed-dlq-v2.fifo
arn:aws:sqs:ap-southeast-2:754724220380:watchme-ser-dlq-v2.fifo
arn:aws:sqs:ap-southeast-2:754724220380:watchme-asr-dlq-v2.fifo
```

---

### Step 3: メインキューにDLQを設定

```bash
# 3-1. SED Queue にDLQを設定
aws sqs set-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue-v2.fifo \
  --attributes '{
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:754724220380:watchme-sed-dlq-v2.fifo\",\"maxReceiveCount\":3}"
  }' \
  --region ap-southeast-2

# 3-2. SER Queue にDLQを設定
aws sqs set-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-queue-v2.fifo \
  --attributes '{
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:754724220380:watchme-ser-dlq-v2.fifo\",\"maxReceiveCount\":3}"
  }' \
  --region ap-southeast-2

# 3-3. ASR Queue にDLQを設定
aws sqs set-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-queue-v2.fifo \
  --attributes '{
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:754724220380:watchme-asr-dlq-v2.fifo\",\"maxReceiveCount\":3}"
  }' \
  --region ap-southeast-2
```

**確認**:
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue-v2.fifo \
  --attribute-names RedrivePolicy \
  --region ap-southeast-2
```

---

### Step 4: audio-processor Lambda修正

**現在のコード**を確認:
```bash
# ローカルにダウンロード
cd /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-audio-processor
cat lambda_function.py
```

**新しいコード**を作成:

```python
import json
import boto3
import hashlib
from datetime import datetime

s3_client = boto3.client('s3')
sqs = boto3.client('sqs', region_name='ap-southeast-2')

# FIFO Queue URLs
ASR_FIFO_QUEUE_URL = 'https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-queue-v2.fifo'
SED_FIFO_QUEUE_URL = 'https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue-v2.fifo'
SER_FIFO_QUEUE_URL = 'https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-queue-v2.fifo'

def lambda_handler(event, context):
    """
    S3にアップロードされた音声ファイルを検知し、
    3つのFIFO SQSキューに並列送信する
    """
    for record in event['Records']:
        # S3イベントから情報取得
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        # keyから device_id と recorded_at を抽出
        # 例: files/device-id/2025-12-12/13-30-00/audio.wav
        parts = key.split('/')
        if len(parts) < 5 or parts[0] != 'files':
            print(f"Invalid key format: {key}")
            continue

        device_id = parts[1]
        date_part = parts[2]  # 2025-12-12
        time_part = parts[3]  # 13-30-00

        # recorded_at を構築 (ISO8601形式)
        # time_part: "13-30-00" -> "13:30:00"
        time_str = time_part.replace('-', ':')
        recorded_at = f"{date_part}T{time_str}+00:00"

        print(f"Processing: device_id={device_id}, recorded_at={recorded_at}, file={key}")

        # 3つのFIFO Queueに並列送信
        send_to_fifo_queue(SED_FIFO_QUEUE_URL, device_id, recorded_at, key, "sed")
        send_to_fifo_queue(SER_FIFO_QUEUE_URL, device_id, recorded_at, key, "ser")
        send_to_fifo_queue(ASR_FIFO_QUEUE_URL, device_id, recorded_at, key, "asr")

        print(f"✅ Sent to all 3 FIFO queues: {key}")

    return {
        'statusCode': 200,
        'body': json.dumps('Processing complete')
    }


def send_to_fifo_queue(queue_url, device_id, recorded_at, file_path, api_type):
    """
    FIFO Queueにメッセージを送信

    Args:
        queue_url: FIFO QueueのURL
        device_id: デバイスID
        recorded_at: 録音時刻 (ISO8601形式)
        file_path: S3ファイルパス
        api_type: API種別 (asr/sed/ser)
    """
    # Message Group ID: デバイスごと・API種別ごとにグループ化
    # 同じグループ内のメッセージは順序保証される
    message_group_id = f"{device_id}-{api_type}"

    # Deduplication ID: 重複排除
    # 同じIDのメッセージは5分以内に2回送信されない
    deduplication_id = get_deduplication_id(device_id, recorded_at, api_type)

    # メッセージボディ
    message_body = json.dumps({
        "device_id": device_id,
        "recorded_at": recorded_at,
        "file_path": file_path
    })

    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
            MessageGroupId=message_group_id,
            MessageDeduplicationId=deduplication_id
        )

        print(f"Sent to FIFO queue ({api_type}): MessageId={response['MessageId']}, GroupId={message_group_id}")

    except Exception as e:
        print(f"Error sending to FIFO queue ({api_type}): {str(e)}")
        raise


def get_deduplication_id(device_id, recorded_at, api_type):
    """
    Deduplication IDを生成

    同じdevice_id + recorded_at + api_type の組み合わせは
    常に同じDeduplication IDを生成する
    """
    unique_string = f"{device_id}-{recorded_at}-{api_type}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:80]  # 最大80文字
```

**保存**:
```bash
# 上記のコードを lambda_function.py に保存
cd /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-audio-processor

# バックアップ
cp lambda_function.py lambda_function.py.backup.$(date +%Y%m%d_%H%M%S)

# 新しいコードを保存（エディタで編集するか、上記のコードをコピペ）
```

**デプロイ**:
```bash
# zipファイル作成
cd /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-audio-processor
zip -r function.zip lambda_function.py

# Lambda更新
aws lambda update-function-code \
  --function-name watchme-audio-processor \
  --zip-file fileb://function.zip \
  --region ap-southeast-2
```

---

### Step 5: Lambda WorkerのEvent Source Mapping更新

#### 5-1. 既存のStandard Queue接続を取得

```bash
# SED Worker
aws lambda list-event-source-mappings \
  --function-name watchme-sed-worker \
  --region ap-southeast-2 \
  --query 'EventSourceMappings[0].UUID' \
  --output text

# SER Worker
aws lambda list-event-source-mappings \
  --function-name watchme-ser-worker \
  --region ap-southeast-2 \
  --query 'EventSourceMappings[0].UUID' \
  --output text

# ASR Worker
aws lambda list-event-source-mappings \
  --function-name watchme-asr-worker \
  --region ap-southeast-2 \
  --query 'EventSourceMappings[0].UUID' \
  --output text
```

**出力例**:
```
12345678-1234-1234-1234-123456789012  # SED
23456789-2345-2345-2345-234567890123  # SER
34567890-3456-3456-3456-345678901234  # ASR
```

#### 5-2. 既存のStandard Queue接続を無効化

**⚠️ 重要**: UUIDを上記の出力に置き換えてください

```bash
# SED Worker: Standard Queue無効化
aws lambda update-event-source-mapping \
  --uuid <SED-WORKER-UUID> \
  --enabled false \
  --region ap-southeast-2

# SER Worker: Standard Queue無効化
aws lambda update-event-source-mapping \
  --uuid <SER-WORKER-UUID> \
  --enabled false \
  --region ap-southeast-2

# ASR Worker: Standard Queue無効化
aws lambda update-event-source-mapping \
  --uuid <ASR-WORKER-UUID> \
  --enabled false \
  --region ap-southeast-2
```

#### 5-3. 新しいFIFO Queue接続を作成

```bash
# SED Worker: FIFO Queue接続
aws lambda create-event-source-mapping \
  --function-name watchme-sed-worker \
  --event-source-arn arn:aws:sqs:ap-southeast-2:754724220380:watchme-sed-queue-v2.fifo \
  --batch-size 1 \
  --enabled true \
  --region ap-southeast-2

# SER Worker: FIFO Queue接続
aws lambda create-event-source-mapping \
  --function-name watchme-ser-worker \
  --event-source-arn arn:aws:sqs:ap-southeast-2:754724220380:watchme-ser-queue-v2.fifo \
  --batch-size 1 \
  --enabled true \
  --region ap-southeast-2

# ASR Worker: FIFO Queue接続
aws lambda create-event-source-mapping \
  --function-name watchme-asr-worker \
  --event-source-arn arn:aws:sqs:ap-southeast-2:754724220380:watchme-asr-queue-v2.fifo \
  --batch-size 1 \
  --enabled true \
  --region ap-southeast-2
```

---

### Step 6: 動作確認

#### 6-1. テスト録音をアップロード

iOSアプリまたはObserver Deviceから録音を実施

#### 6-2. SQSキューの状態確認

```bash
# FIFO Queueのメッセージ数確認
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue-v2.fifo \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
  --region ap-southeast-2

aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-queue-v2.fifo \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
  --region ap-southeast-2

aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-queue-v2.fifo \
  --attribute-names ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible \
  --region ap-southeast-2
```

#### 6-3. Lambda実行ログ確認

```bash
# audio-processor のログ
aws logs tail /aws/lambda/watchme-audio-processor --since 5m --format short --region ap-southeast-2

# sed-worker のログ
aws logs tail /aws/lambda/watchme-sed-worker --since 5m --format short --region ap-southeast-2

# ser-worker のログ
aws logs tail /aws/lambda/watchme-ser-worker --since 5m --format short --region ap-southeast-2
```

**期待されるログ**:
```
audio-processor:
Sent to FIFO queue (sed): MessageId=xxx, GroupId=device-id-sed

sed-worker:
Processing SED for device xxx at 2025-12-12T...
SED processing started successfully
```

#### 6-4. データベース確認

```sql
-- 最新の録音を確認
SELECT
  device_id,
  recorded_at,
  vibe_status,
  behavior_status,
  emotion_status,
  aggregator_status
FROM spot_features
ORDER BY recorded_at DESC
LIMIT 5;
```

**期待される結果**:
- すべてのstatusが `completed` になる
- `aggregator_status` も `completed` になる

---

### Step 7: Standard Queueのクリーンアップ

**⚠️ 注意**: FIFO Queueが1週間安定稼働してから実施

```bash
# Standard Queueが空であることを確認
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue \
  --attribute-names ApproximateNumberOfMessages \
  --region ap-southeast-2

# 空であることを確認してから削除
aws sqs delete-queue \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue \
  --region ap-southeast-2

aws sqs delete-queue \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-queue \
  --region ap-southeast-2

aws sqs delete-queue \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-queue \
  --region ap-southeast-2
```

---

## 🔍 トラブルシューティング

### 問題: メッセージがFIFO Queueに届かない

**確認**:
```bash
# audio-processor のログ確認
aws logs tail /aws/lambda/watchme-audio-processor --since 10m --format short
```

**考えられる原因**:
- audio-processor のデプロイが失敗している
- S3イベントトリガーが動作していない

### 問題: Lambda Workerがメッセージを処理しない

**確認**:
```bash
# Event Source Mappingの状態確認
aws lambda list-event-source-mappings \
  --function-name watchme-sed-worker \
  --region ap-southeast-2
```

**考えられる原因**:
- Event Source Mappingが `Enabled: false`
- IAMロールにSQS権限がない

### 問題: DLQにメッセージが溜まる

**確認**:
```bash
# DLQのメッセージ数確認
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-dlq-v2.fifo \
  --attribute-names ApproximateNumberOfMessages \
  --region ap-southeast-2
```

**対処**:
- CloudWatch Logsで失敗原因を確認
- EC2 APIのヘルス確認
- 必要に応じてDLQから再送信

---

## 📊 期待効果

| 項目 | Standard Queue | FIFO Queue |
|------|---------------|------------|
| **順序保証** | なし | デバイス単位であり |
| **重複処理** | 可能性あり | 自動排除 |
| **並列制御** | Lambda並列数のみ | Message Group単位 |
| **スケーラビリティ** | 低 | 高（デバイス数に応じて） |

---

## 📝 チェックリスト

- [ ] Step 1: FIFO Queue作成（3つ）
- [ ] Step 2: DLQ作成（3つ）
- [ ] Step 3: DLQ設定
- [ ] Step 4: audio-processor修正・デプロイ
- [ ] Step 5: Event Source Mapping更新
- [ ] Step 6: 動作確認
- [ ] Step 7: Standard Queueクリーンアップ（1週間後）

---

## 📚 関連ドキュメント

- [SCALABILITY_ROADMAP.md](./SCALABILITY_ROADMAP.md) - 全体のロードマップ
- [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) - 既知の問題
- [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md) - 処理アーキテクチャ
