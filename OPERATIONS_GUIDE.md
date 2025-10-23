# WatchMe 運用ガイド

最終更新: 2025年9月6日

## 🎯 このガイドの目的

このガイドは、WatchMeプラットフォームにおける、**2つの異なるデプロイ作業**の手順を明確に分離して定義します。
作業の目的に応じて、必ず対応する手順を参照してください。

---

## 1. アプリケーションのデプロイ手順

### 👉 この手順を使う時

-   **各APIのソースコード（Python, JSなど）を修正した**
-   **`.env`ファイル（環境変数）の内容を更新した**

上記のように、サービスの「中身」だけが変更され、`docker-compose.yml`や`systemd`の`.service`ファイルに**変更がない**場合に、この手順を実行します。

### ワークフロー

> **📘 CI/CD詳細**: GitHub ActionsによるCI/CDプロセスの詳細は[CI/CD標準仕様書](./CICD_STANDARD_SPECIFICATION.md)を参照

1.  **CI/CDの完了確認:**
    対象APIのGitリポジトリで、CI/CD（GitHub Actions）が完了し、新しいバージョンタグが付いたDockerイメージがECRにプッシュされたことを確認します。

2.  **本番サーバーへ接続:**
    ```bash
    ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
    ```

3.  **サービスの再起動:**
    以下のコマンドで、対象のサービスを再起動します。`systemd`が、ECRから新しいイメージを自動で`pull`して、コンテナを安全に入れ替えてくれます。

    ```bash
    # 例: avatar-uploaderを再起動する場合
    sudo systemctl restart watchme-avatar-uploader.service
    ```

4.  **動作確認:**
    `systemctl status`コマンドで、サービスが`active (running)`になっていることを確認します。

    ```bash
    sudo systemctl status watchme-avatar-uploader.service
    ```

---

## 2. サーバー構成の変更手順

### 👉 この手順を使う時

-   **`docker-compose.yml`ファイルを修正した**（ポート番号、ボリューム、イメージ名など）
-   **`systemd`の`.service`ファイルを修正した**（依存関係、実行コマンドなど）
-   **Nginxの設定ファイル（`sites-available/`）を修正した**
-   **新しいサービスをシステムに追加した**

上記のように、インフラやサービスの「設計図」に関わる変更を行った場合に、この手順を実行します。

### ワークフロー

1.  **Gitリポジトリでの変更:**
    この`watchme-server-configs`リポジトリで設定ファイルを修正し、変更を`main`ブランチに`push`します。

2.  **本番サーバーへ接続:**
    ```bash
    ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
    ```

3.  **設定の反映:**
    サーバー上でリポジトリの最新の状態を取得し、セットアップスクリプトを実行して、変更をシステム全体に反映させます。

    ```bash
    cd /home/ubuntu/watchme-server-configs
    git pull origin main
    ./setup_server.sh
    ```

4.  **（もし新しいサービスを追加した場合のみ）サービスの有効化:**
    `setup_server.sh`は設定をリンクするだけです。新しいサービスをOS起動時に自動起動させるには、以下のコマンドで「有効化」する必要があります。

    ```bash
    sudo systemctl enable --now <new-service-name>.service
    ```

5.  **動作確認:**
    関連するサービスの`systemctl status`を確認します。

---

## 3. トラブルシューティング

### 🌐 ネットワーク関連の問題

#### 症状: APIコンテナ間の通信エラー
```
ERROR: API接続エラー - コンテナ名 'xxx' が解決できません
```

**解決方法：**
```bash
# 1. ネットワーク接続状態を確認
bash /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh

# 2. 自動修復を実行
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix

# 3. 手動で接続（必要な場合）
docker network connect watchme-network [container-name]
```

#### 症状: Vibe Aggregatorが動作しない

**確認手順：**
```bash
# cronログ確認
sudo tail -100 /var/log/scheduler/cron.log | grep vibe-aggregator

# コンテナログ確認
docker logs api_gen_prompt_mood_chart --tail 50

# 手動実行テスト
docker exec watchme-scheduler-prod python /app/run-api-process-docker.py vibe-aggregator --date 2025-08-28
```

### 💾 メモリ・ディスク関連の問題

#### 症状: Dockerイメージプル/コンテナ起動時の "no space left on device"
```
failed to register layer: write /usr/lib/aarch64-linux-gnu/libLLVM.so.19.1: no space left on device
```

**根本原因**: ディスク容量不足（95%以上使用）

**解決手順**:
```bash
# 1. 現在のディスク使用状況確認
df -h

# 2. Dockerリソース大量クリーンアップ
sudo docker container prune -f    # 停止コンテナ削除
sudo docker image prune -a -f     # 未使用イメージ削除
sudo docker volume prune -f       # 未使用ボリューム削除
sudo docker system prune -a -f    # 包括的クリーンアップ

# 3. 効果確認
df -h  # 10GB以上削減されることを確認
```

#### 症状: コンテナが起動するがすぐに停止する（メモリ不足）
```bash
# コンテナが見つからない、またはステータスがExited (137)
```

**根本原因**: メモリ使用量が制限を超過（OOM Killer作動）

**解決手順**:
```bash
# 1. メモリ使用状況確認
docker stats --no-stream
free -h

# 2. 重要度の低いコンテナを一時停止
docker stop opensmile-aggregator api-sed-aggregator

# 3. メモリ制限付きで起動（例）
docker run -d --name [container-name] \
  --network watchme-network \
  -p [port]:[port] \
  --memory="1g" --cpus="1.0" \
  --env-file /path/to/.env \
  --restart unless-stopped \
  [IMAGE_URI]
```

### 🔐 認証関連の問題

#### 症状: ECR認証エラー "authorization token has expired"
```
pull access denied ... may require 'docker login': denied: Your authorization token has expired
```

**解決手順**:
```bash
# ECRに再ログイン
aws ecr get-login-password --region ap-southeast-2 | \
  sudo docker login --username AWS --password-stdin \
  754724220380.dkr.ecr.ap-southeast-2.amazonaws.com
```

### 🔧 Nginx関連の問題

#### 症状: 502 Bad Gateway エラー
外部からAPIアクセス時に502エラーが発生する場合の診断手順：

1. **コンテナの生存確認**
   ```bash
   # コンテナが実際に動作しているか確認
   docker ps | grep [コンテナ名]

   # 内部からの直接アクセステスト
   curl http://localhost:[ポート]/
   ```

2. **Nginx設定の確認（最重要）**
   ```bash
   # 現在の設定を確認
   grep -A 5 "location /[API名]/" /etc/nginx/sites-available/api.hey-watch.me

   # ⚠️ よくある間違い：
   # 例： proxy_pass http://localhost:[port]/;  # Nginxがホスト上にある場合
   # 例： proxy_pass http://[container-name]:[port]/;  # Nginxがコンテナの場合
   ```

   **重要**: Nginxがホスト上で直接動作している場合は`localhost`が正しい

3. **ポートマッピングの確認**
   ```bash
   # ポートが正しくマッピングされているか確認
   sudo lsof -i:[ポート番号]
   docker port [コンテナ名]
   ```

4. **Nginxログ確認**
   ```bash
   sudo tail -n 50 /var/log/nginx/error.log
   sudo tail -n 50 /var/log/nginx/access.log | grep "[API名]"
   ```

#### 症状: 404エラー

404エラーが発生した場合、以下の手順で問題を切り分けてください。

1. **APIは生きているか？ (サーバー内部から確認)**
   - サービスがダウンしているのが原因かもしれません。まず、サーバー内部から直接APIを叩いてみます。
   ```bash
   # 1. ポート番号を確認
   sudo lsof -i:[ポート番号]

   # 2. 内部から直接curlで叩く
   curl http://localhost:[ポート番号]/[内部APIパス]/[任意のエンドポイント]
   ```
   - ここで応答がなければ、問題はNginxではなく、APIアプリケーション自体にあります。サービスのログを確認してください。

2. **Nginxのログは何か言っているか？**
   - APIが生きているのにエラーが出る場合、Nginxのログにヒントがあるはずです。
   ```bash
   # エラーログの最新50行を確認
   sudo tail -n 50 /var/log/nginx/error.log

   # アクセスログで、該当のリクエストがどのように記録されているか確認
   sudo tail -n 50 /var/log/nginx/access.log | grep "[公開URLパス]"
   ```

3. **設定は正しくリロードされているか？**
   - 設定ファイルを変更した後は、`sudo nginx -t` でテストし、`sudo systemctl reload nginx` を実行したか再確認してください。単純なリロード忘れもよくある原因です。

### 🛠️ よくある質問（トラブルシューティング）

#### Q: 新しいAPIがネットワークに繋がらない！

**A: docker-compose.ymlの設定を確認してください：**
```yaml
networks:
  watchme-network:
    external: true  # これが必須！
```

エラーが続く場合：
```bash
# 監視スクリプトで自動修復
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix
```

#### Q: 設定を間違えてサービスが落ちた！

**A: バックアップから復元：**
```bash
# バックアップファイルを探す
ls -la /etc/nginx/sites-available/*.backup.*

# 最新のバックアップから復元
sudo cp /etc/nginx/sites-available/api.hey-watch.me.backup.[最新のタイムスタンプ] \
        /etc/nginx/sites-available/api.hey-watch.me

# テストとリロード
sudo nginx -t && sudo systemctl reload nginx
```

#### Q: スケジューラーが動かなくなった！

**A: よくある原因と解決方法：**

**原因1: docker-compose.prod.ymlを使ってしまった**
```bash
# 診断: スケジューラーコンテナが存在しない
docker ps | grep scheduler
# 何も表示されない場合

# 解決方法:
cd /home/ubuntu/watchme-api-manager
docker-compose -f docker-compose.all.yml up -d
```

**原因2: ネットワーク設定の誤り**
```bash
# docker-compose.all.ymlの最後を確認
tail -5 docker-compose.all.yml
# external: trueであることを確認（driver: bridgeはNG）
```

### 🧹 Janitor API トラブルシューティング

#### 削除処理が実行されない場合
```bash
# 1. EventBridgeルールの状態確認
aws events describe-rule --name watchme-janitor-schedule --region ap-southeast-2

# 2. Lambda関数の実行ログ確認
aws logs filter-log-events \
  --log-group-name /aws/lambda/watchme-janitor-trigger \
  --region ap-southeast-2 \
  --start-time $(($(date +%s) * 1000 - 86400000)) \
  --filter-pattern "削除"

# 3. APIのヘルスチェック
curl https://api.hey-watch.me/janitor/health

# 4. 手動でLambda実行
aws lambda invoke \
  --function-name watchme-janitor-trigger \
  --region ap-southeast-2 \
  response.json && cat response.json | jq
```

### 🛠️ メンテナンス用コマンド集

#### サービス状態確認
```bash
# 全コンテナの状態確認
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"

# メモリ使用状況
docker stats --no-stream

# ネットワーク接続確認
docker network inspect watchme-network | jq '.[0].Containers | keys'
```

#### AST APIの管理
```bash
# 再起動
cd /home/ubuntu/api_ast && docker-compose restart

# ログ確認
docker logs ast-api --tail 50 -f

# ヘルスチェック
curl http://localhost:8017/health
```

#### SUPERB APIの管理
```bash
# 再起動
cd /home/ubuntu/api_superb_v1 && docker-compose restart

# ログ確認
docker logs superb-api --tail 50 -f

# ヘルスチェック
curl http://localhost:8018/health
```

#### トラブル時の緊急対応
```bash
# メモリ逼迫時（優先度の低いサービスを停止）
docker stop api-sed-aggregator opensmile-aggregator

# ディスク容量不足時
docker system prune -a -f
docker image prune -a -f

# ネットワーク問題時
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix
```

---

## 4. 🚨 EC2インスタンス再起動後の復旧手順

EC2インスタンスの再起動後にシステムがダウンしている場合の対処手順です。

### Step 1: SSH接続して状態確認

```bash
# EC2にSSH接続
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

# システム全体の状態確認
free -h                    # メモリ状況
df -h                      # ディスク使用状況
docker --version           # Docker状態
docker ps -a               # 全コンテナ状態

# systemdサービスの状態確認
sudo systemctl status watchme-*.service | grep -E "●|Active|failed"
sudo systemctl status api-*.service | grep -E "●|Active|failed"
sudo systemctl status mood-*.service opensmile-*.service vibe-*.service | grep -E "●|Active|failed"
```

### Step 2: インフラストラクチャの起動

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

### Step 3: セットアップスクリプトの実行

```bash
# 設定ファイルのリポジトリに移動
cd /home/ubuntu/watchme-server-configs

# 最新の設定を取得
git pull origin main

# セットアップスクリプトを実行（サービスの有効化と起動）
./setup_server.sh
```

### Step 4: サービスの手動起動（セットアップスクリプトが失敗した場合）

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

### Step 5: ネットワーク接続の確認と修復

```bash
# ネットワーク状態の確認
bash /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh

# 問題がある場合、自動修復
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix

# 特定のコンテナをネットワークに接続
docker network connect watchme-network [container-name]
```

### Step 6: 各サービスの健全性確認

```bash
# 全コンテナの状態確認
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# ヘルスチェック失敗のコンテナを確認
docker ps --filter health=unhealthy

# 特定のサービスのログ確認
docker logs --tail 50 [container-name]
sudo journalctl -u [service-name].service --since "10 minutes ago"
```

### Step 7: Nginxの確認

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

### 🔧 再起動前のチェックリスト

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

### 🤖 自動化の推奨設定

#### Cronジョブで監視を自動化

```bash
# crontabに追加
crontab -e

# 5分ごとにネットワークチェックと自動修復
*/5 * * * * /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh > /dev/null 2>&1

# 再起動後にサービスを確実に起動（@reboot）
@reboot sleep 60 && /home/ubuntu/watchme-server-configs/setup_server.sh > /var/log/watchme-startup.log 2>&1
```

### 📊 EC2インスタンス情報

- **現在のインスタンスタイプ**: t4g.large (8GB RAM)
- **アップグレード日**: 2025-09-19
- **以前**: t4g.small (2GB RAM)
- **注意**: 一時的なアップグレード、将来的にt4g.smallに戻す可能性あり
