# EC2インスタンス再起動後のトラブルシューティングガイド

最終更新: 2025-09-19

## 🚨 インスタンス再起動後にシステムがダウンしている場合

### 1. SSH接続して状態確認

```bash
# EC2にSSH接続
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
```

### 2. システム全体の状態確認

```bash
# メモリ状況の確認
free -h

# ディスク使用状況
df -h

# Docker状態確認
docker --version
docker ps -a

# systemdサービスの状態確認
sudo systemctl status watchme-*.service | grep -E "●|Active|failed"
sudo systemctl status api-*.service | grep -E "●|Active|failed"
sudo systemctl status mood-*.service opensmile-*.service vibe-*.service | grep -E "●|Active|failed"
```

### 3. 自動復旧手順

#### Step 1: インフラストラクチャの起動

```bash
# watchme-networkの確認と作成
docker network ls | grep watchme-network
# もし存在しない場合
cd /home/ubuntu/watchme-server-configs
sudo docker-compose -f docker-compose.infra.yml up -d

# インフラサービスの起動
sudo systemctl start watchme-infrastructure.service
sudo systemctl status watchme-infrastructure.service
```

#### Step 2: セットアップスクリプトの実行

```bash
# 設定ファイルのリポジトリに移動
cd /home/ubuntu/watchme-server-configs

# 最新の設定を取得
git pull origin main

# セットアップスクリプトを実行（サービスの有効化と起動）
./setup_server.sh
```

#### Step 3: サービスの手動起動（セットアップスクリプトが失敗した場合）

```bash
# 重要サービスから順番に起動
sudo systemctl start watchme-vault-api.service
sleep 5
sudo systemctl start watchme-api-manager.service
sleep 5
sudo systemctl start watchme-web-app.service
sleep 5

# その他のAPIサービスを起動
for service in api-gpt-v1 mood-chart-api vibe-transcriber-v2 opensmile-api opensmile-aggregator api-sed-aggregator; do
    sudo systemctl start ${service}.service
    sleep 2
done

# 管理サービスを起動
sudo systemctl start watchme-admin.service
sudo systemctl start watchme-avatar-uploader.service
```

### 4. ネットワーク接続の確認と修復

```bash
# ネットワーク状態の確認
bash /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh

# 問題がある場合、自動修復
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix

# 特定のコンテナをネットワークに接続
docker network connect watchme-network [container-name]
```

### 5. 各サービスの健全性確認

```bash
# 全コンテナの状態確認
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# ヘルスチェック失敗のコンテナを確認
docker ps --filter health=unhealthy

# 特定のサービスのログ確認
docker logs --tail 50 [container-name]
sudo journalctl -u [service-name].service --since "10 minutes ago"
```

### 6. Nginxの確認

```bash
# Nginx状態確認
sudo systemctl status nginx

# 設定テスト
sudo nginx -t

# Nginxを再起動
sudo systemctl restart nginx

# アクセス確認
curl -I https://api.hey-watch.me/health
curl -I https://dashboard.hey-watch.me/
curl -I https://admin.hey-watch.me/
```

## 🔍 問題別の対処法

### メモリ不足の場合（t4g.largeでは発生しにくい）

```bash
# メモリ使用状況確認
docker stats --no-stream

# 不要なコンテナを停止
docker stop [low-priority-container]

# Dockerリソースクリーンアップ
docker system prune -f
docker image prune -a -f
```

### ECR認証エラーの場合

```bash
# ECRに再ログイン
aws ecr get-login-password --region ap-southeast-2 | \
  sudo docker login --username AWS --password-stdin \
  754724220380.dkr.ecr.ap-southeast-2.amazonaws.com

# イメージを再プル
docker-compose -f [docker-compose-file] pull
```

### systemdサービスが起動しない場合

```bash
# サービスの詳細エラーを確認
sudo journalctl -xe -u [service-name].service

# サービスファイルを再読み込み
sudo systemctl daemon-reload

# サービスを有効化して起動
sudo systemctl enable [service-name].service
sudo systemctl start [service-name].service
```

## 📝 再起動前のチェックリスト

再起動前に以下を確認しておくと、問題を防げます：

1. **全サービスが自動起動設定されているか**
   ```bash
   systemctl list-unit-files | grep -E "watchme|api-|mood|opensmile|vibe" | grep enabled
   ```

2. **docker-compose.infra.ymlが存在するか**
   ```bash
   ls -la /home/ubuntu/watchme-server-configs/docker-compose.infra.yml
   ```

3. **セットアップスクリプトが最新か**
   ```bash
   cd /home/ubuntu/watchme-server-configs && git status
   ```

## 🚀 自動化の推奨設定

### Cronジョブで監視を自動化

```bash
# crontabに追加
crontab -e

# 5分ごとにネットワークチェックと自動修復
*/5 * * * * /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh > /dev/null 2>&1

# 再起動後にサービスを確実に起動（@reboot）
@reboot sleep 60 && /home/ubuntu/watchme-server-configs/setup_server.sh > /var/log/watchme-startup.log 2>&1
```

## 📞 緊急時の連絡先

- リポジトリ: https://github.com/matsumotokaya/watchme-server-configs
- ドキュメント: README.md, TECHNICAL_REFERENCE.md, OPERATIONS_GUIDE.md

## メモ：t4g.largeへのアップグレード情報

- **変更日**: 2025-09-19
- **変更内容**: t4g.small (2GB RAM) → t4g.large (8GB RAM)
- **コスト**: $0.0212/時 → $0.0848/時
- **注意**: 一時的なアップグレード、将来的にt4g.smallに戻す可能性あり