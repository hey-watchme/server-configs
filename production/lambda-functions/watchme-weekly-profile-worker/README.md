# Weekly Profile Worker Lambda

週次プロファイル分析を自動実行するLambda関数

## 概要

- **トリガー**: EventBridge (毎日00:00 JST)
- **処理内容**: 前日を含む週（月曜〜日曜）のデータを分析
- **実行時間**: 約35-65秒/デバイス

## 処理フロー

```
EventBridge (毎日15:00 UTC = 00:00 JST)
  ↓
Lambda: weekly-profile-worker
  ↓
週開始日計算（前日を含む週の月曜日）
  ↓
Aggregator API (/aggregator/weekly)
  → weekly_aggregators テーブル (UPSERT)
  ↓
Profiler API (/profiler/weekly-profiler)
  → weekly_results テーブル (UPSERT)
```

## デプロイ手順

### 1. Lambda関数をデプロイ

```bash
cd /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-weekly-profile-worker
./deploy.sh
```

### 2. EventBridge Ruleを作成

```bash
./create-eventbridge-rule.sh
```

## 環境変数

| 変数名 | デフォルト値 | 説明 |
|--------|------------|------|
| `API_BASE_URL` | `https://api.hey-watch.me` | API Base URL |
| `DEVICE_IDS` | `9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93` | 処理対象デバイスID（カンマ区切り） |

## 手動テスト

```bash
# Lambda関数を手動実行
aws lambda invoke --function-name watchme-weekly-profile-worker out.json --region ap-southeast-2

# 結果確認
cat out.json | jq
```

## EventBridge設定

- **Rule名**: `watchme-weekly-profile-daily-trigger`
- **Cron式**: `cron(0 15 * * ? *)`
- **スケジュール**: 毎日15:00 UTC (00:00 JST)
- **ターゲット**: `watchme-weekly-profile-worker` Lambda関数

## CloudWatch Logs

```bash
# ログ確認
aws logs tail /aws/lambda/watchme-weekly-profile-worker --follow --region ap-southeast-2
```

## 処理タイミング

### 例: 2025-11-20 00:00 (JST) に実行

```
実行日時: 2025-11-20 00:00 JST (2025-11-19 15:00 UTC)
  ↓
yesterday = 2025-11-19 (火曜日)
  ↓
week_start_date = 2025-11-18 (月曜日)
  ↓
week_end_date = 2025-11-24 (日曜日)
  ↓
対象データ: 2025-11-18 〜 2025-11-24
（現時点では月・火のデータのみ存在）
```

### 毎日更新の利点

- 週の途中でも常に最新の週次データが閲覧可能
- 日曜日の深夜（月曜00:00）に週が完成
- UPSERTのため、同じ週のデータは上書き更新

## トラブルシューティング

### Lambda実行エラー

```bash
# CloudWatch Logsで詳細確認
aws logs tail /aws/lambda/watchme-weekly-profile-worker --since 1h --region ap-southeast-2
```

### EventBridge設定確認

```bash
# Rule一覧
aws events list-rules --region ap-southeast-2 | grep weekly-profile

# ターゲット確認
aws events list-targets-by-rule --rule watchme-weekly-profile-daily-trigger --region ap-southeast-2
```

### 手動で特定の週を再実行

Lambda関数を直接編集して、`yesterday`の日付を変更してから手動実行。

## 関連ドキュメント

- [PROCESSING_ARCHITECTURE.md](../../docs/PROCESSING_ARCHITECTURE.md) - 処理フロー詳細
- [README.md](../../docs/README.md) - システム全体概要

## 変更履歴

### 2025-11-20

- 初回リリース
- EventBridge自動トリガー対応
- 複数デバイス対応（環境変数DEVICE_IDS）
