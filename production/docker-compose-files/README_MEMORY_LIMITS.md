# Docker Compose メモリ制限設定ガイド

## 現在の前提: t4g.small (2GB RAM)

このファイルにある詳細な数値は `t4g.large (8GB)` 運用時の参考値でした。  
**現在の本番は t4g.small (2GB) のため、このまま適用しないでください。**

### t4g.small での暫定方針

- 解析系APIは同時常駐を最小化し、必要なものだけ起動する
- `docker stats --no-stream` と `free -h` を見て 80%超の常態化を避ける
- OpenSMILE/eGeMAPS 等の追加は、先にインスタンス再拡張または分離配置を検討する

### 各サービスの推奨メモリ制限

```yaml
# 重要度：高（常時稼働必須）
watchme-vault-api: 1024m      # Gateway API
watchme-api-manager: 512m     # 管理UI
watchme-scheduler: 512m       # スケジューラー
watchme-web: 768m             # Webダッシュボード

# 重要度：中（APIサービス）
vibe-transcriber-v2: 1536m    # Whisper API (音声認識処理が重い)
paralinguistic-api: 1024m          # 音声特徴量抽出
api-gpt-v1: 768m              # GPT連携
mood-chart-api: 512m          # プロンプト生成
sed-api: 768m                 # 音声イベント検出

# 重要度：低（集計・管理系）
paralinguistic-aggregator: 512m    # 感情スコア集計
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

1. 上記メモリ値は `t4g.large` 想定の旧値
2. `t4g.small` では同値を設定しても実効性が低く、OOM/Swap悪化のリスクが高い
3. 現行では「同時稼働数の制御 + 実測監視」を優先する

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
