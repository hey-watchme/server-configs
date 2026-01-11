# WatchMe 既知の問題と対応TODO

最終更新: 2025-12-12

このドキュメントは、WatchMeシステムにおける既知の問題と、今後対応が必要な課題を記録します。

**⚠️ 重要**: スケーラビリティ改善の包括的な計画は [SCALABILITY_ROADMAP.md](./SCALABILITY_ROADMAP.md) を参照してください。

---

## 🚨 優先度：高

### 1. DLQ定期蓄積問題（週1回発生）

**発見日**: 2026-01-09（4週間連続で発生）

#### 問題の概要

週に1回程度、SED/SER DLQに数百件のメッセージが蓄積する問題が**4週間連続**で発生しています。毎回手動でパージしていますが、根本原因は未解決です。

#### 具体的な症状

1. **DLQへの大量蓄積（2026-01-09時点）**
   - `watchme-sed-dlq-v2.fifo`: **514件**
   - `watchme-ser-dlq-v2.fifo`: **513件**
   - `watchme-asr-dlq-v2.fifo`: 0件
   - **合計: 1,027件**のメッセージが蓄積

2. **発生頻度**
   - 週1回程度
   - 過去4週間連続で発生（2025-12-中旬〜2026-01-09）

3. **影響**
   - SED/SER処理が一部失敗（音響検出・感情分析が欠損）
   - Daily/Weekly分析に影響する可能性
   - システムパフォーマンス低下はなし（DLQは処理対象外のため）

#### 応急処置（毎回実施）

```bash
# DLQ状態確認
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-dlq-v2.fifo \
  --attribute-names ApproximateNumberOfMessages \
  --region ap-southeast-2

aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-dlq-v2.fifo \
  --attribute-names ApproximateNumberOfMessages \
  --region ap-southeast-2

# DLQパージ（削除）
aws sqs purge-queue \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-dlq-v2.fifo \
  --region ap-southeast-2

aws sqs purge-queue \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-dlq-v2.fifo \
  --region ap-southeast-2
```

**⚠️ 注意**: パージは**データ損失**を伴います。削除前にメッセージの内容を確認することを推奨。

#### 考えられる原因（未調査）

1. **API一時的な障害**
   - Behavior/Emotion APIのunhealthy状態
   - メモリ不足・CPU過負荷
   - ネットワークタイムアウト

2. **Lambda Worker タイムアウト**
   - 30秒タイムアウトで処理完了できないケース
   - → 3回リトライ後にDLQへ移動

3. **データ品質の問題**
   - 音声ファイルの品質が低い
   - 無音・ノイズのみの録音
   - ファイル破損

4. **環境変数・認証情報の問題**
   - Hume API認証エラー
   - S3アクセス権限エラー
   - Supabase接続エラー

5. **デモデバイスの処理不整合（仮説）⭐ 有力**
   - **発見日**: 2026-01-09
   - **DLQ分析結果**: デモデバイス（9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93）が70%を占める
   - **問題の構造**:
     - デモデバイスは demo-generator-v2 Lambda が Spot データを直接 Supabase に生成
     - 実際の音声ファイルは存在しない（S3にアップロードされない）
     - しかし、audio-processor Lambda が S3 イベントを受信して SQS に送信してしまう
     - Lambda Worker（ASR/SED/SER）が存在しない音声ファイルを処理しようとして失敗
     - 3回リトライ → DLQ行き
   - **影響範囲**:
     - SED DLQ: 529件（約70%がデモデバイス）
     - SER DLQ: 527件（約70%がデモデバイス）
     - ASR DLQ: 0件（文字起こしは正常？）
   - **根本原因**:
     - デモデバイスのデータ生成フローが音声処理パイプラインと不整合
     - audio-processor がデモデバイスを特別扱いしていない
   - **解決策（案）**:
     - audio-processor にデモデバイスのスキップロジックを追加
     - または、demo-generator が S3 イベントをトリガーしないようにする
     - または、デモデバイス用の音声ファイルを実際に S3 に配置する

#### 恒久対策（未実施）

**対策1: DLQ監視アラートの実装 ⭐ 最優先**

CloudWatch Alarmでメッセージ数を監視：

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name watchme-sed-dlq-alarm \
  --alarm-description "SED DLQに10件以上メッセージが溜まった" \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=QueueName,Value=watchme-sed-dlq-v2.fifo \
  --region ap-southeast-2
```

**対策2: DLQメッセージ内容の調査**

DLQに溜まったメッセージの内容を1件取り出して調査：

```bash
# メッセージ取得（削除しない）
aws sqs receive-message \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-dlq-v2.fifo \
  --max-number-of-messages 1 \
  --region ap-southeast-2 | jq .

# エラーパターンの分析
# - どのデバイスIDが多いか
# - recorded_atの時間帯パターン
# - file_pathの特徴
```

**対策3: Lambda Workerのエラーログ分析**

CloudWatch Logsで失敗パターンを調査：

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/watchme-sed-worker \
  --filter-pattern "ERROR" \
  --start-time $(date -u -v-7d +%s)000 \
  --region ap-southeast-2 | jq -r '.events[].message' | head -50
```

**対策4: API側のエラーログ確認**

EC2上のDockerコンテナログを確認：

```bash
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
docker logs behavior-analysis-feature-extractor --since 7d | grep -i "error\|fail\|timeout" | tail -100
docker logs emotion-analysis-feature-extractor --since 7d | grep -i "error\|fail\|timeout" | tail -100
```

**優先度**: ⭐⭐⭐⭐⭐（週1回発生しており、早急な調査が必要）

**調査期限**: 2週間以内に根本原因を特定すべき

#### 一時停止方法（Hume API課金回避）

**背景**: Hume APIはフリープランのため、本番環境で自動処理すると課金が発生します。

**停止方法**: Lambda ser-workerのエンドポイントURLを変更（2026-01-09実施）

```bash
# 停止（エンドポイントURLを無効化）
aws lambda update-function-configuration \
  --function-name watchme-ser-worker \
  --environment Variables="{API_BASE_URL=https://api.hey-watch.me-disabled}" \
  --region ap-southeast-2

# 再開（元のURLに戻す）
aws lambda update-function-configuration \
  --function-name watchme-ser-worker \
  --environment Variables="{API_BASE_URL=https://api.hey-watch.me}" \
  --region ap-southeast-2

# 再開時はDLQをパージ（溜まったエラーメッセージを削除）
aws sqs purge-queue \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-dlq-v2.fifo \
  --region ap-southeast-2
```

**効果**:
- ✅ Hume API呼び出しが停止（課金なし）
- ✅ 他のAPI（ASR/SED）は継続動作
- ✅ Emotion API自体は稼働（手動curlテスト可能）
- ⚠️ DLQに失敗メッセージが溜まる（再開時にパージ必要）

---

### 2. DLQ監視・アラート体制の不足

**発見日**: 2025-12-13

#### 問題の概要

Dead Letter Queue（DLQ）にメッセージが大量に蓄積しても、アラートがなく気づけない問題が発生しました。

#### 具体的な症状

1. **Lambda関数のエラーが長期間放置**
   - `watchme-dashboard-analysis-worker` Lambdaで`requests`モジュール不足
   - インポートエラーで関数が起動できず、3日間気づかず
   - DLQに991件のメッセージが蓄積（2025-12-10 ~ 2025-12-12）

2. **監視体制の不足**
   - DLQのメッセージ数を監視するアラートなし
   - Lambda関数のエラー率を監視するアラートなし
   - 手動で確認しない限り問題に気づけない

3. **DLQ処理方法の不明確さ**
   - DLQに溜まったメッセージを元のキューに戻す手順が不明確
   - パージ（削除）以外の選択肢がない
   - 大量メッセージの再処理方法が確立されていない

#### 応急処置（2025-12-13実施）

1. **Lambda関数の修正**
   ```bash
   cd /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-dashboard-analysis-worker
   ./build.sh
   aws lambda update-function-code --function-name watchme-dashboard-analysis-worker --zip-file fileb://function.zip --region ap-southeast-2
   ```

2. **DLQのパージ（記録を残して削除）**
   ```bash
   # DLQ_PURGE_LOG.mdに記録を残してから削除
   aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-analysis-dlq --region ap-southeast-2
   ```

3. **手動で最新データのDaily分析をトリガー**
   ```bash
   aws sqs send-message --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-summary-queue \
     --message-body '{"device_id":"...","local_date":"2025-12-13",...}' --region ap-southeast-2
   ```

**⚠️ 影響**: 過去のDaily分析（2025-12-10 ~ 2025-12-12）は実行されていない

#### 恒久対策の提案

**対策1: CloudWatch Alarmによる監視 ⭐ 最優先**

以下のメトリクスを監視し、SNS通知を設定：

1. **DLQメッセージ数監視**
   - メトリクス: `ApproximateNumberOfMessagesVisible`
   - 条件: > 10件
   - アクション: SNS → メール/Slack通知

2. **Lambda Error Rate監視**
   - メトリクス: `Errors / Invocations * 100`
   - 条件: > 10%（1時間で3データポイント）
   - アクション: SNS → メール/Slack通知

3. **Lambda Duration監視**
   - メトリクス: `Duration`
   - 条件: タイムアウト近く（例: > 800秒）
   - アクション: SNS → メール/Slack通知

**実装方法**（例: DLQ監視）:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name watchme-dashboard-analysis-dlq-alarm \
  --alarm-description "DLQに10件以上メッセージが溜まった" \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=QueueName,Value=watchme-dashboard-analysis-dlq \
  --alarm-actions arn:aws:sns:ap-southeast-2:754724220380:watchme-alerts
```

**対策2: DLQ再処理スクリプトの作成**

DLQからメッセージを元のキューに戻すスクリプトを用意：

```bash
#!/bin/bash
# redrive-dlq.sh - DLQから元のキューへメッセージを移動

SOURCE_QUEUE_URL="https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-analysis-dlq"
TARGET_QUEUE_URL="https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-analysis-queue"

while true; do
  MESSAGE=$(aws sqs receive-message --queue-url $SOURCE_QUEUE_URL --max-number-of-messages 1 --region ap-southeast-2)

  if [ -z "$MESSAGE" ]; then
    echo "No more messages in DLQ"
    break
  fi

  BODY=$(echo $MESSAGE | jq -r '.Messages[0].Body')
  RECEIPT_HANDLE=$(echo $MESSAGE | jq -r '.Messages[0].ReceiptHandle')

  # 元のキューに送信
  aws sqs send-message --queue-url $TARGET_QUEUE_URL --message-body "$BODY" --region ap-southeast-2

  # DLQから削除
  aws sqs delete-message --queue-url $SOURCE_QUEUE_URL --receipt-handle "$RECEIPT_HANDLE" --region ap-southeast-2

  echo "Moved 1 message"
done
```

**対策3: Lambda関数のデプロイ検証**

Lambda関数のデプロイ後、自動的に動作確認を行う：

1. デプロイ後にテストメッセージを送信
2. 正常に処理されることを確認
3. エラーがあれば即座にロールバック

**優先度**: ⭐⭐⭐⭐⭐（監視体制は即座に実装すべき）

---

### 2. SQSキュー詰まり問題（イベント駆動型アーキテクチャ）

**発見日**: 2025-12-11

#### 問題の概要

Behavior/Emotion APIが一時的にunhealthyになると、Lambda Worker（sed-worker/ser-worker）からのリクエストがタイムアウトし、SQSメッセージが溜まる問題が発生します。

#### 具体的な症状

1. **APIがunhealthyになる**
   - `/health` エンドポイントがタイムアウト（理由不明、処理自体は正常）
   - Dockerコンテナのヘルスチェックが失敗

2. **Lambda Workerがタイムアウト**
   - タイムアウト設定: 30秒
   - `/async-process` エンドポイントへのリクエストが30秒以内に202を返さない

3. **SQSメッセージが溜まる**
   - タイムアウトしたメッセージはSQSキューに戻る（可視性タイムアウト後）
   - 最大リトライ回数まで繰り返し処理を試行
   - 49件のメッセージが溜まった事例あり（2025-12-11）

4. **高負荷状態が継続**
   - 溜まったメッセージを処理するためCPU 97%を消費
   - 新しい録音が処理されない（古いメッセージを先に処理するため）
   - 場合によっては処理が追いつかない可能性

#### 応急処置（2025-12-11実施）

1. SQSキューをパージ（全メッセージ削除）
   ```bash
   aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue
   aws sqs purge-queue --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-queue
   ```

2. APIコンテナを再起動
   ```bash
   ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
   cd /home/ubuntu/behavior-analysis-feature-extractor && docker-compose -f docker-compose.prod.yml restart
   cd /home/ubuntu/emotion-analysis-feature-extractor && docker-compose -f docker-compose.prod.yml restart
   ```

**⚠️ 注意**: パージは本番環境では許容されない（データ損失）ため、恒久対策が必須。

---

## 📋 恒久対策の提案

### 対策1: Lambda Workerのタイムアウト延長 ⭐ 最優先

**現状**: 30秒
**推奨**: 60秒

**実装方法**:
```bash
aws lambda update-function-configuration --function-name watchme-ser-worker --timeout 60
aws lambda update-function-configuration --function-name watchme-sed-worker --timeout 60
aws lambda update-function-configuration --function-name watchme-asr-worker --timeout 60
```

**効果**:
- 一時的なAPI遅延に対応可能
- Cloudflare 100秒制限内に収まる
- タイムアウトによるメッセージ蓄積を軽減

**優先度**: ⭐⭐⭐⭐⭐（即座に実装可能）

---

### 対策2: DLQ（Dead Letter Queue）の適切な設定

**現状**: 設定済み（要確認）
**推奨設定**:
- 最大リトライ回数: 3回
- 3回失敗後 → DLQに移動
- DLQの定期的な監視・パージ

**確認方法**:
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue \
  --attribute-names RedrivePolicy
```

**効果**:
- 失敗メッセージが無限に再試行されない
- メインキューの詰まりを防止
- 問題のあるメッセージを隔離して後で調査可能

**優先度**: ⭐⭐⭐⭐（設定確認 → 必要なら修正）

---

### 対策3: CloudWatch Alarmによる監視強化

#### 3-1. APIヘルスチェック監視

**アラーム条件**:
- Behavior/Emotion APIの `/health` が3回連続失敗
- → SNS通知 → 担当者に即座にアラート

**実装箇所**:
- CloudWatch Synthetics Canary（定期的にヘルスチェック）
- または Lambda関数で5分ごとにヘルスチェック

**効果**:
- APIのunhealthy状態を早期発見
- 自動またはマニュアルでコンテナ再起動

**優先度**: ⭐⭐⭐⭐（監視体制の強化）

#### 3-2. SQS Message Age監視

**アラーム条件**:
- `ApproximateAgeOfOldestMessage` > 600秒（10分）
- → SNS通知

**効果**:
- メッセージが溜まり始めたことを早期発見
- 手動介入の判断材料

**優先度**: ⭐⭐⭐（追加の安全策）

---

### 対策4: SQS可視性タイムアウトの調整

**現状**: 15分（900秒）
**推奨**: Lambda timeout + 余裕（例: 5分 = 300秒）

**理由**:
- Lambda Workerが60秒でタイムアウト
- 可視性タイムアウトが長すぎると、失敗メッセージの再処理が遅れる
- 短くすることで、問題を早期に検出・対処可能

**実装方法**:
```bash
aws sqs set-queue-attributes \
  --queue-url https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue \
  --attributes VisibilityTimeout=300
```

**効果**:
- 失敗メッセージの再試行が早くなる
- DLQへの移動も早くなる

**優先度**: ⭐⭐⭐（Lambda timeout延長と同時実施）

---

### 対策5: APIコンテナの自動再起動メカニズム

**提案**: ヘルスチェック失敗時の自動再起動

**実装方法**:
- Docker Composeの `restart: always` は既に設定済み
- さらに、Dockerヘルスチェックの `--health-retries` を調整
- または、CloudWatch Alarm → Lambda → EC2 SSMでコンテナ再起動

**効果**:
- unhealthy状態の自動復旧
- 人手介入を減らす

**優先度**: ⭐⭐（中期的な改善）

---

## 🔍 根本原因の調査が必要な問題

### `/health` エンドポイントのタイムアウト問題

**現象**:
- コンテナ内部から `/health` → 即座に応答（0.8秒）
- 外部（Nginx/Cloudflare経由）から `/health` → タイムアウト（30秒+）
- 一方で `/async-process` → 外部からも正常（1.6秒）

**考えられる原因**:
1. Nginxの設定問題（特定のエンドポイントへのルーティング）
2. Cloudflareのキャッシュ/CDN設定
3. Dockerネットワークの問題
4. uvicorn/FastAPIの非同期処理の問題

**調査が必要な項目**:
- [ ] Nginxアクセスログの詳細分析
- [ ] Cloudflareの設定確認（Page Rulesなど）
- [ ] uvicornのワーカー数・スレッド設定
- [ ] `/health` と `/async-process` のコードの差異分析

**優先度**: ⭐⭐⭐（根本解決のため調査が必要）

---

## 📊 実装の優先順位

| 対策 | 優先度 | 実装難易度 | 効果 | 実施時期 |
|------|--------|-----------|------|---------|
| 1. Lambda timeout延長 | ⭐⭐⭐⭐⭐ | 低 | 高 | **即時** |
| 2. DLQ設定確認・修正 | ⭐⭐⭐⭐ | 低 | 高 | **即時** |
| 3-1. ヘルスチェック監視 | ⭐⭐⭐⭐ | 中 | 高 | 1週間以内 |
| 4. 可視性タイムアウト調整 | ⭐⭐⭐ | 低 | 中 | 即時〜1週間 |
| 3-2. Message Age監視 | ⭐⭐⭐ | 中 | 中 | 1週間以内 |
| 5. 自動再起動メカニズム | ⭐⭐ | 高 | 高 | 1ヶ月以内 |
| 根本原因調査 | ⭐⭐⭐ | 高 | 不明 | 継続的に |

---

## 📝 実装チェックリスト

### ✅ フェーズ0: 緊急安定化対策（完了: 2025-12-12）

- [x] **Lambda並列実行数の制限**
  - [x] watchme-sed-worker: 2並列
  - [x] watchme-ser-worker: 2並列
  - [x] watchme-asr-worker: 10並列
- [x] **Lambda Worker timeout を 60秒に延長**
  - [x] watchme-asr-worker: 60秒
  - [x] watchme-sed-worker: 60秒
  - [x] watchme-ser-worker: 60秒
- [x] **可視性タイムアウトを300秒に調整**
  - [x] watchme-asr-queue: 300秒
  - [x] watchme-sed-queue: 300秒
  - [x] watchme-ser-queue: 300秒

**効果**:
- CPU枯渇によるAPIのunhealthy状態を防止
- タイムアウト耐性が2倍に向上（30秒 → 60秒）
- 失敗時の復旧が3倍高速化（15分 → 5分）

### フェーズ1: FIFO Queue移行（目標: 2025-12-19）

- [ ] FIFO Queue作成
  - [ ] watchme-asr-queue-v2.fifo
  - [ ] watchme-sed-queue-v2.fifo
  - [ ] watchme-ser-queue-v2.fifo
- [ ] audio-processor Lambda修正
  - [ ] Message Group ID実装
  - [ ] Deduplication ID実装
  - [ ] FIFO Queue送信ロジック
- [ ] Lambda Workerのイベントソースマッピング更新
  - [ ] watchme-asr-worker
  - [ ] watchme-sed-worker
  - [ ] watchme-ser-worker
- [ ] 段階的切り替え・動作確認
- [ ] Standard Queue無効化・削除

**詳細**: [SCALABILITY_ROADMAP.md](./SCALABILITY_ROADMAP.md#phase-1-fifo-queue移行)

### フェーズ2: 監視体制構築（1週間以内）

- [ ] **DLQ監視（最優先）**
  - [ ] watchme-dashboard-analysis-dlq: メッセージ数 > 10件
  - [ ] watchme-dashboard-summary-dlq: メッセージ数 > 10件（存在する場合）
  - [ ] その他すべてのDLQ
- [ ] **Lambda Error Rate監視**
  - [ ] watchme-dashboard-analysis-worker: エラー率 > 10%
  - [ ] watchme-dashboard-summary-worker: エラー率 > 10%
  - [ ] watchme-aggregator-checker: エラー率 > 10%
  - [ ] watchme-audio-processor: エラー率 > 10%
  - [ ] watchme-asr-worker: エラー率 > 10%
  - [ ] watchme-sed-worker: エラー率 > 10%
  - [ ] watchme-ser-worker: エラー率 > 10%
- [ ] CloudWatch Synthetics Canaryでヘルスチェック監視
  - [ ] Behavior API
  - [ ] Emotion API
  - [ ] Vibe Transcriber API
- [ ] CloudWatch Alarm設定
  - [ ] SQS Message Age > 10分
  - [ ] API Unhealthy 3回連続
- [ ] SNS通知先の設定（メール/Slack）
- [ ] DLQ再処理スクリプトの作成

### フェーズ3: 長期改善（1ヶ月以内）

- [ ] 自動再起動メカニズムの実装
- [ ] `/health` タイムアウト問題の根本原因調査
- [ ] 負荷テスト（大量メッセージ処理時の挙動確認）

---

## 📚 関連ドキュメント

- [処理アーキテクチャ](./PROCESSING_ARCHITECTURE.md) - イベント駆動型アーキテクチャの詳細
- [技術仕様](./TECHNICAL_REFERENCE.md) - Lambda関数とSQSの設定
- [運用ガイド](./OPERATIONS_GUIDE.md) - デプロイ・運用手順
- [トラブルシューティング](./EC2_RESTART_TROUBLESHOOTING.md) - 既存のトラブル対応

---

## 📞 緊急時の連絡先

**問題発生時の対応フロー**:
1. CloudWatch Logs でエラー確認
2. SQSキューの状態確認
3. APIコンテナの再起動
4. それでも解決しない場合 → SQSキューパージ（最終手段）

**重要**: SQSパージは**データ損失**を伴うため、本番環境では慎重に判断すること。
