# Docker Compose メモリ制限設定ガイド

## t4g.large (8GB RAM) での推奨メモリ制限

EC2インスタンスをt4g.largeにアップグレード後の推奨メモリ制限設定：

### 各サービスの推奨メモリ制限

```yaml
# 重要度：高（常時稼働必須）
watchme-vault-api: 1024m      # Gateway API
watchme-api-manager: 512m     # 管理UI
watchme-scheduler: 512m       # スケジューラー
watchme-web: 768m             # Webダッシュボード

# 重要度：中（APIサービス）
vibe-transcriber-v2: 1536m    # Whisper API (音声認識処理が重い)
opensmile-api: 1024m          # 音声特徴量抽出
api-gpt-v1: 768m              # GPT連携
mood-chart-api: 512m          # プロンプト生成
sed-api: 768m                 # 音声イベント検出

# 重要度：低（集計・管理系）
opensmile-aggregator: 512m    # 感情スコア集計
api-sed-aggregator: 512m      # 音声イベント集計
watchme-admin: 512m           # 管理画面
watchme-avatar-uploader: 256m # アバターアップロード
```

### docker-compose.ymlへの適用例

```yaml
services:
  vibe-transcriber-v2:
    image: 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber-v2:latest
    container_name: vibe-transcriber-v2
    deploy:
      resources:
        limits:
          memory: 1536m
        reservations:
          memory: 512m
    # ... 他の設定
```

### 注意事項

1. **合計メモリ使用量**: 約9GB（OS含む）を想定
2. **余裕を持たせる**: 実際の使用可能メモリ7.8GBに対して、合計で7GB程度に抑える
3. **動的調整**: 実際の使用状況に応じて調整が必要
4. **t4g.smallに戻す場合**: メモリ制限を1/4程度に減らす必要あり

### モニタリングコマンド

```bash
# メモリ使用状況の確認
docker stats --no-stream

# システム全体のメモリ状況
free -h

# 特定コンテナの詳細
docker inspect [container-name] | grep -A 5 Memory
```

## 今後の対応

1. 各docker-compose.prod.ymlファイルにメモリ制限を追加
2. サーバーでの動作確認後、必要に応じて調整
3. t4g.smallに戻す場合の設定も準備