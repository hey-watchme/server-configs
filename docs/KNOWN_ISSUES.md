# WatchMe 既知の問題と対応TODO

最終更新: 2026-01-25

このドキュメントは、WatchMeシステムにおける既知の問題を**本質的な課題別**に整理し、今後対応が必要な内容を記録します。

**⚠️ 重要**: スケーラビリティ改善の包括的な計画は [SCALABILITY_ROADMAP.md](./SCALABILITY_ROADMAP.md) を参照してください。

---

## 🎯 本質的な課題の全体像

WatchMeシステムで発生している様々な症状（DLQ蓄積、SQSキュー詰まり、処理失敗等）は、以下の**4つの本質的な課題**に起因しています：

| 課題 | 優先度 | 状態 | 影響範囲 |
|------|--------|------|---------|
| **1. タイムアウト・遅延問題** | ⭐⭐⭐⭐⭐ | 🔴 未解決 | Lambda Worker全体、DLQ蓄積 |
| **2. 監視・検知体制の欠如** | ⭐⭐⭐⭐⭐ | 🟡 部分対応 | 問題の長期放置 |
| **3. アーキテクチャ不整合** | ⭐⭐⭐ | 🔴 未解決 | デモデバイス処理 |
| **4. APIエンドポイント構造の不統一** | ⭐⭐⭐⭐ | 🔴 未解決 | 設定ミス、推測による誤り |
| **5. CORS設定の分散・不統一** | ⭐⭐⭐⭐ | 🔴 未解決 | API修正時に他APIが壊れる |

---

## 🔴 課題1: タイムアウト・遅延問題（根本原因・未解決）

### 概要

Lambda WorkerからEC2 APIへのHTTPSアクセスが30秒以上かかり、タイムアウトする問題。これが**すべてのDLQ蓄積問題の根本原因**となっています。

### 具体的な症状

#### 症状1-A: Lambda WorkerのHTTPSタイムアウト（2026-01-22発見）

**現象**:
- `https://api.hey-watch.me` 経由: **30秒以上** → タイムアウト
- `http://3.24.16.82:ポート番号` 直接: **1-2秒** → 正常

**影響**:
- Lambda Worker（asr/sed/ser-worker）が3回リトライ → DLQ行き
- SED DLQ: 10件蓄積（2026-01-22時点）

**応急処置（2026-01-22実施）**:
```bash
# Lambda環境変数を直接IP経由に変更
aws lambda update-function-configuration --function-name watchme-asr-worker \
  --environment 'Variables={API_BASE_URL=http://3.24.16.82:8013,...}'

aws lambda update-function-configuration --function-name watchme-sed-worker \
  --environment 'Variables={API_BASE_URL=http://3.24.16.82:8017,...}'

aws lambda update-function-configuration --function-name watchme-ser-worker \
  --environment 'Variables={API_BASE_URL=http://3.24.16.82:8018,...}'
```

**効果**: ✅ タイムアウト回避、⚠️ 根本原因は未解決

---

#### 症状1-B: `/health` エンドポイントのタイムアウト（2025-12-11発見）

**現象**:
- コンテナ内部から: **0.8秒** → 正常
- 外部（Nginx/Cloudflare経由）から: **30秒以上** → タイムアウト
- `/async-process`は外部からも **1.6秒** → 正常

**影響**:
- Dockerコンテナがunhealthyと判定される
- Lambda Workerからの処理リクエストも影響を受ける

---

#### 症状1-C: API一時的unhealthy状態（2025-12-11発見）

**現象**:
- Behavior/Emotion APIが突然unhealthyになる
- `/health`エンドポイントがタイムアウト
- 実際の処理は正常に動作している

**影響**:
- Lambda Workerが処理できない → SQSメッセージ蓄積
- 49件のメッセージが溜まり、CPU 97%消費（2025-12-11事例）

**応急処置**:
- SQSキューパージ（⚠️ データ損失）
- APIコンテナ再起動

---

### 考えられる根本原因（要調査）

1. **Cloudflare設定の問題**
   - 過去に「Cloudflare Proxy問題」で51秒レスポンス（2025-12-29修正済み）
   - 現在はDNS Onlyだが、別の設定（SSL/TLS、Argo Smart Routing等）が影響？

2. **Nginx SSL/TLS設定の問題**
   - HTTPSのみ遅延が発生
   - SSL証明書検証タイムアウト

3. **EC2セキュリティグループ・ネットワーク問題**
   - HTTPSポート443へのアクセス制限
   - VPCルーティング問題

4. **API側の負荷・メモリ不足**
   - 特定の条件下でリソース枯渇
   - uvicorn/FastAPIの非同期処理の問題

---

### 恒久対策

#### 対策1: 根本原因の徹底調査（最優先 ⭐⭐⭐⭐⭐）

**調査手順**:

1. **Cloudflare設定の全確認**
   ```bash
   # レスポンス時間計測
   time curl -I https://api.hey-watch.me/behavior-analysis/features/health
   time curl -I http://3.24.16.82:8017/health

   # Cloudflare設定確認（ブラウザで）
   # - SSL/TLS設定
   # - Page Rules
   # - Firewall Rules
   # - Argo Smart Routing
   ```

2. **Nginx SSL設定の確認**
   ```bash
   ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
   cat /etc/nginx/sites-available/api.hey-watch.me | grep -A 20 "ssl"
   nginx -T | grep -A 10 "api.hey-watch.me"
   ```

3. **EC2セキュリティグループ確認**
   ```bash
   aws ec2 describe-security-groups --region ap-southeast-2 | \
     jq '.SecurityGroups[] | select(.GroupName | contains("watchme"))'
   ```

4. **Lambda VPC設定確認**
   ```bash
   aws lambda get-function --function-name watchme-sed-worker \
     --region ap-southeast-2 | jq '.Configuration.VpcConfig'
   ```

5. **APIログの詳細分析**
   ```bash
   # タイムアウト時のNginxアクセスログ
   ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
   tail -f /var/log/nginx/access.log | grep "behavior-analysis"

   # APIコンテナログ
   docker logs behavior-analysis-feature-extractor -f | grep -i "timeout\|slow\|error"
   ```

---

#### 対策2: 代替アーキテクチャの検討

**案1: Lambda VPC配置 + プライベートIP接続**
- Lambda関数をVPC内に配置
- EC2のプライベートIPで直接アクセス
- HTTPSの問題を完全に回避

**案2: API Gateway経由**
- API GatewayをHTTPSエンドポイントとして配置
- Lambda → API Gateway → EC2
- 安定したHTTPS接続

**案3: HTTPのみ運用（非推奨）**
- セキュリティリスクあり
- 一時的な回避策としてのみ検討

---

## 🟡 課題2: 監視・検知体制の欠如（部分対応済み）

### 概要

DLQに数百件のメッセージが蓄積しても、Lambda関数がエラーを出し続けても、気づけない問題。

### 具体的な症状

#### 症状2-A: DLQ大量蓄積の長期放置

**事例1（2025-12-12）**:
- `watchme-dashboard-analysis-dlq`: **991件**蓄積
- 原因: Lambda関数で`requests`モジュール不足（インポートエラー）
- 期間: **3日間**放置
- 発見: 手動確認するまで気づかず

**事例2（2026-01-21）**:
- `watchme-sed-dlq-v2.fifo`: **671件**
- `watchme-ser-dlq-v2.fifo`: **670件**
- 合計: **1,342件**
- 発見: 定期確認で発覚

#### 症状2-B: 週1回のDLQ蓄積パターン（2026-01-09発見）

**パターン**:
- 週1回程度、数百件のDLQメッセージが蓄積
- **4週間連続**で発生
- 毎回手動でパージ

**主な原因**:
- デモデバイス処理不整合（約70%）
- タイムアウト問題（残り30%）

---

### 恒久対策

#### 対策1: CloudWatch Alarm実装（最優先 ⭐⭐⭐⭐⭐）

**監視項目**:

1. **DLQメッセージ数監視**
   ```bash
   # 全DLQに対してアラーム設定
   for dlq in watchme-asr-dlq-v2.fifo watchme-sed-dlq-v2.fifo \
               watchme-ser-dlq-v2.fifo watchme-dashboard-summary-dlq \
               watchme-dashboard-analysis-dlq; do

     aws cloudwatch put-metric-alarm \
       --alarm-name "${dlq}-alarm" \
       --alarm-description "DLQに10件以上メッセージが溜まった" \
       --metric-name ApproximateNumberOfMessagesVisible \
       --namespace AWS/SQS \
       --statistic Average \
       --period 300 \
       --evaluation-periods 1 \
       --threshold 10 \
       --comparison-operator GreaterThanThreshold \
       --dimensions Name=QueueName,Value=${dlq} \
       --alarm-actions arn:aws:sns:ap-southeast-2:754724220380:watchme-alerts \
       --region ap-southeast-2
   done
   ```

2. **Lambda Error Rate監視**
   ```bash
   # 全Lambda関数のエラー率監視
   for func in watchme-asr-worker watchme-sed-worker watchme-ser-worker \
               watchme-audio-processor watchme-aggregator-checker \
               watchme-dashboard-summary-worker watchme-dashboard-analysis-worker; do

     aws cloudwatch put-metric-alarm \
       --alarm-name "${func}-error-rate" \
       --metric-name Errors \
       --namespace AWS/Lambda \
       --statistic Sum \
       --period 300 \
       --evaluation-periods 2 \
       --threshold 5 \
       --comparison-operator GreaterThanThreshold \
       --dimensions Name=FunctionName,Value=${func} \
       --alarm-actions arn:aws:sns:ap-southeast-2:754724220380:watchme-alerts \
       --region ap-southeast-2
   done
   ```

3. **SQS Message Age監視**
   ```bash
   # メッセージが10分以上滞留したらアラート
   aws cloudwatch put-metric-alarm \
     --alarm-name watchme-sed-queue-age \
     --metric-name ApproximateAgeOfOldestMessage \
     --namespace AWS/SQS \
     --statistic Maximum \
     --period 300 \
     --evaluation-periods 1 \
     --threshold 600 \
     --comparison-operator GreaterThanThreshold \
     --dimensions Name=QueueName,Value=watchme-sed-queue-v2.fifo \
     --region ap-southeast-2
   ```

4. **API Health Check監視**
   - CloudWatch Synthetics Canaryで5分ごとにヘルスチェック
   - 3回連続失敗 → SNS通知

---

#### 対策2: SNS通知先の設定

```bash
# SNSトピック作成
aws sns create-topic --name watchme-alerts --region ap-southeast-2

# メール購読
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-southeast-2:754724220380:watchme-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region ap-southeast-2
```

---

#### 対策3: DLQ再処理スクリプト

DLQからメッセージを元のキューに戻すスクリプト:

```bash
#!/bin/bash
# redrive-dlq.sh

SOURCE_QUEUE_URL="$1"
TARGET_QUEUE_URL="$2"

if [ -z "$SOURCE_QUEUE_URL" ] || [ -z "$TARGET_QUEUE_URL" ]; then
  echo "Usage: $0 <source-dlq-url> <target-queue-url>"
  exit 1
fi

count=0
while true; do
  MESSAGE=$(aws sqs receive-message \
    --queue-url $SOURCE_QUEUE_URL \
    --max-number-of-messages 1 \
    --region ap-southeast-2)

  if [ -z "$MESSAGE" ] || [ "$MESSAGE" == "null" ]; then
    echo "✅ 完了: ${count}件のメッセージを移動しました"
    break
  fi

  BODY=$(echo $MESSAGE | jq -r '.Messages[0].Body')
  RECEIPT_HANDLE=$(echo $MESSAGE | jq -r '.Messages[0].ReceiptHandle')

  # 元のキューに送信
  aws sqs send-message \
    --queue-url $TARGET_QUEUE_URL \
    --message-body "$BODY" \
    --region ap-southeast-2

  # DLQから削除
  aws sqs delete-message \
    --queue-url $SOURCE_QUEUE_URL \
    --receipt-handle "$RECEIPT_HANDLE" \
    --region ap-southeast-2

  count=$((count + 1))
  echo "移動: ${count}件"
done
```

---

## 🟢 課題3: アーキテクチャ不整合（未解決）

### 概要

デモデバイスのデータ生成フローが、音声処理パイプラインと不整合を起こしている。

### 具体的な症状

#### デモデバイス処理の問題（2026-01-09発見）

**デバイスID**: `9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93`

**問題の構造**:
1. `demo-generator-v2` LambdaがSpotデータを直接Supabaseに生成
2. **実際の音声ファイルはS3に存在しない**
3. しかし、`audio-processor` LambdaがS3イベントを受信（なぜ？）
4. SQSに送信 → Lambda Worker起動
5. 存在しない音声ファイルを処理しようとして失敗
6. 3回リトライ → DLQ行き

**影響範囲**:
- SED DLQ: 約70%がデモデバイス（529件中370件）
- SER DLQ: 約70%がデモデバイス（527件中370件）
- ASR DLQ: 影響なし

---

### 恒久対策

#### 対策1: audio-processorにスキップロジック追加（推奨 ⭐⭐⭐⭐）

```python
# audio-processor Lambda
DEMO_DEVICE_IDS = [
    '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93'
]

def lambda_handler(event, context):
    for record in event['Records']:
        s3_key = record['s3']['object']['key']

        # デバイスIDを抽出
        device_id = extract_device_id(s3_key)

        # デモデバイスはスキップ
        if device_id in DEMO_DEVICE_IDS:
            print(f"Skipping demo device: {device_id}")
            continue

        # 通常処理
        send_to_sqs(s3_key, device_id)
```

---

#### 対策2: demo-generatorが実際の音声ファイルを配置（代替案）

デモデータ生成時に、実際の音声ファイル（無音またはダミー音声）をS3に配置する。

**メリット**: パイプライン全体が一貫して動作
**デメリット**: S3ストレージコスト、処理コスト増

---

## 🔴 課題4: APIエンドポイント構造の不統一（未解決）

### 概要（2026-01-23発見）

各APIでエンドポイント構造に統一されたルールがないため、AIや開発者が「このAPIならこのエンドポイントだろう」と推測すると間違える。

### 具体例

- Vibe Transcriber: `/async-process` と `/fetch-and-transcribe` の両方が存在
- Behavior Features: `/async-process` のみ
- Emotion Features: `/async-process` のみ

**問題**: 構造に一貫性がないため、パスの推測・変換が失敗し、設定ミスを引き起こす。

### 実際に発生した問題（2026-01-23）

Claude（AI）が「Vibe Transcriberは `/fetch-and-transcribe` を使うべき」と誤推測し、Lambda環境変数を誤った値に設定。結果として404エラーが発生し、処理が停止した。

### 恒久対策

全APIで `/async-process` エンドポイントに統一し、推測不要な明確なルールを確立する。

---

## 🔴 課題5: CORS設定の分散・不統一（未解決）

### 概要（2026-01-25発見）

CORS（Cross-Origin Resource Sharing）設定がNginxとFastAPIの両方に分散しており、APIを修正すると別のAPIが壊れる問題。

### 発生した問題

**事例（2026-01-25 Business API）**:
1. 他のAPI（Aggregator等）を修正
2. 依存ライブラリ更新 or Docker再ビルドでCORSミドルウェアの挙動が変化
3. Nginx側のCORS設定（`*`）とFastAPI側のCORS設定（`https://business.hey-watch.me`）が重複
4. レスポンスヘッダーが`Access-Control-Allow-Origin: https://business.hey-watch.me, *`となる
5. ブラウザがCORSエラーを返す

**エラーメッセージ**:
```
Access to fetch at 'https://api.hey-watch.me/business/api/support-plans'
has been blocked by CORS policy: The 'Access-Control-Allow-Origin' header
contains multiple values 'https://business.hey-watch.me, *', but only one is allowed.
```

### 現状の問題

| API | CORS設定場所 | リスク |
|-----|-------------|-------|
| Business API | FastAPI（修正済み） | ✅ 解決 |
| Aggregator | Nginx | ❌ FastAPIにCORS追加したら壊れる |
| Profiler | Nginx | ❌ 同上 |
| Behavior Features | Nginx | ❌ 同上 |
| Emotion Features | Nginx | ❌ 同上 |
| Vibe Transcriber | Nginx | ❌ 同上 |
| その他全API | Nginx | ❌ 同上 |

**根本原因**: 設定が分散しているため、どこかを触ると別の場所が壊れる

---

### 恒久対策

#### 対策: 全APIのCORS設定を統一（推奨 ⭐⭐⭐⭐）

**方針**: 全てFastAPI側で管理し、Nginx側からCORS設定を削除

**理由**:
- アプリケーション側で制御する方が柔軟
- オリジンごとの細かい制御が可能
- 設定が1箇所に集約され、管理しやすい

**作業手順**:

1. **各APIのFastAPIにCORSミドルウェアを追加**
   ```python
   from fastapi.middleware.cors import CORSMiddleware

   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # または特定のオリジン
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. **Nginx設定からCORS関連を削除**
   ```nginx
   # 削除する行
   add_header "Access-Control-Allow-Origin" "*";
   add_header "Access-Control-Allow-Methods" "GET, POST, OPTIONS";
   add_header "Access-Control-Allow-Headers" "Content-Type, Authorization";

   # OPTIONSリクエスト処理も削除
   if ($request_method = "OPTIONS") {
       return 204;
   }
   ```

3. **Nginx設定をEC2に反映**
   ```bash
   ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
   cd /home/ubuntu/watchme-server-configs
   git pull origin main
   sudo cp production/sites-available/api.hey-watch.me /etc/nginx/sites-available/
   sudo nginx -t && sudo systemctl reload nginx
   ```

**対象API一覧**:
- [ ] Aggregator API（ポート8050）
- [ ] Profiler API（ポート8051）
- [ ] Behavior Features API（ポート8017）
- [ ] Emotion Features API（ポート8018）
- [ ] Vibe Transcriber API（ポート8013）
- [ ] Vault API（ポート8000）
- [ ] Avatar Uploader API（ポート8014）
- [ ] Janitor API（ポート8030）
- [ ] Demo Generator API（ポート8020）
- [ ] QR Code Generator API（ポート8021）

**参照ドキュメント**: [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) のCORS設定セクション

---

## 📊 全DLQ一覧と確認コマンド

### DLQ一覧

| DLQ名 | 処理段階 | 失敗原因 |
|-------|---------|---------|
| `watchme-asr-dlq-v2.fifo` | Spot分析（ASR） | Vibe API停止、タイムアウト |
| `watchme-sed-dlq-v2.fifo` | Spot分析（SED） | Behavior API停止、unhealthy、タイムアウト |
| `watchme-ser-dlq-v2.fifo` | Spot分析（SER） | Emotion API停止、タイムアウト |
| `watchme-dashboard-summary-dlq` | Daily集計 | Aggregator API停止 |
| `watchme-dashboard-analysis-dlq` | Daily分析 | Profiler API停止、プッシュ通知失敗 |

### 全DLQ一括確認コマンド

```bash
echo "=== Spot分析DLQ（FIFO Queue） ==="
aws sqs get-queue-attributes --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-dlq-v2.fifo --attribute-names ApproximateNumberOfMessages --region ap-southeast-2 | jq -r '"ASR DLQ: " + .Attributes.ApproximateNumberOfMessages'

aws sqs get-queue-attributes --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-dlq-v2.fifo --attribute-names ApproximateNumberOfMessages --region ap-southeast-2 | jq -r '"SED DLQ: " + .Attributes.ApproximateNumberOfMessages'

aws sqs get-queue-attributes --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-dlq-v2.fifo --attribute-names ApproximateNumberOfMessages --region ap-southeast-2 | jq -r '"SER DLQ: " + .Attributes.ApproximateNumberOfMessages'

echo ""
echo "=== Daily分析DLQ（Standard Queue） ==="
aws sqs get-queue-attributes --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-summary-dlq --attribute-names ApproximateNumberOfMessages --region ap-southeast-2 | jq -r '"Dashboard Summary DLQ: " + .Attributes.ApproximateNumberOfMessages'

aws sqs get-queue-attributes --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-analysis-dlq --attribute-names ApproximateNumberOfMessages --region ap-southeast-2 | jq -r '"Dashboard Analysis DLQ: " + .Attributes.ApproximateNumberOfMessages'
```

### 全DLQ一括パージコマンド

**⚠️ 警告**: パージは**データ損失**を伴います。削除前にメッセージ内容を確認することを推奨。

```bash
# Spot分析DLQ（FIFO Queue）
aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-dlq-v2.fifo --region ap-southeast-2
aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-dlq-v2.fifo --region ap-southeast-2
aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-dlq-v2.fifo --region ap-southeast-2

# Daily分析DLQ（Standard Queue）
aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-summary-dlq --region ap-southeast-2
aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-analysis-dlq --region ap-southeast-2

echo "🎉 全DLQのパージ完了"
```

---

## 📝 実装チェックリスト

### ✅ フェーズ0: 緊急安定化対策（完了: 2025-12-12）

- [x] Lambda並列実行数の制限（2並列/10並列）
- [x] Lambda Worker timeout を 60秒に延長
- [x] 可視性タイムアウトを300秒に調整

### ✅ フェーズ1: 応急処置（完了: 2026-01-22）

- [x] Lambda Worker環境変数を直接IP経由に変更
- [x] SED DLQパージ（10件削除）

### 🚧 フェーズ2: 監視体制構築（目標: 2026-01-29）

- [ ] DLQ監視アラーム（5つのDLQ）
- [ ] Lambda Error Rate監視（7つのLambda）
- [ ] SQS Message Age監視
- [ ] SNS通知先設定
- [ ] CloudWatch Synthetics Canary（API Health Check）
- [ ] DLQ再処理スクリプト作成

### 🚧 フェーズ3: 根本原因調査（目標: 2026-02-05）

- [ ] Cloudflare設定の全確認
- [ ] Nginx SSL設定の確認
- [ ] EC2セキュリティグループ確認
- [ ] Lambda VPC設定確認
- [ ] APIログの詳細分析
- [ ] **根本原因の特定と修正**

### 🚧 フェーズ4: アーキテクチャ修正（目標: 2026-02-05）

- [ ] audio-processorにデモデバイススキップロジック追加
- [ ] デモデバイスDLQの確認・パージ

---

## 📚 関連ドキュメント

- [処理アーキテクチャ](./PROCESSING_ARCHITECTURE.md) - イベント駆動型アーキテクチャの詳細
- [技術仕様](./TECHNICAL_REFERENCE.md) - Lambda関数とSQSの設定
- [運用ガイド](./OPERATIONS_GUIDE.md) - デプロイ・運用手順
- [スケーラビリティロードマップ](./SCALABILITY_ROADMAP.md) - 長期改善計画

---

## 📞 緊急時の対応フロー

### 問題発生時の基本手順

1. **CloudWatch Logs でエラー確認**
   ```bash
   aws logs tail /aws/lambda/watchme-sed-worker --region ap-southeast-2 --since 10m
   ```

2. **DLQの状態確認**（上記の一括確認コマンドを実行）

3. **APIコンテナの状態確認**
   ```bash
   ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
   docker ps | grep -E "behavior|emotion|vibe"
   ```

4. **APIコンテナの再起動**
   ```bash
   cd /home/ubuntu/behavior-analysis-feature-extractor
   docker-compose -f docker-compose.prod.yml restart
   ```

5. **それでも解決しない場合**
   - DLQメッセージを1件取得して内容確認
   - 問題が明確なら redrive-dlq.sh で再処理
   - 不明な場合のみパージを検討（最終手段）

**重要**: DLQパージは**データ損失**を伴うため、本番環境では慎重に判断すること。
