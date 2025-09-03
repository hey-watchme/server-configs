# APIデプロイメントガイド

最終更新: 2025年9月3日

## 📋 このガイドについて

このガイドは、WatchMeプラットフォームにAPIをデプロイする際の**標準手順書**です。
今回のwatchme-vault-api修正での教訓を踏まえ、混乱を防ぐための明確なプロセスを記載しています。

## ⚠️ 最重要事項

### デプロイ前に必ず確認すること

1. **現在の実行方式を確認**
   ```bash
   # systemdサービスの状態確認
   sudo systemctl status [サービス名].service
   
   # Dockerコンテナの状態確認
   docker ps | grep [コンテナ名]
   ```

2. **どの設定ファイルが使用されているか確認**
   - systemd直接実行 → `/etc/systemd/system/[サービス名].service`
   - Docker実行 → `docker-compose.yml` または `docker-compose.prod.yml`

3. **ネットワーク設定の確認**
   - 全サービスは `watchme-network` に接続する必要がある
   - `docker-compose.yml` に `external: true` が設定されているか確認

## 🔄 デプロイパターン

### パターンA: Dockerコンテナとしてデプロイ（推奨）

#### 1. ローカルでの準備

**必須ファイル:**
- `Dockerfile` または `Dockerfile.prod`（本番用）
- `docker-compose.yml` と `docker-compose.prod.yml`
- `requirements.txt` または `package.json`
- `.env.example`（環境変数のテンプレート）

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
      dockerfile: Dockerfile.prod  # 本番用Dockerfileを明示
    container_name: your-service-name
    ports:
      - "127.0.0.1:8000:8000"  # localhostのみにバインド
    networks:
      - watchme-network  # 必須！
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always  # 自動再起動

networks:
  watchme-network:
    external: true  # 既存ネットワークを使用（重要！）
```

#### 2. systemdサービスファイルの作成

`watchme-server-configs/systemd/[サービス名].service`:
```ini
[Unit]
Description=[サービスの説明] Docker Container
After=docker.service watchme-infrastructure.service
Requires=docker.service watchme-infrastructure.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/[サービスディレクトリ]
TimeoutStartSec=0

# 既存コンテナを確実に停止
ExecStartPre=-/usr/bin/docker-compose -f docker-compose.prod.yml down

# 本番用設定でコンテナ起動
ExecStart=/usr/bin/docker-compose -f docker-compose.prod.yml up

# 停止時の処理
ExecStop=/usr/bin/docker-compose -f docker-compose.prod.yml down

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. デプロイ手順

```bash
# 1. ローカルで変更をコミット
cd /Users/kaya.matsumoto/projects/watchme/watchme-server-configs
git add systemd/[サービス名].service
git commit -m "feat: [サービス名]のsystemd設定を追加"
git push origin main

# 2. サーバーで反映
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

# 3. 設定を取得
cd /home/ubuntu/watchme-server-configs
git pull origin main

# 4. APIのコードをデプロイ
cd /home/ubuntu/[サービスディレクトリ]
git pull origin main  # または新規の場合はgit clone

# 5. 環境変数設定
cp .env.example .env
nano .env  # 必要な環境変数を設定

# 6. setup_server.shで設定を反映
cd /home/ubuntu/watchme-server-configs
./setup_server.sh

# 7. サービスを有効化・起動
sudo systemctl enable [サービス名].service
sudo systemctl start [サービス名].service

# 8. 状態確認
sudo systemctl status [サービス名].service
docker ps | grep [コンテナ名]
curl http://localhost:[ポート]/health
```

### パターンB: 既存サービスの移行（uvicorn直接実行 → Docker）

#### 移行前の確認事項

1. **現在の設定を完全に理解する**
   ```bash
   # 現在のサービス設定を確認
   cat /etc/systemd/system/[サービス名].service
   
   # 現在のプロセスを確認
   ps aux | grep [サービス名]
   ```

2. **データとログの退避**
   ```bash
   # ログのバックアップ
   sudo cp -r /var/log/[サービス名] /var/log/[サービス名].backup.$(date +%Y%m%d)
   ```

#### 移行手順

```bash
# 1. 旧サービスを停止・無効化
sudo systemctl stop [サービス名].service
sudo systemctl disable [サービス名].service

# 2. Dockerで起動（上記パターンAの手順3から実行）
```

## 🔍 トラブルシューティングチェックリスト

### コンテナが起動しない

- [ ] `docker-compose.yml` の構文は正しいか？
  ```bash
  docker-compose -f docker-compose.prod.yml config
  ```

- [ ] ポートの競合はないか？
  ```bash
  sudo lsof -i:[ポート番号]
  ```

- [ ] 環境変数は設定されているか？
  ```bash
  cat .env
  ```

### ヘルスチェックが失敗する

- [ ] Dockerfileにcurlがインストールされているか？
- [ ] ヘルスチェックのエンドポイントは正しいか？
- [ ] アプリケーションは指定ポートでリッスンしているか？

### ネットワーク接続エラー

- [ ] `watchme-network` に接続されているか？
  ```bash
  docker network inspect watchme-network | grep [コンテナ名]
  ```

- [ ] `docker-compose.yml` に `external: true` が設定されているか？

### systemdサービスが起動しない

- [ ] WorkingDirectoryは存在するか？
- [ ] docker-composeのパスは正しいか？
- [ ] ユーザー権限は適切か？

## 📝 今回の教訓（2025年9月3日）

### watchme-vault-apiの事例から学んだこと

1. **問題**: ヘルスチェックでcurlが見つからずunhealthy状態
   - **原因**: 開発用Dockerfileが本番で使用されていた
   - **解決**: docker-compose.prod.ymlの使用に切り替え
   - **教訓**: 本番では必ず`.prod`ファイルを使用する

2. **問題**: サーバー再起動時に自動起動しない
   - **原因**: 手動でdocker-composeを実行していた
   - **解決**: systemdサービスとして管理
   - **教訓**: 全サービスはsystemdで管理する

3. **問題**: 設定の不一致
   - **原因**: ローカルとサーバーで異なる設定
   - **解決**: watchme-server-configsで一元管理
   - **教訓**: 設定変更は必ずGit経由で行う

## ✅ デプロイ完了チェックリスト

- [ ] コンテナが正常に起動している
  ```bash
  docker ps | grep [コンテナ名]
  ```

- [ ] ヘルスチェックがhealthyを返す
  ```bash
  docker ps | grep [コンテナ名] | grep healthy
  ```

- [ ] systemdサービスがenabledかつactive
  ```bash
  sudo systemctl status [サービス名].service | grep -E "Loaded|Active"
  ```

- [ ] ログにエラーがない
  ```bash
  docker logs [コンテナ名] --tail 50
  sudo journalctl -u [サービス名].service -n 50
  ```

- [ ] APIエンドポイントが応答する
  ```bash
  curl http://localhost:[ポート]/health
  ```

- [ ] Nginxから外部アクセス可能
  ```bash
  curl https://api.hey-watch.me/[エンドポイント]/health
  ```

## 🚀 ベストプラクティス

1. **開発と本番の分離**
   - 開発: `Dockerfile` + `docker-compose.yml`
   - 本番: `Dockerfile.prod` + `docker-compose.prod.yml`

2. **ヘルスチェックの実装**
   - 全APIに `/health` エンドポイントを実装
   - Dockerfileにcurlをインストール
   - docker-composeでhealthcheckを設定

3. **ネットワークの統一**
   - 全サービスを `watchme-network` に接続
   - `external: true` を必ず設定

4. **systemd管理の徹底**
   - 手動起動は避ける
   - 全サービスをsystemdで管理
   - 自動起動を有効化

5. **ドキュメントの更新**
   - デプロイ後は必ず `server_overview.md` を更新
   - 変更履歴を `README.md` に記録

## 📚 関連ドキュメント

- [README.md](./README.md) - 全体概要とインフラ構成
- [NETWORK-ARCHITECTURE.md](./NETWORK-ARCHITECTURE.md) - ネットワーク設計
- [server_overview.md](./server_overview.md) - サービス一覧とエンドポイント

## 🔄 更新履歴

| 日付 | 内容 | 作成者 |
|------|------|--------|
| 2025-09-03 | 初版作成（watchme-vault-api修正の教訓を反映） | System |