# WatchMe 運用ガイド

最終更新: 2025年9月3日

## 📋 このガイドについて

日常的なサーバー運用、APIデプロイ、トラブルシューティングの実用的な手順書です。

## ⚡ クイックリファレンス

### サーバー接続
```bash
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
```

### 主要サービス管理
```bash
# 全サービス状態確認
sudo systemctl status watchme-*.service | grep -E "●|Active"

# 特定サービス管理
sudo systemctl status watchme-vault-api.service
sudo systemctl restart watchme-vault-api.service
sudo systemctl stop watchme-vault-api.service
```

### Docker管理
```bash
# 全コンテナ状態確認
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# ネットワーク接続確認
docker network inspect watchme-network | grep -A 1 -B 1 "Name"
```

## 🚀 APIデプロイ手順

### パターンA: 新規APIデプロイ（推奨）

#### 1. ローカルでの準備

**必須ファイル:**
- `Dockerfile.prod`（本番用）
- `docker-compose.prod.yml`
- `requirements.txt` または `package.json`
- `.env.example`

**Dockerfile.prodの必須要素:**
```dockerfile
# curlをインストール（ヘルスチェック用）
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
```

**docker-compose.prod.ymlの必須要素:**
```yaml
version: '3.8'

services:
  your-service:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: your-service-name
    ports:
      - "127.0.0.1:8000:8000"  # localhostのみ
    networks:
      - watchme-network  # 必須！
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    restart: always

networks:
  watchme-network:
    external: true  # 重要！
```

#### 2. systemdサービス設定

`watchme-server-configs/systemd/[サービス名].service`:
```ini
[Unit]
Description=[サービス説明] Docker Container
After=docker.service watchme-infrastructure.service
Requires=docker.service watchme-infrastructure.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/[サービスディレクトリ]
TimeoutStartSec=0

ExecStartPre=-/usr/bin/docker-compose -f docker-compose.prod.yml down
ExecStart=/usr/bin/docker-compose -f docker-compose.prod.yml up
ExecStop=/usr/bin/docker-compose -f docker-compose.prod.yml down

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. デプロイ実行

```bash
# 1. 設定をプッシュ
cd /Users/kaya.matsumoto/projects/watchme/watchme-server-configs
git add systemd/[サービス名].service
git commit -m "feat: [サービス名]のsystemd設定追加"
git push origin main

# 2. サーバーで反映
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

# 3. 設定取得
cd /home/ubuntu/watchme-server-configs
git pull origin main

# 4. APIコードをデプロイ
cd /home/ubuntu/[サービスディレクトリ]
git pull origin main  # 新規: git clone [repo]

# 5. 環境変数設定
cp .env.example .env
nano .env

# 6. 設定反映
cd /home/ubuntu/watchme-server-configs
./setup_server.sh

# 7. サービス開始
sudo systemctl enable [サービス名].service
sudo systemctl start [サービス名].service

# 8. 確認
sudo systemctl status [サービス名].service
docker ps | grep [コンテナ名]
curl http://localhost:[ポート]/health
```

### パターンB: 既存サービス更新

```bash
# 1. サーバー接続
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

# 2. コード更新
cd /home/ubuntu/[サービスディレクトリ]
git pull origin main

# 3. サービス再起動
sudo systemctl restart [サービス名].service

# 4. 確認
sudo systemctl status [サービス名].service
```

## 🔧 トラブルシューティング

### コンテナが起動しない

**チェック項目:**
```bash
# 1. 構文確認
docker-compose -f docker-compose.prod.yml config

# 2. ポート競合確認
sudo lsof -i:[ポート番号]

# 3. 環境変数確認
cat .env

# 4. ログ確認
sudo journalctl -u [サービス名].service -n 50
```

### ヘルスチェック失敗（unhealthy状態）

**確認手順:**
```bash
# 1. curlインストール確認
docker exec [コンテナ名] which curl

# 2. 手動ヘルスチェック
docker exec [コンテナ名] curl -f http://localhost:8000/health

# 3. Dockerfileの確認
grep -i curl Dockerfile.prod
```

**解決策:**
- Dockerfile.prodにcurlをインストール
- 正しいDockerfileが使用されているか確認

### ネットワーク接続エラー

**確認手順:**
```bash
# 1. ネットワーク接続確認
docker network inspect watchme-network | grep [コンテナ名]

# 2. 手動接続テスト
docker exec [コンテナA] ping -c 1 [コンテナB]

# 3. 設定確認
grep -A 5 networks docker-compose.prod.yml
```

### サーバー再起動後に起動しない

**確認手順:**
```bash
# 1. サービス有効化確認
sudo systemctl is-enabled [サービス名].service

# 2. 依存関係確認
sudo systemctl list-dependencies [サービス名].service

# 3. 起動ログ確認
sudo journalctl -u [サービス名].service --since "1 hour ago"
```

## 📊 監視・メンテナンス

### 定期確認項目

**毎日:**
```bash
# システムリソース確認
free -h
df -h
docker stats --no-stream

# サービス状態確認
sudo systemctl status watchme-*.service | grep -E "●|Active|failed"
```

**毎週:**
```bash
# ログローテーション
sudo journalctl --vacuum-time=7d

# Docker不要リソース削除
docker system prune -f
```

### 緊急時の対応

**メモリ不足時:**
```bash
# 低優先度サービス停止
sudo systemctl stop watchme-admin.service

# Docker クリーンアップ
docker system prune -a -f

# 必要に応じてswap確認
swapon --show
```

**全サービス停止が必要な場合:**
```bash
# 全WatchMeサービス停止
sudo systemctl stop watchme-*.service

# インフラサービス再起動
sudo systemctl restart watchme-infrastructure.service

# 個別サービス再起動
sudo systemctl start watchme-vault-api.service
# ... 必要なサービスを順次起動
```

## ✅ デプロイ完了チェックリスト

- [ ] コンテナが正常起動: `docker ps | grep [コンテナ名]`
- [ ] ヘルスチェック成功: `docker ps | grep healthy`
- [ ] systemd有効化: `sudo systemctl is-enabled [サービス名]`
- [ ] ログエラー無し: `sudo journalctl -u [サービス名] -n 20`
- [ ] API応答確認: `curl http://localhost:[ポート]/health`
- [ ] 外部アクセス確認: `curl https://api.hey-watch.me/[path]/health`

## 📞 サポート

**開発者**: Kaya Matsumoto
**緊急時**: systemdログとDockerログを確認後、必要に応じてサービス再起動