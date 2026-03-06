# WatchMe API CI/CD 標準仕様書

Status: Active  
Source of truth: API リポジトリ側の CI/CD 方式

**目的**: 全 WatchMe API で統一された CI/CD プロセスを定義

---

## 📖 クイックナビゲーション

| 目的 | セクション |
|-----|----------|
| **環境変数管理** | **[環境変数管理の原則](#-環境変数管理の原則)** |
| 新規API実装 | [実装ガイド](#実装ガイド新規api向け) |
| 大規模AIモデル | [AIモデル対応](#-重要大きなaiモデルを使用する場合の必須対応) |
| エラー対処 | [トラブルシューティング](#トラブルシューティング) |
| 現状確認 | [起動方式の全体像](#-現在の起動方法管理方法の全体像2025-11-21更新) |

---

## 🔐 環境変数管理の原則

**重要: この原則は全WatchMe APIで統一されています。**

### ローカル開発環境

```yaml
# docker-compose.local.yml（ローカル専用）
services:
  api:
    env_file:
      - .env  # ← .envファイルから読み込み
```

- ✅ `.env` ファイルを使用する
- ✅ `docker-compose.local.yml` で `env_file` を参照
- ✅ `.gitignore` に `.env` を追加（Git管理外）

### 本番環境（CI/CD）

```yaml
# docker-compose.prod.yml（本番専用）
services:
  api:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}  # ← 明示的に展開
      - SUPABASE_URL=${SUPABASE_URL}
```

- ✅ **GitHub Actions Secrets を唯一の source of truth とする**
- ✅ `docker-compose.prod.yml` では `environment: ${VAR}` 形式で明示的に展開
- ❌ **本番環境に `.env` ファイルが存在する構成は禁止**
  - GitHub Actions が `.env` を動的生成するため、存在はするが Source of Truth ではない

### 環境変数の流れ（本番）

```
GitHub Secrets
  ↓（GitHub Actions）
EC2 の .env ファイルに注入
  ↓（docker-compose）
${VAR} 形式で展開
  ↓
コンテナ環境変数
```

### 新規環境変数の追加手順

1. **GitHub Secrets に追加**
   ```bash
   gh secret set NEW_VAR --repo hey-watchme/your-api --body "value"
   ```

2. **GitHub Actions ワークフローに追加**
   ```yaml
   # .github/workflows/deploy-to-ecr.yml
   env:
     NEW_VAR: ${{ secrets.NEW_VAR }}

   run: |
     echo "NEW_VAR=${NEW_VAR}" >> .env
   ```

3. **docker-compose.prod.yml に追加**
   ```yaml
   environment:
     - NEW_VAR=${NEW_VAR}
   ```

**3箇所すべてを更新しないと動作しません。**

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

**重要: WatchMeプロジェクトでは、全てのSecretsはOrganizationレベルで設定されています。**

以下のSecretsは **hey-watchme Organization** で一元管理されており、全リポジトリで自動的に利用可能です：

```
AWS_ACCESS_KEY_ID       # AWS認証（Organization設定済み）
AWS_SECRET_ACCESS_KEY   # AWS認証（Organization設定済み）
EC2_SSH_PRIVATE_KEY     # SSH接続用秘密鍵（Organization設定済み）
SUPABASE_URL            # Supabase プロジェクトURL（Organization設定済み）
SUPABASE_KEY            # Supabase サービスロールキー（Organization設定済み）
OPENAI_API_KEY          # OpenAI APIキー（Organization設定済み）
GROQ_API_KEY            # Groq APIキー（Organization設定済み）
```

**確認方法:**
- リポジトリの Settings > Secrets and variables > Actions
- 下部の **"Organization secrets"** セクションに上記Secretsが表示されていればOK
- `gh secret list` コマンドはリポジトリレベルのSecretsのみ表示するため、Organization Secretsは表示されない

**⚠️ 重要: Privateリポジトリの場合、Organization SecretsのRepository accessに明示的に追加が必要**

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
| **CORSエラー（プリフライト失敗）** | ❌ NginxでOPTIONSを直接204返却、❌ FastAPIでワイルドカード使用 | [CORS問題の診断と修正](#cors問題の診断と修正) 参照 |

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

**症状**: `ERROR: ResolutionImpossible` が発生

**確認すべき点**:
1. PyPIに指定したバージョンが存在するか（例: `supabase==2.12.2` は存在しない。2.12.0までしかない）
2. エラーログの依存関係ツリーを読む（`realtime 2.27.1 depends on pydantic>=2.11.7`）
3. 連鎖的に関連パッケージも更新する（supabase → pydantic → fastapi/uvicorn）
4. 最新の安定版を使う（古いバージョンは互換性問題が多い）

**実例**: Business API (2026-01-10)
- `supabase==2.3.4` + `httpx==0.27.0` → 競合
- `httpx==0.25.2` → `TypeError: proxy`
- `supabase==2.12.2` → PyPIに存在しない
- `supabase==2.27.1` → `pydantic>=2.11.7` 要求 → fastapi/uvicorn も更新

---

### 初回デプロイの事前準備（必須）

**重要**: GitHub Actionsだけでは初回デプロイは完了しない。以下を事前に実行：

```bash
# 1. ECRリポジトリ作成
aws ecr create-repository --repository-name watchme-{api-name} --region ap-southeast-2

# 2. EC2セットアップ
ssh ubuntu@{EC2_HOST}
mkdir -p /home/ubuntu/{api-directory-name}
docker network create watchme-network 2>/dev/null || true
```

---

### Nginx設定の反映方法

**症状**: APIは稼働しているが外部から404

**原因**: `/etc/nginx/sites-available/` にコピーされていない

**正しい手順**:
```bash
# server-configsで編集・プッシュ後
ssh ubuntu@{EC2_HOST}
cd /home/ubuntu/watchme-server-configs
git pull
sudo cp production/sites-available/api.hey-watch.me /etc/nginx/sites-available/
sudo nginx -t && sudo systemctl reload nginx
```

**よくある間違い**: `git pull` だけして終わり → Nginxに反映されない

---

### CORS問題の診断と修正

**診断コマンド**:
```bash
# OPTIONSリクエストテスト
curl -X OPTIONS https://api.hey-watch.me/{path} -H "Origin: https://{domain}" -i
# → access-control-allow-origin ヘッダーがあるか確認

# Nginx設定確認
grep "return 204" /etc/nginx/sites-available/api.hey-watch.me

# FastAPI設定確認
grep "allow_origins" backend/app.py
```

**修正観点**:
1. **NginxでOPTIONSを直接204返却している場合** → 削除（FastAPIに任せる）
2. **FastAPIでワイルドカード使用** → 具体的なドメインに変更
3. **Cloudflare Proxy有効** → DNS only（グレー雲）に変更

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
