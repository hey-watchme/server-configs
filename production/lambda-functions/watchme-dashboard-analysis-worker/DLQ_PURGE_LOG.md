# DLQ Purge Log

## 削除日時
2025-12-13 15:30 JST

## 理由
`watchme-dashboard-analysis-worker` Lambda関数のインポートエラー（`requests`モジュール不足）により、
2025-12-10 ~ 2025-12-12の期間にDaily分析が失敗し、DLQに991件のメッセージが蓄積。

## 削除内容
- **DLQキュー**: `watchme-dashboard-analysis-dlq`
- **メッセージ数**: 991件
- **対象期間**: 2025-12-10 ~ 2025-12-12（推定）

## サンプルメッセージ
```json
{
  "device_id": "9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93",
  "local_date": "2025-12-12",
  "recorded_at": "2025-12-11T15:01:01.955+00:00"
}
```

## 修正内容
1. `build.sh`を実行して依存関係（`requests`）を含むデプロイメントパッケージを再作成
2. AWS Lambdaに最新版をデプロイ（2025-12-12 15:28 UTC）
3. Lambda関数がアクティブ状態に復旧

## 影響
過去のDaily分析（2025-12-10 ~ 2025-12-12）は実行されていないが、
今後の新しいSpot分析からは正常にDaily分析が実行される。

## 対応者
Claude Code
