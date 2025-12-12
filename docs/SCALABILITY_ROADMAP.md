# WatchMe スケーラビリティ改善ロードマップ

最終更新: 2025-12-12

このドキュメントは、WatchMeシステムを1人から100人、さらに1000人規模まで対応させるための段階的な改善計画です。

---

## 🎯 目標

| フェーズ | 対応ユーザー数 | 目標期限 | 状態 |
|---------|--------------|---------|-----|
| **Phase 0** | 1-5人 | 2025-12-12 | ✅ **完了** |
| **Phase 1** | 1-20人 | 2025-12-19 | 🔄 進行中 |
| **Phase 2** | 1-100人 | 2026-01-31 | 📋 計画中 |
| **Phase 3** | 1-1000人+ | 2026-02-28 | 📋 計画中 |

---

## ✅ Phase 0: 緊急安定化対策（完了: 2025-12-12）

### 実施内容

#### 1. Lambda並列実行数の制限

**問題**: Lambda WorkerがEC2 APIに無制限に同時リクエスト → CPU枯渇 → APIがunhealthy

**対策**:
```bash
# SED Worker: 最大2並列（EC2 CPU制限）
aws lambda put-function-concurrency \
  --function-name watchme-sed-worker \
  --reserved-concurrent-executions 2

# SER Worker: 最大2並列（EC2 CPU制限）
aws lambda put-function-concurrency \
  --function-name watchme-ser-worker \
  --reserved-concurrent-executions 2

# ASR Worker: 最大10並列（外部APIなのでOK）
aws lambda put-function-concurrency \
  --function-name watchme-asr-worker \
  --reserved-concurrent-executions 10
```

**効果**:
- ✅ EC2への同時リクエスト数が最大4件に制限
- ✅ CPU枯渇によるAPIのunhealthy状態を防止
- ✅ メッセージはSQSキューで待機（処理順序保証）

#### 2. Lambda Timeout延長

**問題**: Lambda Worker timeout 30秒 → API遅延時にタイムアウト → SQSメッセージ蓄積

**対策**:
```bash
# 全Lambda Workerを60秒に延長
aws lambda update-function-configuration \
  --function-name watchme-sed-worker --timeout 60
aws lambda update-function-configuration \
  --function-name watchme-ser-worker --timeout 60
aws lambda update-function-configuration \
  --function-name watchme-asr-worker --timeout 60
```

**効果**:
- ✅ 一時的なAPI遅延に耐えられる（30秒 → 60秒）
- ✅ Cloudflare 100秒制限内に収まる
- ✅ タイムアウトによるメッセージ蓄積を軽減

#### 3. SQS可視性タイムアウト短縮

**問題**: 可視性タイムアウト 15分 → 失敗時のリトライが遅い

**対策**:
```bash
# 全SQSキューを5分に短縮
aws sqs set-queue-attributes \
  --queue-url https://sqs.../watchme-sed-queue \
  --attributes VisibilityTimeout=300
```

**効果**:
- ✅ 失敗メッセージの再処理が早くなる（15分 → 5分）
- ✅ 問題の早期発見・対処が可能
- ✅ DLQへの移動も早くなる

### 設定サマリー

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| **Lambda並列数** | 無制限 | SED:2, SER:2, ASR:10 |
| **Lambda Timeout** | 30秒 | 60秒 |
| **SQS可視性タイムアウト** | 15分 | 5分 |

---

## 🔄 Phase 1: FIFO Queue移行（目標: 2025-12-19）

### 目的

- **順序保証**: 同一デバイスの録音を時系列順に処理
- **重複排除**: 同じ録音を2回処理しない
- **並列数制御**: デバイス単位で並列実行を制御

### Standard Queue（現在）の問題

```
Device A: [録音1] [録音2] [録音3]
Device B: [録音1] [録音2] [録音3]

↓ Standard Queueでは...

処理順序: A1, B2, A3, B1, A2, B3 （バラバラ）
- 新旧の録音が混在
- 同じ録音が2回処理される可能性
```

### FIFO Queue（移行後）の動作

```
Device A: [録音1] → [録音2] → [録音3]  （順次処理）
Device B: [録音1] → [録音2] → [録音3]  （順次処理）
Device C: [録音1] → [録音2] → [録音3]  （順次処理）

ただし、Device A/B/Cは並列処理可能（最大2並列）
```

### 実装タスク

#### 1. FIFO Queue作成

```bash
# SED用FIFO Queue
aws sqs create-queue \
  --queue-name watchme-sed-queue-v2.fifo \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "true",
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:754724220380:watchme-sed-dlq.fifo\",\"maxReceiveCount\":3}"
  }'

# SER用FIFO Queue
aws sqs create-queue \
  --queue-name watchme-ser-queue-v2.fifo \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "true",
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:754724220380:watchme-ser-dlq.fifo\",\"maxReceiveCount\":3}"
  }'

# ASR用FIFO Queue
aws sqs create-queue \
  --queue-name watchme-asr-queue-v2.fifo \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "true",
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:754724220380:watchme-asr-dlq.fifo\",\"maxReceiveCount\":3}"
  }'
```

#### 2. audio-processor Lambda修正

```python
import hashlib
import json

def get_message_group_id(device_id: str, api_type: str) -> str:
    """
    Message Group ID: デバイスごと・API種別ごとにグループ化
    同じグループ内のメッセージは順序保証される
    """
    return f"{device_id}-{api_type}"

def get_deduplication_id(device_id: str, recorded_at: str, api_type: str) -> str:
    """
    Deduplication ID: 重複排除
    同じIDのメッセージは5分以内に2回送信されない
    """
    unique_string = f"{device_id}-{recorded_at}-{api_type}"
    return hashlib.sha256(unique_string.encode()).hexdigest()

def send_to_fifo_queue(sqs, queue_url, device_id, recorded_at, file_path, api_type):
    """FIFO Queueにメッセージ送信"""
    message_body = json.dumps({
        "device_id": device_id,
        "recorded_at": recorded_at,
        "file_path": file_path
    })

    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=message_body,
        MessageGroupId=get_message_group_id(device_id, api_type),
        MessageDeduplicationId=get_deduplication_id(device_id, recorded_at, api_type)
    )

    print(f"Sent to FIFO queue: {api_type}, MessageId: {response['MessageId']}")
    return response

# Lambda handler
def lambda_handler(event, context):
    # S3イベントからファイル情報取得
    device_id = extract_device_id(event)
    recorded_at = extract_recorded_at(event)
    file_path = extract_file_path(event)

    # 3つのFIFO Queueに並列送信
    send_to_fifo_queue(sqs, ASR_FIFO_QUEUE_URL, device_id, recorded_at, file_path, "asr")
    send_to_fifo_queue(sqs, SED_FIFO_QUEUE_URL, device_id, recorded_at, file_path, "sed")
    send_to_fifo_queue(sqs, SER_FIFO_QUEUE_URL, device_id, recorded_at, file_path, "ser")

    return {"status": "success"}
```

#### 3. Lambda Workerのイベントソースマッピング更新

```bash
# 既存のStandard Queue接続を無効化
aws lambda update-event-source-mapping \
  --uuid <existing-mapping-uuid> \
  --enabled false

# 新しいFIFO Queue接続を作成
aws lambda create-event-source-mapping \
  --function-name watchme-sed-worker \
  --event-source-arn arn:aws:sqs:ap-southeast-2:754724220380:watchme-sed-queue-v2.fifo \
  --batch-size 1 \
  --enabled true
```

#### 4. デプロイ・切り替え手順

1. ✅ FIFO Queue作成
2. ✅ audio-processor修正・テスト
3. ✅ Lambda Workerのイベントソースマッピング作成
4. ⚠️ 一時的にStandard/FIFO両方を監視
5. ✅ Standard Queueが空になったら無効化
6. ✅ Standard Queue削除

### 期待効果

| 項目 | Standard Queue | FIFO Queue |
|------|---------------|------------|
| **順序保証** | なし | デバイス単位であり |
| **重複処理** | 可能性あり | 自動排除 |
| **並列制御** | Lambda並列数のみ | Message Group単位 |
| **スケーラビリティ** | 低 | 高（デバイス数に応じて） |

---

## 🚀 Phase 2: Auto Scaling（目標: 2026-01-31）

### 現状の問題

**EC2単一インスタンス（t4g.large）**:
- 固定リソース: 2 vCPU, 8GB RAM
- スケール不可: 負荷が増えても対応できない
- 単一障害点: EC2停止 = 全サービス停止

### ECS Fargate + Auto Scaling案

#### アーキテクチャ変更

```
【現在】
EC2 (t4g.large)
├─ Behavior API (Docker)
├─ Emotion API (Docker)
└─ Vibe Transcriber (Docker)

【Phase 2】
Application Load Balancer
├─ ECS Fargate: Behavior API (2-10タスク)
├─ ECS Fargate: Emotion API (2-10タスク)
└─ ECS Fargate: Vibe Transcriber (2-10タスク)
```

#### ECS Task定義

```yaml
# Behavior Features API
task_definition:
  family: watchme-behavior-features
  cpu: 512          # 0.5 vCPU per task
  memory: 1024      # 1GB per task
  container:
    image: 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-behavior-analysis-feature-extractor:latest
    port: 8017
    healthCheck:
      command: ["CMD-SHELL", "curl -f http://localhost:8017/health || exit 1"]
      interval: 30
      timeout: 10
      retries: 3

# Auto Scaling設定
autoscaling:
  min_capacity: 2   # 最小2タスク
  max_capacity: 10  # 最大10タスク
  target_tracking:
    metric: ECSServiceAverageCPUUtilization
    target_value: 70.0
    scale_out_cooldown: 60
    scale_in_cooldown: 300
```

#### コスト比較

| 項目 | EC2 (現在) | ECS Fargate (Phase 2) |
|------|-----------|---------------------|
| **通常時（低負荷）** | $50/月（固定） | $20/月（2タスク） |
| **ピーク時（高負荷）** | $50/月（固定） | $100/月（10タスク） |
| **実際のコスト** | $50/月 | 約$30/月（90%低負荷 + 10%高負荷） |
| **スケーラビリティ** | ❌ なし | ✅ 自動スケール |
| **可用性** | ❌ 単一障害点 | ✅ Multi-AZ |

**結論**: Phase 2実装により、**コストは削減され、スケーラビリティは大幅に向上**

### 実装タスク

1. ✅ ECRリポジトリ準備（既存利用）
2. ⬜ ECS Cluster作成
3. ⬜ Task Definition作成
4. ⬜ Application Load Balancer作成
5. ⬜ ECS Service作成（Auto Scaling有効）
6. ⬜ CloudWatch Logs統合
7. ⬜ 段階的切り替え（Blue/Green Deployment）

---

## 🛡️ Phase 3: Circuit Breaker + Multi-Region（目標: 2026-02-28）

### Circuit Breaker Pattern

**目的**: 障害の連鎖防止、自動復旧

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            # Circuit Open: リクエストを即座に拒否
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"  # 復旧試行
            else:
                # メッセージを遅延キューに移動
                move_to_delay_queue(*args, **kwargs)
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                # 成功 → Circuit閉じる
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                # 失敗が閾値を超えた → Circuit開く
                self.state = "OPEN"
                send_alarm("API Circuit Breaker OPEN")
            raise
```

### Multi-Region対応

**目的**: 災害対策、レイテンシ削減

```
【Phase 3】
Region: ap-southeast-2 (Sydney) - Primary
Region: ap-northeast-1 (Tokyo) - Secondary

Route 53 Failover Routing Policy
├─ Primary: Sydney ECS Cluster
└─ Secondary: Tokyo ECS Cluster (同期レプリケーション)
```

---

## 📊 拡張性：新しい分析軸の追加

### 追加手順（テンプレート化）

新しい分析API（例: Sentiment Analysis）を追加する場合：

```yaml
# 1. SQS FIFO Queue作成
queue_name: watchme-sentiment-queue.fifo
concurrent_limit: 2  # EC2 CPU使用量に応じて調整
visibility_timeout: 300
max_retries: 3

# 2. Lambda Worker作成
function_name: watchme-sentiment-worker
timeout: 60
reserved_concurrency: 2

# 3. EC2 API追加（Phase 1）または ECS Task追加（Phase 2+）
ecs_task:
  cpu: 512
  memory: 1024
  autoscaling:
    min: 2
    max: 10

# 4. audio-processor修正
send_to_fifo_queue(sqs, SENTIMENT_FIFO_QUEUE_URL, device_id, recorded_at, file_path, "sentiment")

# 5. aggregator-checker修正
required_features = ["vibe", "behavior", "emotion", "sentiment"]  # 4つに増加
```

**所要時間**: 半日〜1日（テンプレート化により高速化）

---

## 📈 スケーラビリティ目標達成度

| ユーザー数 | Phase 0 | Phase 1 | Phase 2 | Phase 3 |
|-----------|---------|---------|---------|---------|
| **1人** | ✅ 安定 | ✅ 安定 | ✅ 安定 | ✅ 安定 |
| **10人** | ⚠️ 可能 | ✅ 安定 | ✅ 安定 | ✅ 安定 |
| **100人** | ❌ 不可 | ⚠️ 可能 | ✅ 安定 | ✅ 安定 |
| **1000人** | ❌ 不可 | ❌ 不可 | ⚠️ 可能 | ✅ 安定 |

---

## 🔍 監視・運用

### CloudWatch Alarm設定（Phase 1で実施）

```bash
# SQS Message Age監視
aws cloudwatch put-metric-alarm \
  --alarm-name watchme-sed-queue-message-age \
  --alarm-description "SED Queue message age > 10 minutes" \
  --metric-name ApproximateAgeOfOldestMessage \
  --namespace AWS/SQS \
  --statistic Maximum \
  --period 300 \
  --threshold 600 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 1

# Lambda Error Rate監視
aws cloudwatch put-metric-alarm \
  --alarm-name watchme-sed-worker-errors \
  --alarm-description "SED Worker error rate > 10%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

---

## 📚 関連ドキュメント

- [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) - 既知の問題と緊急対応
- [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md) - 処理アーキテクチャ詳細
- [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) - 技術仕様
- [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md) - 運用ガイド

---

## 📞 実装サポート

各フェーズの実装時に参照すべきコマンド・コード例は、このドキュメントに記載しています。

**進捗管理**:
- [ ] Phase 0: 完了（2025-12-12）
- [ ] Phase 1: FIFO Queue移行（目標: 2025-12-19）
- [ ] Phase 2: Auto Scaling（目標: 2026-01-31）
- [ ] Phase 3: Circuit Breaker + Multi-Region（目標: 2026-02-28）
