# WatchMe API CI/CD 標準仕様書

**目的**: 全WatchMe APIで統一されたCI/CDプロセスを定義し、再現性・自動化・整合性を保証する

---

## このドキュメントの使い方

### 📖 読者別ガイド

| 状況 | 読むべきセクション |
|-----|------------------|
| **新しいAPIのCI/CD実装** | [実装ガイド](#実装ガイド新規api向け) を順番に読む |
| **大きなAIモデルを使用する** | 🚨 [重要：大きなAIモデルを使用する場合の必須対応](#-重要大きなaiモデルを使用する場合の必須対応) を必読 |
| **エラーが発生した** | [トラブルシューティング](#トラブルシューティング) で症状を検索 |
| **設定の詳細を知りたい** | [ファイル仕様リファレンス](#ファイル仕様リファレンス) を参照 |
| **なぜ失敗し続けるのか理解したい** | [基本原則と重要概念](#基本原則と重要概念) を読む |

---

## 基本原則と重要概念

### CI/CDの価値

- **再現性**: 誰がやっても同じように、自動で、ミスなくデプロイが完了
- **自動化**: 手動作業は初回セットアップの1回のみ
- **追跡可能性**: すべての変更がGitで管理され、履歴が残る
- **整合性**: すべてのコンポーネントが協調して動作

### デプロイフロー全体像

```
1. 開発者がコードをpush
   ↓
2. GitHub Actionsが起動
   ↓
3. Dockerイメージをビルド＆ECRへpush
   ↓
4. EC2サーバーへ設定ファイルと環境変数を配置
   ↓
5. 既存コンテナを完全削除
   ↓
6. 新規コンテナを起動
   ↓
7. ヘルスチェックで動作確認
```

### 成功の鍵（3つの必須要件）

1. **ECR名の一貫性**: 全設定ファイルで同じECRリポジトリ名を使用
2. **削除の完全性**: 既存コンテナを確実に削除してから新規起動
3. **環境変数の正確性**: アプリが必要とする全環境変数を.envに書き込む

### 避けるべきアンチパターン

- ❌ デプロイのたびにSSHでサーバーに入って手動作業
- ❌ デプロイスクリプトをサーバー上で直接編集
- ❌ 環境変数を手動で設定・更新
- ❌ 「動いているものには触らない」という考え方
- ❌ 個別最適化による全体の不整合

### 正しいプロセス

1. **初回セットアップ**: EC2上でディレクトリ作成（1回のみ）
2. **コード管理**: すべての設定ファイルをGitで管理
3. **自動デプロイ**: `git push` だけですべてが更新される
4. **全体整合性**: すべてのコンポーネントが一貫したルールで動作

---

## 実装ガイド（新規API向け）

### 必要なGitHub Secrets

以下がリポジトリに設定されていることを確認（Settings > Secrets and variables > Actions）：

```
AWS_ACCESS_KEY_ID       # AWS認証
AWS_SECRET_ACCESS_KEY   # AWS認証
EC2_HOST                # デプロイ先EC2のIPアドレス
EC2_SSH_PRIVATE_KEY     # SSH接続用秘密鍵
EC2_USER                # SSHユーザー名（通常はubuntu）
SUPABASE_URL            # Supabase プロジェクトURL
SUPABASE_KEY            # Supabase サービスロールキー
```

**注意**: APIによって必要な環境変数は異なります。詳細は [環境変数の確認方法](#環境変数の確認方法) を参照。

### ステップ1: 実装前の確認

#### 1-1. アプリケーションが必要とする環境変数を確認

```bash
# アプリケーションコードで環境変数のチェックを検索
cd /path/to/your-api
grep -rn "os.getenv\|os.environ" main.py app.py
grep -rn "raise.*環境変数\|raise.*設定されていません" *.py
```

**よくある必須環境変数:**
- Supabase系: `SUPABASE_URL`, `SUPABASE_KEY`
- AWS系: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- OpenAI系: `OPENAI_API_KEY`

見つかった環境変数をリストアップして、次のステップで使用します。

#### 1-2. ローカルでDocker動作確認

```bash
# Dockerイメージのクリーンビルドと動作確認
docker build --no-cache -f Dockerfile -t test-image .
docker run --env-file .env.local test-image

# 動作確認できたらCI/CDへ進む
```

#### 1-3. ECRリポジトリ名を決定

- **GitHubリポジトリ名とは別の名前**を使用（例: `watchme-{api-name}`）
- すべての設定ファイルで**同じ名前**を使用する

### ステップ2: 初回セットアップ（1回限りの手動作業）

#### 2-1. ECRリポジトリの作成

```bash
# AWS CLIでECRリポジトリを作成
aws ecr create-repository \
  --repository-name watchme-{api-name} \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true
```

#### 2-2. EC2サーバーの準備

```bash
# EC2に接続
ssh -i ~/watchme-key.pem ubuntu@{EC2_HOST}

# アプリケーション用ディレクトリ作成
mkdir -p /home/ubuntu/{api-directory-name}

# Dockerネットワークの確認/作成
docker network create watchme-network 2>/dev/null || true

# ディレクトリが作成されたことを確認
ls -la /home/ubuntu/{api-directory-name}

# ログアウト
exit
```

#### 2-3. 初回セットアップ完了チェックリスト

- [ ] ECRリポジトリが作成されている
- [ ] EC2上にアプリケーションディレクトリが作成されている
- [ ] GitHub Secretsがすべて設定されている
- [ ] Dockerネットワーク `watchme-network` が存在する
- [ ] 必須環境変数をリストアップ済み

### ステップ3: 設定ファイルの作成

#### 3-1. ディレクトリ構成

⚠️ **重要**: WatchMeプロジェクトでは、設定ファイルは **server-configs リポジトリで集中管理** します。

**APIリポジトリ（例: api-profiler）:**
```
/your-api-repository/
├── .github/
│   └── workflows/
│       └── deploy-ecr.yml       # CI/CDワークフロー（APIリポジトリに配置）
├── Dockerfile.prod              # Dockerイメージ定義
├── main.py                      # アプリケーションコード
└── requirements.txt
```

**server-configs リポジトリ（設定ファイルの集中管理）:**
```
/watchme-server-configs/production/
├── docker-compose-files/
│   └── {api-name}-docker-compose.prod.yml  # Docker Compose設定
├── systemd/
│   └── {api-name}.service                  # systemdサービス定義
└── sites-available/
    └── api.hey-watch.me                    # Nginx設定（全API共通）
```

**なぜ集中管理するのか:**
- ✅ すべてのAPI設定を1箇所で管理（一貫性の保証）
- ✅ EC2上で `git pull` するだけで全API設定を更新可能
- ✅ Nginx設定は全APIで共有（1ファイルで管理）
- ✅ systemdサービスは統一されたパスを参照

#### 3-2. `server-configs/production/docker-compose-files/{api-name}-docker-compose.prod.yml` の作成

**ファイルパス**: `/path/to/server-configs/production/docker-compose-files/{api-name}-docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  api:
    image: 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-{api-name}:latest
    container_name: {api-name}
    ports:
      - "127.0.0.1:{port}:{port}"  # localhostのみ公開（Nginx経由でアクセス）
    env_file:
      - /home/ubuntu/{api-directory-name}/.env  # 絶対パスで指定
    restart: always
    networks:
      - watchme-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  watchme-network:
    external: true
```

**重要ポイント:**
- `env_file`: 絶対パスで `/home/ubuntu/{api-directory-name}/.env` を指定
- `ports`: セキュリティのため `127.0.0.1:{port}:{port}` 形式（外部直接アクセス不可）
- `container_name`: システム全体で一意の名前

#### 3-3. `server-configs/production/systemd/{api-name}.service` の作成

**ファイルパス**: `/path/to/server-configs/production/systemd/{api-name}.service`

```ini
[Unit]
Description={API Name} Docker Container
After=docker.service watchme-infrastructure.service
Requires=docker.service watchme-infrastructure.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/{api-directory-name}
TimeoutStartSec=0
Restart=always
RestartSec=10

# ECR login
ExecStartPre=-/bin/bash -c 'aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com'

# Pull latest image
ExecStartPre=-/usr/local/bin/docker-compose -f /home/ubuntu/watchme-server-configs/production/docker-compose-files/{api-name}-docker-compose.prod.yml pull

# Start with Docker Compose
ExecStartPre=-/usr/local/bin/docker-compose -f /home/ubuntu/watchme-server-configs/production/docker-compose-files/{api-name}-docker-compose.prod.yml down
ExecStart=/usr/local/bin/docker-compose -f /home/ubuntu/watchme-server-configs/production/docker-compose-files/{api-name}-docker-compose.prod.yml up
ExecStop=/usr/local/bin/docker-compose -f /home/ubuntu/watchme-server-configs/production/docker-compose-files/{api-name}-docker-compose.prod.yml down

[Install]
WantedBy=multi-user.target
```

**重要ポイント:**
- Docker Composeファイルのパスは `watchme-server-configs` 内を参照
- `WorkingDirectory` は `/home/ubuntu/{api-directory-name}`（.envファイルの配置場所）

#### 3-4. `server-configs/production/sites-available/api.hey-watch.me` へのlocation追加

**既存のNginx設定ファイルに追加**:

```nginx
# {API Name} - {説明} (YYYY-MM-DD)
location /{api-path}/ {
    proxy_pass http://localhost:{port}/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # タイムアウト設定（180秒）
    proxy_read_timeout 180s;
    proxy_connect_timeout 180s;
    proxy_send_timeout 180s;

    # CORS設定
    add_header "Access-Control-Allow-Origin" "*";
    add_header "Access-Control-Allow-Methods" "GET, POST, OPTIONS";
    add_header "Access-Control-Allow-Headers" "Content-Type, Authorization";

    # OPTIONSリクエストの処理
    if ($request_method = "OPTIONS") {
        return 204;
    }
}
```

**外部URL**: `https://api.hey-watch.me/{api-path}/`

#### 3-5. `.github/workflows/deploy-ecr.yml` の作成

完全なテンプレートは [GitHub Actionsワークフロー仕様](#github-actionsワークフロー仕様) を参照。

**重要ポイント:**

1. **ECRリポジトリ名を環境変数で定義**
```yaml
env:
  AWS_REGION: ap-southeast-2
  ECR_REPOSITORY: watchme-{api-name}  # ★ここを正しく設定
```

2. **ディレクトリ作成ステップを追加**（べき等性確保）
```yaml
- name: Create application directory on EC2 if not exists
  run: |
    ssh ${EC2_USER}@${EC2_HOST} "mkdir -p /home/ubuntu/{api-directory-name}"
```

3. **環境変数ファイル作成ステップ**（ステップ1-1でリストアップした変数をすべて含める）
```yaml
- name: Create/Update .env file on EC2
  env:
    # ★必要な環境変数をすべて定義
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: |
    ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
      cd /home/ubuntu/{api-directory-name}
      echo "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}" > .env
      echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}" >> .env
      echo "SUPABASE_URL=${SUPABASE_URL}" >> .env
      echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
    ENDSSH
```

### ステップ4: server-configs リポジトリへの設定ファイルのコミット

**重要**: まず server-configs リポジトリに設定ファイルをコミットします。

```bash
# server-configs リポジトリで作業
cd /path/to/server-configs

# 作成した設定ファイルを追加
git add production/docker-compose-files/{api-name}-docker-compose.prod.yml
git add production/systemd/{api-name}.service
git add production/sites-available/api.hey-watch.me

# コミット＆プッシュ
git commit -m "feat: Add {API Name} configuration"
git push origin main
```

### ステップ5: EC2へ設定ファイルの反映

```bash
# EC2に接続
ssh -i ~/watchme-key.pem ubuntu@{EC2_HOST}

# server-configs を最新化
cd /home/ubuntu/watchme-server-configs
git pull origin main

# systemd サービスをインストール
sudo cp production/systemd/{api-name}.service /etc/systemd/system/{api-name}.service
sudo systemctl daemon-reload
sudo systemctl enable {api-name}

# Nginx 設定を反映（server-configs内のファイルはシンボリックリンクで既に反映されている場合が多い）
sudo nginx -t  # 設定テスト
sudo systemctl reload nginx

# ログアウト
exit
```

### ステップ6: APIリポジトリのCI/CD設定とデプロイ実行

```bash
# APIリポジトリで作業
cd /path/to/your-api-repository

# GitHub Actions ワークフローを追加
git add .github/workflows/deploy-ecr.yml
git commit -m "feat: Add CI/CD configuration"
git push origin main

# GitHub Actionsの実行を確認
# https://github.com/{organization}/{repository}/actions
```

### ステップ7: 動作確認

```bash
# EC2でコンテナが起動しているか確認
ssh ubuntu@{EC2_HOST}
docker ps | grep {container-name}

# ヘルスチェック
curl http://localhost:{port}/health

# ログ確認
docker logs {container-name} --tail 100
```

---

## ファイル仕様リファレンス

### GitHub Actionsワークフロー仕様

#### ⚠️ deploy-to-ec2ジョブの必須ステップチェックリスト

**以下のステップが順番通りに実装されているか確認してください：**

- [ ] ステップ1: コードのチェックアウト（`actions/checkout@v4`）← **忘れやすい**
- [ ] ステップ2: SSHエージェントのセットアップ（`webfactory/ssh-agent@v0.9.0`）
- [ ] ステップ3: Known Hostsの追加（`ssh-keyscan`）
- [ ] ステップ4: EC2にディレクトリ作成（`mkdir -p`）
- [ ] ステップ5: ファイルをEC2にコピー（`scp docker-compose.prod.yml run-prod.sh`）← **忘れやすい**
- [ ] ステップ6: .envファイル作成/更新（`echo "VAR=value" > .env`）
- [ ] ステップ7: デプロイスクリプト実行（`./run-prod.sh`）

#### Dockerイメージビルドの標準テンプレート

```yaml
- name: Delete old images from ECR (optional but recommended)
  run: |
    aws ecr batch-delete-image \
      --region ${{ env.AWS_REGION }} \
      --repository-name ${{ env.ECR_REPOSITORY }} \
      --image-ids imageTag=latest || true

- name: Build, tag, and push image to Amazon ECR
  env:
    ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
    IMAGE_TAG: ${{ github.sha }}
  run: |
    docker buildx build \
      --platform linux/arm64 \
      --no-cache \              # ★必須：キャッシュを無効化
      --push \
      -f Dockerfile \
      -t $ECR_REGISTRY/${{ env.ECR_REPOSITORY }}:$IMAGE_TAG \
      -t $ECR_REGISTRY/${{ env.ECR_REPOSITORY }}:latest \
      .
```

#### 環境変数の確認方法

**重要: .envファイルに含める環境変数は、アプリケーションコードによって異なります**

**チェック方法:**
```bash
# アプリケーションコードで環境変数のチェックを検索
grep -r "os.getenv\|os.environ" main.py app.py
grep -r "raise.*環境変数\|raise.*設定されていません" main.py app.py
```

**GitHub Secretsと.envファイルの関係:**
- **GitHub Secrets**: GitHub Actions実行中のみ利用可能
- **.envファイル**: EC2上のDockerコンテナ内で利用可能
- **重要**: GitHub Secretsはコンテナ内に自動的には渡されない
- **必須**: 必要な環境変数をすべて.envファイルに明示的に書き込む

### run-prod.sh仕様

#### 必須要件

- docker-composeを使用（`docker run` 直接実行は禁止）
- カレントディレクトリの.envを参照
- ハードコードされた認証情報は含めない
- 既存コンテナの完全削除を保証

#### デプロイフロー

```
1. ECRから最新イメージを取得
2. 既存コンテナの完全削除（3層アプローチ）
3. 新規コンテナの起動
4. ヘルスチェックで起動確認
```

#### コンテナ削除の実装（3層アプローチ）

```bash
# 1. 実行中コンテナの検索と停止
RUNNING_CONTAINERS=$(docker ps -q --filter "name=container-name")
if [ ! -z "$RUNNING_CONTAINERS" ]; then
    docker stop $RUNNING_CONTAINERS
fi

# 2. 全コンテナの削除（停止済み含む）
ALL_CONTAINERS=$(docker ps -aq --filter "name=container-name")
if [ ! -z "$ALL_CONTAINERS" ]; then
    docker rm -f $ALL_CONTAINERS
fi

# 3. docker-compose管理コンテナの削除
docker-compose -f docker-compose.prod.yml down || true
```

**重要ポイント:**
- 検索してから削除（存在確認）
- ログ出力で進捗を明確化
- エラー耐性（一部失敗しても継続）

#### ⚠️ デプロイ失敗の典型的パターンと対策

**問題1: `docker system prune -a -f` の誤用**

❌ **絶対にやってはいけないこと:**
```bash
# GitHub Actionsワークフロー内で
docker system prune -a -f  # すべてのイメージを削除
docker-compose pull         # 直後にpull
```

**何が起こるか:**
1. `prune -a -f` が全イメージ（ECRからpullした最新イメージも）を削除
2. `docker-compose pull` がキャッシュを誤認識してスキップ
3. **結果: 古いコンテナが稼働し続ける**

✅ **正しい実装:**
```bash
# GitHub Actionsワークフロー内で
docker-compose down || true  # コンテナのみ削除

# ❌ docker system prune は使わない

# run-prod.sh内で強制pull
docker pull --platform linux/arm64 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/{repository}:latest
```

**問題2: `docker-compose pull` の不確実性**

❌ **問題のある実装:**
```bash
docker-compose pull  # 既存イメージがあるとスキップする可能性
```

✅ **確実な実装:**
```bash
# 直接docker pullで強制的に最新を取得
docker pull --platform linux/arm64 {ECR-URI}:latest

# プルしたイメージの確認
docker images | grep {repository-name} | head -1
```

**問題3: デプロイ検証の欠如**

❌ **問題:**
- デプロイ成功と報告されるが、実際には古いコードが稼働
- 手動確認するまで気づかない

✅ **解決策: デプロイ検証スクリプトの導入**
```bash
#!/bin/bash
# verify-deployment.sh

# Check 1: Container is running
docker ps | grep -q {container-name} || exit 1

# Check 2: Health endpoint
curl -f http://localhost:{port}/health || exit 1

# Check 3: Code verification (model name, key features)
docker exec {container-name} cat main.py | grep -q '{expected-pattern}' || exit 1

# Check 4: Verify ECR image
EXPECTED_IMAGE="{ECR-URI}:latest"
ACTUAL_IMAGE=$(docker inspect {container-name} --format='{{.Config.Image}}')
[ "$ACTUAL_IMAGE" == "$EXPECTED_IMAGE" ] || exit 1

echo "✅ Deployment verified successfully"
```

### Dockerfile仕様

#### ⚠️ 必須チェック：アプリケーションファイルのコピー漏れ防止

**問題**: 新規ファイル（例：llm_providers.py）を追加したが、Dockerfileでコピーし忘れる

**症状**:
```
ModuleNotFoundError: No module named 'new_module'
ImportError: cannot import name 'function_name'
```

**診断方法**:
```bash
# 1. アプリケーションで使用されている全Pythonファイルを確認
ls *.py

# 2. Dockerfileでコピーされているファイルを確認
grep "COPY.*\.py" Dockerfile Dockerfile.prod

# 3. 差分を確認（コピーされていないファイルがあるか）
```

**予防策（推奨）**: ワイルドカードでまとめてコピー

```dockerfile
# ❌ 悪い例：個別にCOPY（追加時に忘れやすい）
COPY main.py .
COPY supabase_client.py .
# llm_providers.py を忘れた！

# ✅ 良い例：パターンマッチでまとめてコピー
COPY *.py .
```

**個別COPYが必要な場合**: 明示的にチェックリスト化

```dockerfile
# アプリケーションファイルのコピー
# ★新規ファイル追加時は必ずここに追記すること
COPY main.py .
COPY supabase_client.py .
COPY llm_providers.py .
COPY config.py .
# TODO: 新規Pythonファイルを追加したらここに追記
```

**ベストプラクティス**: 実装チェックリスト

新規Pythonファイルを追加したら：
- [ ] Dockerfileに `COPY {new_file}.py .` を追加
- [ ] Dockerfile.prodに `COPY {new_file}.py .` を追加（本番用がある場合）
- [ ] ローカルでDocker動作確認: `docker build -t test . && docker run test`
- [ ] git push前に必ずローカルDockerテスト

#### 🚨 重要：大きなAIモデルを使用する場合の必須対応

**対象API**: Kushinada、Whisper、BERT系モデルなど、1GB以上の大きなモデルを使用するAPI

**問題**:
- AIモデルのダウンロードに3-5分かかる
- 実行時にダウンロードするとCI/CDが毎回タイムアウトする
- ネットワークエラーのリスクがある

**✅ 根本的解決策：ビルド時にモデルをプリロード**

```dockerfile
# HuggingFaceトークンを引数から受け取る
ARG HF_TOKEN
RUN test -n "$HF_TOKEN" || (echo "Error: HF_TOKEN build arg is required" && exit 1)

# ✅ モデルとチェックポイントをビルド時に完全ダウンロード
# これにより実行時のダウンロード時間（3-5分）を完全に排除
RUN HF_TOKEN=${HF_TOKEN} python3 -c "\
from transformers import HubertModel; \
from huggingface_hub import hf_hub_download; \
import os; \
os.environ['HF_TOKEN'] = '${HF_TOKEN}'; \
print('🔧 モデルをダウンロード中...'); \
HubertModel.from_pretrained('imprt/kushinada-hubert-large', token='${HF_TOKEN}'); \
print('✅ モデルダウンロード完了'); \
print('🔧 チェックポイントをダウンロード中...'); \
checkpoint_path = hf_hub_download( \
    repo_id='imprt/kushinada-hubert-large-jtes-er', \
    filename='s3prl/result/downstream/kushinada-hubert-large-jtes-er_fold1/dev-best.ckpt', \
    token='${HF_TOKEN}' \
); \
print(f'✅ チェックポイントダウンロード完了: {checkpoint_path}'); \
"
```

**GitHub Actionsでの設定**:
```yaml
- name: Build, tag, and push image to Amazon ECR
  env:
    HF_TOKEN: ${{ secrets.HF_TOKEN }}  # ★HF_TOKENを渡す
  run: |
    docker buildx build \
      --platform linux/arm64 \
      --no-cache \
      --push \
      --build-arg HF_TOKEN=$HF_TOKEN \  # ★ビルド引数として渡す
      -f Dockerfile \
      -t $ECR_REGISTRY/${{ env.ECR_REPOSITORY }}:latest \
      .
```

**メリット**:
- ✅ コンテナ起動時間：3-5分 → 数秒（99%削減）
- ✅ CI/CD信頼性：毎回失敗 → 安定動作
- ✅ ネットワークエラーリスク：排除
- ✅ 本番環境でHF_TOKEN不要

**トレードオフ**:
- ⚠️ Dockerイメージサイズ：約1.5-2GB増加
- ⚠️ ビルド時間：約3-5分増加（初回のみ）
- ✅ 実行時間：3-5分削減（毎回）

**ヘルスチェック設定の調整**:

⚠️ **重要**: モデルをイメージに含めても、初回デプロイではキャッシュが空のため約40秒かかります。

```dockerfile
# 初回デプロイを考慮して、十分な猶予を設定
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8018/health || exit 1
```

```yaml
# docker-compose.prod.ymlも同様に設定
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8018/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s  # 初回デプロイはモデルロードに約40秒かかる
```

**CI/CDワークフローのヘルスチェック**:
```yaml
# 最大60秒間（12回 × 5秒）リトライ
for i in {1..12}; do
  if curl -f http://localhost:8018/health > /dev/null 2>&1; then
    echo "✅ Health check passed (attempt $i/12)"
    break
  fi
  echo "  Attempt $i/12 failed, retrying in 5 seconds..."
  sleep 5
done
```

**キャッシュディレクトリの注意点**:
- ビルド時: `/root/.cache/huggingface/`
- 実行時: `ENV TRANSFORMERS_CACHE=/app/.cache`（異なる場合がある）
- → 初回起動時にHugging Faceから再ダウンロードが発生する可能性

**2回目以降のデプロイ**:
- キャッシュが効くため数秒で起動
- ヘルスチェックは1-2回目で成功

**参考実装**: `emotion-analysis-feature-extractor-v3` (Kushinadaモデル)

---

#### 空ディレクトリ問題の対処

**問題**: Gitは空ディレクトリを追跡しないため、Dockerビルド時に必要なディレクトリが存在しない可能性

**解決策**: Dockerfile内で必要なディレクトリを明示的に作成

```dockerfile
# アプリケーションコードをコピー
COPY . .

# 必要なディレクトリを作成（FastAPIでstatic/templatesを使う場合）
RUN mkdir -p /app/static /app/templates || true
```

### docker-compose.prod.yml仕様

#### 必須設定要素

- **image**: ECRのフルパス（`754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/{ECR_REPOSITORY}:latest`）
- **container_name**: 一意のコンテナ名（システム全体で重複不可）
- **env_file**: `.env` を参照
- **ports**: `127.0.0.1:{port}:{port}` 形式（セキュリティ）
- **networks**: `watchme-network` (external: true)

#### 設定の整合性

- imageのリポジトリ名は全設定ファイルで統一
- container_nameはデプロイスクリプトと一致
- networksは事前に作成済みのものを使用

---

## トラブルシューティング

### 問題パターン早見表

| 症状 | 確認コマンド | 対処法 |
|-----|------------|-------|
| デプロイ成功するが動作しない | `grep -o "watchme-[a-z-]*" *.yml *.sh` | ECRリポジトリ名を全ファイルで統一 |
| 環境変数が展開されていない | `cat .env \| grep "\$"` | echoコマンドで環境変数作成 |
| 古いコードが動いている | `docker images --no-trunc` | `--no-cache` オプション追加 |
| コンテナ名が競合 | `docker ps -a \| grep {name}` | 既存コンテナを完全削除 |
| コンテナ起動直後にクラッシュ | `docker logs {name} --tail 100` | 必須環境変数が.envに含まれているか確認 |

### コンテナ起動直後のクラッシュ（環境変数不足エラー）

#### 症状

```
ValueError: AWS_ACCESS_KEY_IDおよびAWS_SECRET_ACCESS_KEYが設定されていません
RuntimeError: 環境変数XXXXが設定されていません
```

#### 診断手順

**1. コンテナログの確認**
```bash
ssh ubuntu@{EC2_HOST}
docker logs {container-name} --tail 100
```

**2. アプリケーションコードで必須環境変数を確認**
```bash
cd /path/to/api
grep -rn "os.getenv\|os.environ" main.py app.py
grep -rn "raise.*環境変数\|raise.*設定されていません" *.py
```

**3. 現在の.envファイルを確認**
```bash
ssh ubuntu@{EC2_HOST}
cat /home/ubuntu/{api-name}/.env
```

#### 解決方法

**ステップ1**: 不足している環境変数を特定（上記診断手順2の結果）

**ステップ2**: GitHub Secretsに値が登録されているか確認
- リポジトリの Settings > Secrets and variables > Actions で確認

**ステップ3**: `deploy-to-ecr.yml` を修正

```yaml
# 修正前（不足している場合）
- name: Create/Update .env file on EC2
  env:
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: |
    ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
      cd /home/ubuntu/{api-name}
      echo "SUPABASE_URL=${SUPABASE_URL}" > .env
      echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
    ENDSSH

# 修正後（必要な変数を追加）
- name: Create/Update .env file on EC2
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}         # ★追加
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }} # ★追加
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: |
    ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
      cd /home/ubuntu/{api-name}
      echo "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}" > .env             # ★追加
      echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}" >> .env   # ★追加
      echo "SUPABASE_URL=${SUPABASE_URL}" >> .env
      echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
    ENDSSH
```

**ステップ4**: コミット＆プッシュ
```bash
git add .github/workflows/deploy-to-ecr.yml
git commit -m "Fix: Add missing environment variables to .env"
git push origin main
```

#### 予防策

新しいAPIのCI/CD実装時：
1. アプリケーションコードで `grep -r "os.getenv" .` を実行
2. 必須環境変数をすべてリストアップ
3. 初回から.envファイルにすべて含める
4. ローカルでDocker動作確認してからCI/CD実装

### コンテナ競合エラー

#### 症状

```
Error: Conflict. The container name "/container-name" is already in use
```

#### 診断手順

**1. 既存コンテナの確認**
```bash
ssh ubuntu@{EC2_HOST}
docker ps -a | grep {container-name}
```

**2. コンテナの起動方法を特定**
- `docker-compose ps` で表示される → docker-compose管理
- 表示されない → `docker run` 直接起動またはsystemd管理

**3. 解決方法**
```bash
# 既存コンテナを完全に削除
docker stop {container-name} 2>/dev/null || true
docker rm -f {container-name} 2>/dev/null || true
docker-compose -f docker-compose.prod.yml down --remove-orphans

# 新規起動
docker-compose -f docker-compose.prod.yml up -d
```

### ECRリポジトリ名の不一致

#### ⚠️ 重要：リポジトリ名の違いを理解する

**GitHubリポジトリとECRリポジトリは別物:**
- **GitHubリポジトリ名**: 例 `admin`, `api-sed-aggregator`
- **ECRリポジトリ名**: 例 `watchme-admin`, `watchme-api-sed-aggregator`

#### ECRリポジトリ名の一貫性チェック

```bash
# 以下のコマンドで同じ名前が表示されることを確認
grep "ECR_REPOSITORY" .github/workflows/*.yml
grep "image:" docker-compose.prod.yml
```

#### よくあるミス

- ❌ GitHubリポジトリ名をECRリポジトリ名として使用
- ❌ `ECR_REPOSITORY` と `docker-compose.yml` のimageが不一致
- ✅ 正解: ECR関連の設定はすべて同じECRリポジトリ名を使用

### デプロイが失敗する場合の確認事項

#### 1. コミットとプッシュの確認

```bash
# ローカルとリモートの同期確認
git status
git fetch origin && git diff origin/main --stat

# 最新コミットがGitHubに反映されているか
git log --oneline -1
git log --oneline origin/main -1
```

#### 2. ECRイメージの更新確認

```bash
# 最新イメージがECRにあるか確認
aws ecr describe-images \
  --repository-name {ECR_REPOSITORY} \
  --region ap-southeast-2 \
  --query 'sort_by(imageDetails,& imagePushedAt)[-1].[imageTags[0],imagePushedAt]' \
  --output text
```

#### 3. 必須ステップの実装確認

```bash
# ECR削除ステップがあるか
grep -n "Delete old images from ECR" .github/workflows/deploy-to-ecr.yml

# --no-cacheが使われているか
grep -n "no-cache" .github/workflows/deploy-to-ecr.yml

# リポジトリ名が統一されているか
grep -h "ECR_REPOSITORY\|image:" *.yml *.sh .github/workflows/*.yml | grep -o "watchme-[a-z-]*" | sort -u
```

---

## セキュリティ考慮事項

- 認証情報はGitHub Secretsでのみ管理
- `.env` ファイルは `.gitignore` に含める
- Dockerイメージに認証情報を含めない
- ハードコードは完全に排除
- ログに認証情報を出力しない（デバッグ時も注意）

---

## 適用対象API一覧

| API名 | ディレクトリ | ポート | 外部URL | 現状 |
|------|------------|--------|---------|------|
| profiler-api | /home/ubuntu/profiler-api | 8051 | /profiler/ | ✅ 完全対応 (2025-11-13) |
| aggregator | /home/ubuntu/aggregator | 8050 | /aggregator/ | ✅ 完全対応 |
| api-sed-aggregator | /home/ubuntu/api-sed-aggregator | 8010 | /behavior-aggregator/ | ✅ 完全対応 |
| emotion-analysis-feature-extractor-v3 | /home/ubuntu/emotion-analysis-feature-extractor-v3 | 8018 | /emotion-analysis/feature-extractor/ | ✅ 正常 |
| api_ast | /home/ubuntu/api_ast | 8017 | /behavior-analysis/features/ | ⚠️ 要修正 |
| opensmile-aggregator | /home/ubuntu/opensmile-aggregator | 8012 | /emotion-analysis/aggregator/ | ⚠️ 要確認 |

---

## 📋 現在の起動方法・管理方法の全体像（2025-11-21更新）

### 🎯 概要

WatchMeプロジェクトでは、**2つの異なる起動方式**が混在しています。
これは歴史的経緯によるもので、現在**統一化作業を進めています**。

**2つの起動方式:**
1. **GitHub Actions方式**（新標準） - 完全自動CI/CD
2. **systemd + 集中管理方式**（移行期） - systemdサービスが集中管理ファイルを参照

### 🔄 起動方式の詳細

#### 方式1: GitHub Actions方式（新標準・推奨）✨

**特徴:**
- `git push` だけで自動デプロイ
- 各APIリポジトリが独立して管理
- EC2上のディレクトリに設定ファイルを自動配置

**デプロイフロー:**
```
git push → GitHub Actions起動 → ECRにイメージpush →
EC2にSSH → ディレクトリ内に.env/docker-compose.prod.yml配置 →
既存コンテナ削除 → 新規コンテナ起動 → ヘルスチェック
```

**EC2上の配置:**
```
/home/ubuntu/{api-name}/
├── .env                      # GitHub Actionsが作成
├── docker-compose.prod.yml   # GitHub Actionsがコピー
└── run-prod.sh               # GitHub Actionsがコピー
```

**管理方法:**
- コンテナは `docker-compose.prod.yml` の `restart: always` で自動再起動
- systemdサービスは**使用しない**

**適用サービス（8個）:**

| サービス | コンテナ名 | ポート | GitHubリポジトリ | ECRリポジトリ | 稼働状況 |
|---------|-----------|--------|----------------|--------------|---------|
| Behavior Features | behavior-analysis-feature-extractor | 8017 | api-behavior-analysis-feature-extractor-v3 | watchme-behavior-analysis-feature-extractor | ✅ 正常（v3 PaSST稼働中） |
| Emotion Features | emotion-analysis-feature-extractor | 8018 | api-emotion-analysis-feature-extractor-v3 | watchme-emotion-analysis-feature-extractor | ✅ 正常 |
| Vibe Transcriber | vibe-analysis-transcriber | 8013 | api-vibe-analysis-transcriber | watchme-vibe-analysis-transcriber | ✅ 正常 |
| Vault API | watchme-vault-api | 8000 | api-vault | watchme-api-vault | ✅ 正常 |
| Aggregator API | aggregator-api | 8011 | api-aggregator | watchme-aggregator | ✅ 正常 |
| Admin | watchme-admin | 9000 | admin | watchme-admin | ✅ 正常 |
| Janitor | janitor-api | 8030 | api-janitor | watchme-api-janitor | ✅ 正常 |
| Avatar Uploader | watchme-avatar-uploader | 8014 | api-avatar-uploader | watchme-api-avatar-uploader | ✅ 正常 |

**確認コマンド:**
```bash
# コンテナが稼働しているか確認
ssh ubuntu@3.24.16.82
docker ps | grep {container-name}

# ログ確認
docker logs {container-name} --tail 100

# 再起動（GitHub Actions再実行、またはEC2上で手動）
cd /home/ubuntu/{api-name}
./run-prod.sh
```

#### 方式2: systemd + 集中管理方式（移行期）🔄

**特徴:**
- systemdサービスが `/home/ubuntu/watchme-server-configs/production/docker-compose-files/` 内のファイルを参照
- サーバー再起動時に自動起動（systemdが管理）
- GitHub Actionsも併用（ハイブリッド）

**デプロイフロー:**
```
git push → GitHub Actions起動 → ECRにイメージpush →
EC2にSSH → .envファイル作成 → systemdサービス再起動
```

**EC2上の配置:**
```
/home/ubuntu/{api-name}/
├── .env                      # GitHub Actionsが作成

/home/ubuntu/watchme-server-configs/production/
├── docker-compose-files/
│   └── {api-name}-docker-compose.prod.yml  # systemdが参照
└── systemd/
    └── {api-name}.service                   # systemdサービス定義
```

**systemdサービスの動作:**
```bash
# サービスは以下を実行
docker-compose -f /home/ubuntu/watchme-server-configs/production/docker-compose-files/{api-name}-docker-compose.prod.yml up
```

**適用サービス（4個）:**

| サービス | コンテナ名 | ポート | GitHubリポジトリ | ECRリポジトリ | systemdサービス名 | 稼働状況 |
|---------|-----------|--------|----------------|--------------|-----------------|---------|
| **Profiler API** | profiler-api | 8051 | api-profiler | watchme-profiler | profiler-api.service | ✅ 正常 |
| API Manager | watchme-api-manager-prod | 9001 | api-manager | watchme-api-manager | watchme-api-manager.service | ✅ 正常 |
| Web Dashboard | watchme-web-prod | 3000 | web | watchme-web | watchme-web-app.service | ✅ 正常 |
| Infrastructure | - | - | - | - | watchme-infrastructure.service | ✅ 正常（Dockerネットワーク管理） |

**確認コマンド:**
```bash
# systemdサービス状態確認
ssh ubuntu@3.24.16.82
sudo systemctl status profiler-api.service

# サービス再起動
sudo systemctl restart profiler-api.service

# ログ確認（systemd経由）
sudo journalctl -u profiler-api.service -n 50

# ログ確認（Docker）
docker logs profiler-api --tail 100
```

### ⚠️ 重要：不整合の修正について

**現在の状況（2025-11-21時点）:**

以下のsystemdサービスは**設定ファイルの不整合により失敗**していましたが、**2025-11-21に無効化しました**。
これらのサービスは実際には **GitHub Actions方式で稼働中** のため、問題ありません。

**無効化したsystemdサービス（8個）:**
- `behavior-analysis-feature-extractor-v2.service` - docker-composeファイルが存在しない
- `emotion-analysis-aggregator.service` - docker-composeファイルが存在しない
- `emotion-analysis-feature-extractor-v3.service` - docker-composeファイルが存在しない
- `vibe-analysis-transcriber-v2.service` - docker-composeファイルが存在しない
- `vibe-analysis-transcriber.service` - コンテナ起動失敗
- `watchme-admin.service` - コンテナ起動失敗
- `watchme-avatar-uploader.service` - コンテナ起動失敗
- `watchme-vault-api.service` - コンテナ起動失敗

**無効化の経緯:**
1. これらのサービスは古いsystemd設定（移行期の設定ミス）
2. 実際のコンテナはGitHub Actionsで正常稼働中
3. systemdサービスは `auto-restart` 状態で失敗を繰り返していた
4. 実害はないが、`systemctl list-units` で混乱を招くため無効化

**無効化コマンド（実施済み）:**
```bash
sudo systemctl stop behavior-analysis-feature-extractor-v2 emotion-analysis-aggregator \
  emotion-analysis-feature-extractor-v3 vibe-analysis-transcriber-v2 vibe-analysis-transcriber \
  watchme-admin watchme-avatar-uploader watchme-vault-api

sudo systemctl disable behavior-analysis-feature-extractor-v2 emotion-analysis-aggregator \
  emotion-analysis-feature-extractor-v3 vibe-analysis-transcriber-v2 vibe-analysis-transcriber \
  watchme-admin watchme-avatar-uploader watchme-vault-api
```

**影響:**
- ✅ コンテナの稼働には**影響なし**（`restart: always`で自動再起動）
- ✅ EC2再起動時もコンテナは自動起動される
- ✅ systemdの状態がクリーンになった

**今後の予定:**
- Profiler API、API Manager、Web Dashboardも**GitHub Actions方式に統一**予定
- 完全移行後、systemdサービスは `watchme-infrastructure.service` のみとなる予定

### 📊 起動方式の比較

| 項目 | GitHub Actions方式 | systemd + 集中管理方式 |
|------|-------------------|---------------------|
| **デプロイ方法** | `git push` のみ | `git push` + `systemctl restart` |
| **設定ファイル管理** | APIリポジトリ内 | server-configsリポジトリ |
| **再起動管理** | `restart: always` | systemd |
| **EC2再起動時** | Dockerが自動再起動 | systemdが自動起動 |
| **メリット** | 完全自動化・リポジトリ独立 | サーバー全体の一元管理 |
| **デメリット** | 各リポジトリに設定重複 | 設定変更時にserver-configs更新が必要 |
| **推奨度** | ✅ 新標準（推奨） | ⚠️ 移行期（段階的廃止予定） |

### 🔍 現在稼働中の全コンテナ一覧（2025-11-21確認済み）

```bash
# 確認コマンド
ssh ubuntu@3.24.16.82
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

| コンテナ名 | 稼働時間 | 起動方式 | 管理方法 |
|-----------|---------|---------|---------|
| aggregator-api | 41時間 | GitHub Actions | docker-compose |
| profiler-api | 44時間 | GitHub Actions + systemd | systemd |
| emotion-analysis-feature-extractor | 2日 | GitHub Actions | docker-compose |
| behavior-analysis-feature-extractor | 3日 | GitHub Actions | docker-compose |
| vibe-analysis-transcriber | 3日 | GitHub Actions | docker-compose |
| watchme-vault-api | 5日 | GitHub Actions | docker-compose |
| watchme-admin | 4週間 | GitHub Actions | docker-compose |
| janitor-api | 4週間 | GitHub Actions | docker-compose |
| demo-generator-api | 6週間 | GitHub Actions | docker-compose |
| watchme-avatar-uploader | 6週間 | GitHub Actions | docker-compose |
| watchme-api-manager-prod | 8週間 | systemd | systemd |
| watchme-web-prod | 2ヶ月 | systemd | systemd |

**合計:** 12コンテナ稼働中（全て正常）

### 🛠️ 管理コマンド早見表

#### 起動方式の確認
```bash
# コンテナがどのように起動されたか確認
ssh ubuntu@3.24.16.82
docker inspect {container-name} --format '{{.Config.Labels}}' | grep com.docker.compose.project.config_files
```

出力例:
- `/home/ubuntu/{api-name}/docker-compose.prod.yml` → GitHub Actions方式
- `/home/ubuntu/watchme-server-configs/production/docker-compose-files/xxx.yml` → systemd方式

#### GitHub Actions方式のサービス
```bash
# コンテナ再起動
cd /home/ubuntu/{api-name}
./run-prod.sh

# または直接docker-compose
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# ログ確認
docker logs {container-name} --tail 100 -f
```

#### systemd方式のサービス
```bash
# サービス再起動
sudo systemctl restart {service-name}

# 状態確認
sudo systemctl status {service-name}

# ログ確認
sudo journalctl -u {service-name} -n 100 -f
```

#### 全体確認
```bash
# 稼働中のコンテナ
docker ps

# systemdサービス（WatchMe関連のみ）
systemctl list-units --type=service | grep watchme

# 失敗しているsystemdサービス（現在は0件のはず）
systemctl list-units --type=service --state=failed
```

### 📝 新規API追加時の推奨フロー

新しいAPIを追加する場合は、**GitHub Actions方式（方式1）** を使用してください。

1. このドキュメントの [実装ガイド（新規API向け）](#実装ガイド新規api向け) を参照
2. systemdサービスは**作成不要**
3. `docker-compose.prod.yml` に `restart: always` を必ず設定
4. GitHub Actionsワークフローでヘルスチェックを実装

---
