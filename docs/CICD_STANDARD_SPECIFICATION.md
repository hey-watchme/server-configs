# WatchMe API CI/CD 標準仕様書

**目的**: 全WatchMe APIで統一されたCI/CDプロセスを定義

---

## 📖 クイックナビゲーション

| 目的 | セクション |
|-----|----------|
| 新規API実装 | [実装ガイド](#実装ガイド新規api向け) |
| 大規模AIモデル | [AIモデル対応](#-重要大きなaiモデルを使用する場合の必須対応) |
| エラー対処 | [トラブルシューティング](#トラブルシューティング) |
| 現状確認 | [起動方式の全体像](#-現在の起動方法管理方法の全体像2025-11-21更新) |

---

## ⚡ デプロイフロー

```
git push → GitHub Actions → ECRへpush → EC2へデプロイ → コンテナ起動 → ヘルスチェック
```

### 必須要件

1. **ECR名の一貫性**: 全設定ファイルで同じECRリポジトリ名
2. **コンテナの完全削除**: 既存コンテナを削除してから起動
3. **環境変数の完全性**: 必要な環境変数を.envに記載

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

**APIリポジトリ（例: api-profiler）:**
```
/your-api-repository/
├── .github/workflows/deploy-ecr.yml
├── Dockerfile
├── docker-compose.prod.yml
├── run-prod.sh
└── main.py
```

**server-configs リポジトリ（Nginx設定のみ）:**
```
/watchme-server-configs/production/sites-available/
└── api.hey-watch.me  # Nginx設定（全API共通）
```

#### 3-2. `docker-compose.prod.yml` の作成（APIリポジトリ内）

```yaml
version: '3.8'

services:
  api:
    image: 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-{api-name}:latest
    container_name: {api-name}
    ports:
      - "127.0.0.1:{port}:{port}"
    env_file:
      - .env
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

#### 3-3. Nginx設定の追加（server-configsリポジトリ）

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

#### 3-4. `.github/workflows/deploy-ecr.yml` の作成

重要ポイント:
- ECRリポジトリ名: `watchme-{api-name}`
- ディレクトリ作成: `mkdir -p /home/ubuntu/{api-directory-name}`
- 環境変数: 必要な変数をすべて.envに書き込む

### ステップ4: Nginx設定の反映（server-configsリポジトリ）

```bash
cd /path/to/server-configs
git add production/sites-available/api.hey-watch.me
git commit -m "feat: Add {API Name} Nginx location"
git push origin main

# EC2で反映
ssh -i ~/watchme-key.pem ubuntu@{EC2_HOST}
cd /home/ubuntu/watchme-server-configs
git pull origin main
sudo nginx -t
sudo systemctl reload nginx
exit
```

### ステップ5: APIリポジトリのCI/CD設定とデプロイ実行

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

### ステップ6: 動作確認

```bash
ssh ubuntu@{EC2_HOST}
docker ps | grep {container-name}
docker logs {container-name} --tail 100
curl http://localhost:{port}/health
```

---

## ファイル仕様リファレンス

### Dockerイメージビルド

**🚨 必須設定項目チェックリスト:**

- [ ] `--platform linux/arm64` を指定（EC2はGraviton2/ARM64）
- [ ] `--no-cache` を指定（キャッシュ問題を防ぐ）
- [ ] フロントエンドの場合: `ENV NODE_ENV=production` をDockerfileに追加
- [ ] 既存のコンテナとイメージを完全削除してから起動

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
      --platform linux/arm64 \  # ★必須：EC2はARM64
      --no-cache \              # ★必須：キャッシュを無効化
      --push \
      -f Dockerfile \
      -t $ECR_REGISTRY/${{ env.ECR_REPOSITORY }}:$IMAGE_TAG \
      -t $ECR_REGISTRY/${{ env.ECR_REPOSITORY }}:latest \
      .
```

**フロントエンド（React/Vue/Vite等）の追加要件:**

```dockerfile
# Dockerfile内で必ず設定
ENV NODE_ENV=production  # ★必須：本番ビルドを有効化
RUN npm run build
```

**理由:**
- `NODE_ENV=production` がないと、`vite.config.js` の `base` 設定が正しく適用されない
- キャッシュを使うと、古いビルド成果物が残る
- ARM64を指定しないと、AMD64イメージがビルドされEC2で動作しない

### 環境変数の確認

```bash
grep -r "os.getenv\|os.environ" main.py app.py
```

**重要**: GitHub Secretsはコンテナに自動的に渡されない。.envファイルに明示的に書き込む必要がある

### デプロイスクリプト（GitHub Actions内で実行）

**🚨 必須：完全削除＋再作成方式**

```bash
# 1. 既存のコンテナを停止・削除（新旧両方）
docker stop {new-container-name} || true
docker rm {new-container-name} || true
docker stop {old-container-name} || true  # 旧コンテナ名がある場合
docker rm {old-container-name} || true

# 2. 古いイメージも削除（キャッシュ問題を防ぐ）
docker rmi {ECR-URI}:latest || true

# 3. ECRから最新イメージをプル
docker pull --platform linux/arm64 {ECR-URI}:latest

# 4. Docker networkが存在しない場合は作成
docker network create watchme-network 2>/dev/null || true

# 5. 新しいコンテナを起動
docker run -d \
  --name {container-name} \
  --network watchme-network \
  -p {port}:{port} \
  --restart unless-stopped \
  {ECR-URI}:latest

# 6. ヘルスチェック（最大60秒間リトライ）
sleep 5
for i in {1..12}; do
  if docker ps | grep {container-name}; then
    echo "✅ Container started successfully"
    break
  fi
  echo "Waiting for container... ($i/12)"
  sleep 5
done
```

**注意事項:**
- ❌ `docker system prune -a -f` は使用禁止（全イメージを削除してしまう）
- ✅ 必ず `docker rmi` で特定のイメージのみ削除
- ✅ 旧コンテナ名がある場合は、両方削除する

### Dockerfile

**推奨**: ワイルドカードでファイルをコピー

```dockerfile
# ✅ 推奨
COPY *.py .

# ❌ 個別COPY（追加時に忘れやすい）
COPY main.py .
COPY supabase_client.py .
```

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


---

## トラブルシューティング

| 症状 | 原因 | 対処法 |
|-----|------|-------|
| **デプロイ成功するが古いコードが動く** | ❌ `--no-cache` 未設定 | Dockerビルドに `--no-cache` 追加 |
| **フロントエンドが真っ白** | ❌ `NODE_ENV=production` 未設定 | Dockerfileに `ENV NODE_ENV=production` 追加 |
| **コンテナが起動しない（ARM64エラー）** | ❌ `--platform linux/arm64` 未設定 | ビルドに `--platform linux/arm64` 追加 |
| **古いイメージが残る** | ❌ イメージ削除なし | デプロイ前に `docker rmi {URI}:latest` 実行 |
| **環境変数が読まれない** | .envファイル未作成 | .envファイルに `echo "VAR=${VAR}"` で書き込み |
| **コンテナ名が競合** | 旧コンテナ削除忘れ | `docker stop/rm` で新旧両方削除 |
| **ECRリポジトリ名が違う** | 設定ファイル間で不一致 | 全ファイルでECRリポジトリ名を統一 |
| **Pythonパッケージのバージョン競合** | 依存関係の互換性問題 | [Pythonパッケージ依存関係の解決](#pythonパッケージ依存関係の解決) 参照 |
| **初回デプロイが必ず失敗する** | EC2上のディレクトリ未作成 | [初回デプロイの事前準備](#初回デプロイの事前準備必須) 参照 |
| **Nginx設定が反映されない** | 設定ファイルが/etc/nginxにコピーされていない | [Nginx設定の反映方法](#nginx設定の反映方法) 参照 |

### 環境変数不足エラー

```bash
# 1. ログで不足している変数を確認
docker logs {container-name} --tail 100

# 2. コードで必要な変数を確認
grep -r "os.getenv\|os.environ" *.py

# 3. deploy-to-ecr.ymlに追加
# env: セクションと echo コマンドの両方に追加
```

---

### Pythonパッケージ依存関係の解決

**症状**: ECRへのDockerイメージpush時に `ERROR: ResolutionImpossible` が発生

**よくある原因**:
1. パッケージ間のバージョン競合
2. 存在しないバージョンの指定
3. 依存パッケージの最小バージョン要求

**解決手順**:

#### 1. エラーログから競合を特定

```bash
gh run view {run-id} --repo {org}/{repo} --log-failed | grep -i "error"
```

**エラー例**:
```
ERROR: Cannot install supabase because these package versions have conflicting dependencies.
  realtime 2.27.1 depends on pydantic>=2.11.7
  The user requested pydantic==2.6.3
```

#### 2. 依存関係ツリーを確認

**方法A: pipのエラーメッセージを確認**

エラーメッセージに表示される依存関係を読む：
```
The conflict is caused by:
    The user requested pydantic==2.6.3
    realtime 2.27.1 depends on pydantic<3.0.0 and >=2.11.7
```

**方法B: PyPIで直接確認**

1. https://pypi.org/ で問題のパッケージを検索
2. バージョン一覧から利用可能なバージョンを確認
3. 各バージョンの依存関係を確認

#### 3. バージョンの調整

**戦略1: メインパッケージを固定、依存パッケージを調整**

```python
# ❌ 古いバージョン（競合する）
supabase==2.3.4  # httpx<0.26 を要求
httpx==0.27.0    # 競合

# ✅ 新しいバージョン（互換性あり）
supabase==2.27.1  # httpx>=0.27 に対応
httpx==0.27.2
```

**戦略2: 連鎖的に更新**

```python
# supabase 2.27.1 の依存パッケージ realtime が pydantic>=2.11.7 を要求
# → pydantic を 2.11.7 に更新
# → pydantic 2.11.7 に対応した fastapi/uvicorn も更新

fastapi==0.115.0    # pydantic 2.11.7 対応
uvicorn==0.32.1
pydantic==2.11.7
supabase==2.27.1
httpx==0.27.2
```

#### 4. ローカルで検証

```bash
# 仮想環境で依存関係をテスト
cd /path/to/backend
python3 -m venv test_env
source test_env/bin/activate
pip install -r requirements.txt

# エラーがなければOK
# エラーが出たら requirements.txt を再調整
```

#### 5. 実際の例（Business API - 2026-01-10）

**問題の経緯**:
1. `supabase==2.3.4` + `httpx==0.27.0` → バージョン競合
2. `httpx==0.25.2` に変更 → `supabase==2.3.4` が `TypeError: Client.__init__() got an unexpected keyword argument 'proxy'` を発生
3. `supabase==2.12.2` に変更 → PyPIに存在しない（2.12.0までしかない）
4. `supabase==2.27.1` に変更 → `pydantic>=2.11.7` を要求
5. 最終的な解決:

```python
# requirements.txt (最終版)
fastapi==0.115.0
uvicorn==0.32.1
python-multipart==0.0.9
pydantic==2.11.7
python-dotenv==1.0.1
aiofiles==23.2.1
boto3==1.34.34
supabase==2.27.1
httpx==0.27.2
openpyxl==3.1.2
groq==0.4.2
openai==1.14.0
```

**教訓**:
- ✅ 最新の安定版を使用する（古いバージョンは互換性問題が多い）
- ✅ PyPIで実際に存在するバージョンを確認する
- ✅ エラーメッセージの依存関係ツリーを読み解く
- ✅ 連鎖的に関連パッケージも更新する

---

### 初回デプロイの事前準備（必須）

**重要**: GitHub Actionsのワークフローだけでは初回デプロイは完了しません。**必ず以下の手動セットアップが必要です**。

#### なぜ初回デプロイは失敗するのか？

GitHub Actionsのワークフローは以下を想定しています：
- EC2上にアプリケーションディレクトリが存在する
- Dockerネットワーク `watchme-network` が存在する
- ECRリポジトリが存在する

しかし、**初回は何も存在しない**ため、ワークフローが失敗します。

#### 必須の事前準備（初回のみ）

**ステップ1: ECRリポジトリの作成**

```bash
aws ecr create-repository \
  --repository-name watchme-{api-name} \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true
```

**ステップ2: EC2上のディレクトリとネットワークの作成**

```bash
ssh -i ~/watchme-key.pem ubuntu@{EC2_HOST}

# アプリケーションディレクトリ作成
mkdir -p /home/ubuntu/{api-directory-name}

# Dockerネットワーク作成（既に存在する場合はスキップ）
docker network create watchme-network 2>/dev/null || true

# 確認
ls -la /home/ubuntu/{api-directory-name}
docker network ls | grep watchme-network

exit
```

**ステップ3: GitHub Actionsを実行**

```bash
# ローカルからプッシュ（自動的にワークフローが起動）
git push origin main

# または手動実行
gh workflow run "Deploy to Amazon ECR and EC2" --repo {org}/{repo}
```

#### 実際の例（Business API - 2026-01-10）

```bash
# ステップ1: ECRリポジトリ作成（ローカル）
aws ecr create-repository \
  --repository-name watchme-business \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true

# ステップ2: EC2セットアップ
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82 << 'ENDSSH'
  mkdir -p /home/ubuntu/watchme-business-api
  docker network create watchme-network 2>/dev/null || true
  echo "✅ Setup complete"
ENDSSH

# ステップ3: デプロイ実行
gh workflow run "Deploy to Amazon ECR and EC2" --repo hey-watchme/business

# 進行状況確認
gh run watch
```

**チェックリスト**:
- [ ] ECRリポジトリが作成されている
- [ ] EC2上にアプリケーションディレクトリが作成されている
- [ ] Dockerネットワーク `watchme-network` が存在する
- [ ] GitHub Secretsがすべて設定されている

---

### Nginx設定の反映方法

**症状**: APIが正常に稼働しているのに、外部から `{"detail":"Not Found"}` が返る

**原因**: Nginxの設定ファイルが `/etc/nginx/sites-available/` にコピーされていない

#### 正しい設定反映手順

**ステップ1: server-configsリポジトリで設定を追加**

```bash
cd /path/to/server-configs

# Nginx設定を編集
nano production/sites-available/api.hey-watch.me

# 以下を追加
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
    add_header "Access-Control-Allow-Headers" "Content-Type, Authorization, X-API-Token";

    # OPTIONSリクエストの処理
    if ($request_method = "OPTIONS") {
        return 204;
    }
}

# コミット・プッシュ
git add production/sites-available/api.hey-watch.me
git commit -m "feat: Add {API Name} Nginx location"
git push origin main
```

**ステップ2: EC2で設定を反映**

```bash
ssh -i ~/watchme-key.pem ubuntu@{EC2_HOST}

# server-configsリポジトリを更新
cd /home/ubuntu/watchme-server-configs
git pull origin main

# ⚠️ 重要: /etc/nginx/ に手動でコピー
sudo cp production/sites-available/api.hey-watch.me /etc/nginx/sites-available/api.hey-watch.me

# 設定テスト
sudo nginx -t

# Nginx再読み込み
sudo systemctl reload nginx

exit
```

**ステップ3: 動作確認**

```bash
# 外部からヘルスチェック
curl https://api.hey-watch.me/{api-path}/health

# 成功すると以下のようなレスポンスが返る
# {"status":"healthy", ...}
```

#### なぜ自動でコピーされないのか？

- `watchme-server-configs` リポジトリは単なるバックアップ・バージョン管理用
- `/etc/nginx/sites-available/` は直接編集されることもあるため、自動同期していない
- 手動でコピーすることで、意図しない上書きを防ぐ

#### よくある間違い

**❌ 間違い**: `git pull` だけして終わり
```bash
cd /home/ubuntu/watchme-server-configs
git pull origin main
# ← これだけではNginxに反映されない！
```

**✅ 正解**: コピー + reload まで実行
```bash
cd /home/ubuntu/watchme-server-configs
git pull origin main
sudo cp production/sites-available/api.hey-watch.me /etc/nginx/sites-available/
sudo nginx -t
sudo systemctl reload nginx
```

#### 実際の例（Business API - 2026-01-10）

```bash
# Nginx設定が反映されず、404が返り続けた
curl https://api.hey-watch.me/business/health
# → {"detail":"Not Found"}

# EC2内部では正常に動作していた
ssh ubuntu@3.24.16.82 "curl http://localhost:8052/health"
# → {"status":"healthy", ...}

# 原因: Nginx設定ファイルがコピーされていなかった
ssh ubuntu@3.24.16.82 "grep -A 20 'Business API' /etc/nginx/sites-available/api.hey-watch.me"
# → (何も表示されない)

# 解決: 手動でコピー
ssh ubuntu@3.24.16.82 << 'ENDSSH'
  sudo cp /home/ubuntu/watchme-server-configs/production/sites-available/api.hey-watch.me /etc/nginx/sites-available/
  sudo nginx -t
  sudo systemctl reload nginx
ENDSSH

# 再確認 → 成功
curl https://api.hey-watch.me/business/health
# → {"status":"healthy", "service":"watchme-business-api", ...}
```

---

## 📋 起動方式の全体像（2025-11-21更新）

### 現状

**GitHub Actions方式（新標準）**: 9サービス稼働中
**systemd方式（移行期/保留）**: 3サービス
**Infrastructure（維持）**: watchme-network管理

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

**適用サービス（10個）:**

| サービス | ポート | 稼働状況 | コンテナ名 |
|---------|--------|---------|----------|
| Profiler API | 8051 | ✅ 正常（2025-11-21移行完了） | profiler-api |
| Aggregator API | 8050 | ✅ 正常 | aggregator-api |
| Behavior Features | 8017 | ✅ 正常（AST） | behavior-analysis-feature-extractor |
| Emotion Features | 8018 | ✅ 正常（Kushinada） | emotion-analysis-feature-extractor |
| Vibe Transcriber | 8013 | ✅ 正常（Groq Whisper） | vibe-analysis-transcriber |
| Vault API | 8000 | ✅ 正常 | watchme-vault-api |
| Admin | 9000 | ✅ 正常 | watchme-admin |
| Janitor | 8030 | ✅ 正常 | janitor-api |
| Avatar Uploader | 8014 | ✅ 正常 | watchme-avatar-uploader |
| Demo Generator | 8020 | ✅ 正常 | demo-generator-api |

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

**適用サービス（3個）:**

| サービス | ポート | 状態 | systemdサービス名 | 備考 |
|---------|--------|------|------------------|------|
| API Manager | 9001 | ✅ 稼働中 | watchme-api-manager.service | systemd管理 |
| Web Dashboard | 3000 | ✅ 稼働中 | watchme-web-app.service | systemd管理 |
| Infrastructure | - | ✅ 維持 | watchme-infrastructure.service | watchme-network管理（変更不要） |

**削除済みsystemdサービス（2025-12-02）:**
- `watchme-behavior-yamnet.service` → GitHub Actions方式に移行済み
- `watchme-vault-api.service` → GitHub Actions方式に移行済み

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

### Infrastructure サービスについて

**役割**: `watchme-network` Dockerネットワークの作成・管理
**維持理由**: EC2再起動時に自動的にネットワークを作成（全コンテナが依存）
**方針**: **このまま維持**（変更不要）

### 管理コマンド

```bash
# コンテナ確認
docker ps

# ログ確認
docker logs {container-name} --tail 100 -f

# 再起動
cd /home/ubuntu/{api-name} && ./run-prod.sh

# systemd確認（Infrastructure/API Manager/Web Dashboard のみ）
sudo systemctl status {service-name}
```

---
