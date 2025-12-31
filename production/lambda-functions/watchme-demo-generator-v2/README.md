# watchme-demo-generator-v2

デモアカウント用のSpot & Daily分析データ生成Lambda関数（V2.1）

## 概要

- **目的**: デモアカウントのリアルなSpot & Dailyデータを1時間ごとに生成
- **データ形式**: Profiler APIの出力フォーマットに準拠
- **実行頻度**: 1時間ごとに自動実行（EventBridge Scheduler）
- **対象テーブル**: `spot_results`, `daily_results`

## アーキテクチャ

```
EventBridge Scheduler (1時間ごと)
    ↓
Lambda: watchme-demo-generator-v2
    ↓ (HTTP POST - UPSERT)
Supabase: spot_results テーブル（新規レコード）
Supabase: daily_results テーブル（累積更新）
```

## 生成データ

### デバイス情報
- **Device ID**: `a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d`
- **ペルソナ**: 5歳男児（幼稚園年長）

### 24時間パターン
- 00:00-06:00: 睡眠（vibe_score: -5〜5）
- 07:00-08:00: 起床・朝食（vibe_score: 20〜35）
- 09:00-15:00: 幼稚園活動（vibe_score: 30〜55）
- 16:00-17:00: マインクラフト（vibe_score: 60〜65）★ピーク
- 18:00-22:00: 家族時間・就寝（vibe_score: 45→5）

### データ形式（Profiler API準拠）

#### Spot分析（spot_results）
毎時1レコードを新規作成

```json
{
  "device_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "recorded_at": "2025-12-31T01:00:00+00:00",
  "vibe_score": 40,
  "summary": "午前の活動。お絵かきと工作に夢中になっている。",
  "behavior": "お絵かき, 工作",
  "emotion": "集中, 喜び",
  "local_date": "2025-12-31",
  "local_time": "2025-12-31T10:00:00+09:00",
  "profile_result": {...},
  "llm_model": "demo-generator-v2"
}
```

#### Daily分析（daily_results）
同一日付のレコードを1時間ごとに上書き（UPSERT）

```json
{
  "device_id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
  "local_date": "2025-12-31",
  "vibe_score": 26.5,
  "summary": "午後17時。マインクラフトで大きなお城を建築中...",
  "vibe_scores": [
    {"time": "2025-12-31T00:00", "score": -5},
    {"time": "2025-12-31T01:00", "score": -3},
    ...
    {"time": "2025-12-31T17:00", "score": 69}
  ],
  "burst_events": [
    {"time": "07:00", "event": "元気に目が覚めて、1日が始まった", "score_change": 20},
    {"time": "08:00", "event": "パンケーキを食べて嬉しそう", "score_change": 15},
    ...
  ],
  "processed_count": 18,
  "llm_model": "demo-generator-v2"
}
```

## ファイル構成

```
watchme-demo-generator-v2/
├── lambda_function.py    # メインのLambda関数
├── requirements.txt      # 依存関係（requests==2.31.0のみ）
├── build.sh             # ビルドスクリプト
├── function.zip         # デプロイパッケージ
├── build/               # ビルド時の一時ファイル
└── README.md            # このファイル
```

## ビルド・デプロイ

### 1. ビルド

```bash
cd /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/watchme-demo-generator-v2
./build.sh
```

### 2. デプロイ

```bash
aws lambda update-function-code \
  --function-name watchme-demo-generator-v2 \
  --zip-file fileb://function.zip \
  --region ap-southeast-2
```

### 3. 環境変数の設定

```bash
aws lambda update-function-configuration \
  --function-name watchme-demo-generator-v2 \
  --environment "Variables={SUPABASE_URL=https://qvtlwotzuzbavrzqhyvt.supabase.co,SUPABASE_KEY=your_key}" \
  --region ap-southeast-2
```

## テスト

### 手動実行

```bash
aws lambda invoke \
  --function-name watchme-demo-generator-v2 \
  --region ap-southeast-2 \
  response.json

cat response.json | python3 -m json.tool
```

### ログ確認

```bash
aws logs tail /aws/lambda/watchme-demo-generator-v2 --follow --region ap-southeast-2
```

## EventBridge Scheduler設定

### スケジュール作成（1時間ごと）

AWS Console → EventBridge → Schedules で設定：

- **名前**: `watchme-demo-generator-v2-hourly`
- **スケジュール**: `cron(0 * * * ? *)` (毎時00分)
- **タイムゾーン**: `Asia/Tokyo`
- **ターゲット**: Lambda `watchme-demo-generator-v2`

## V1（旧システム）との違い

| 項目 | V1（旧） | V2（新） |
|------|---------|---------|
| **アーキテクチャ** | Lambda → EC2 API → DB | Lambda → DB（直接） |
| **実行頻度** | 30分ごと | 1時間ごと |
| **データポイント** | 48個/日 | 24個/日 |
| **依存関係** | requests（EC2呼び出し） | requests（Supabase直接） |
| **保守性** | EC2管理が必要 | Lambda関数のみ |

## トラブルシューティング

### Lambda実行エラー

```bash
# CloudWatchログで確認
aws logs tail /aws/lambda/watchme-demo-generator-v2 --region ap-southeast-2
```

### データが保存されない

1. 環境変数を確認
```bash
aws lambda get-function-configuration \
  --function-name watchme-demo-generator-v2 \
  --region ap-southeast-2 \
  --query 'Environment'
```

2. Supabase接続を確認
   - SUPABASE_URLが正しいか
   - SUPABASE_KEYが有効か

### スケジュールが動かない

- EventBridge Schedulerが有効か確認
- Lambda実行権限が付与されているか確認

## 実装済み機能

- ✅ Spot分析データの24時間パターン生成
- ✅ Daily分析データの累積生成（UPSERT）
- ✅ burst_eventsの時刻ごと累積
- ✅ vibe_scoresの時系列配列（ISO 8601形式）
- ✅ Supabase UPSERT対応（`Prefer: resolution=merge-duplicates`）

## 今後の拡張予定

### Phase 3（今後）
- [ ] 複数パターン（5種類）に拡張
- [ ] 曜日考慮（平日/週末）
- [ ] ランダム性の向上

### Phase 4（将来）
- [ ] 複数ペルソナ対応
- [ ] Weekly分析データの生成
- [ ] 季節変動の実装

## 関連ドキュメント

- [全体アーキテクチャ](../../docs/README.md)
- [Lambda関数デプロイガイド](../DEPLOYMENT_GUIDE.md)
- [旧システム削除手順](../../api/demo-generator/README.md#-旧システムv1の削除手順)

## 更新履歴

- **2025-12-31 (V2.1)**: Daily分析対応
  - Daily分析データの生成機能を追加
  - burst_eventsのフィールド名修正（`vibe_change` → `score_change`）
  - vibe_scoresの時刻フォーマット修正（ISO 8601形式）
  - Supabase UPSERT対応（`resolution=merge-duplicates`）

- **2025-12-31 (V2.0)**: 初回リリース
  - Spot分析専用に簡素化
  - requestsのみで実装（Supabase SDK不使用）
  - 24時間パターンのリアルなデータ作成