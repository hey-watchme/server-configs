# WatchMe API CI/CD 標準仕様書

**目的**: 全WatchMe APIで統一されたCI/CDプロセスを定義し、再現性・自動化・整合性を保証する

---

## このドキュメントの使い方

### 📖 読者別ガイド

| 状況 | 読むべきセクション |
|-----|------------------|
| **新しいAPIのCI/CD実装** | [実装ガイド](#実装ガイド新規api向け) を順番に読む |
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

```
/your-api-repository/
├── .github/
│   └── workflows/
│       └── deploy-to-ecr.yml    # CI/CDワークフロー
├── docker-compose.prod.yml      # 本番用Docker Compose設定
├── run-prod.sh                  # デプロイスクリプト
├── Dockerfile                   # Dockerイメージ定義
└── .env.example                 # 環境変数のサンプル（.envは.gitignore）
```

#### 3-2. `.github/workflows/deploy-to-ecr.yml` の作成

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

#### 3-3. `docker-compose.prod.yml` の作成

```yaml
version: '3.8'

services:
  api:
    image: 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-{api-name}:latest  # ★ECR_REPOSITORYと一致
    container_name: {unique-container-name}  # ★システム全体で一意の名前
    ports:
      - "127.0.0.1:{port}:{port}"
    env_file:
      - .env  # ★環境変数ファイルを参照
    networks:
      - watchme-network
    restart: unless-stopped
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

#### 3-4. `run-prod.sh` の作成

テンプレートは [run-prod.sh仕様](#run-prodsh仕様) を参照。

**必須要件:**
- docker-composeを使用
- .envファイルを参照
- 既存コンテナの完全削除
- ヘルスチェック実施

### ステップ4: デプロイ実行

```bash
# すべてのファイルをコミット＆プッシュ
git add .github/workflows/deploy-to-ecr.yml docker-compose.prod.yml run-prod.sh Dockerfile
git commit -m "Add CI/CD configuration"
git push origin main

# GitHub Actionsの実行を確認
# https://github.com/{organization}/{repository}/actions
```

### ステップ5: 動作確認

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

#### 必須ステップ（deploy-to-ec2ジョブ）

```yaml
# ステップ1: SSHエージェントのセットアップ
# ステップ2: コードのチェックアウト
# ステップ3: Known Hostsの追加
# ステップ4: EC2にディレクトリ作成（べき等性のため常に実行）
# ステップ5: docker-compose.prod.ymlとrun-prod.shをEC2にコピー
# ステップ6: EC2に.envファイルを作成/更新
# ステップ7: docker-composeでコンテナ再起動
```

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

### Dockerfile仕様

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

| API名 | ディレクトリ | ポート | 現状 |
|------|------------|--------|------|
| api-sed-aggregator | /home/ubuntu/api-sed-aggregator | 8010 | ✅ 完全対応 |
| api_ast | /home/ubuntu/api_ast | 8017 | ⚠️ 要修正 |
| opensmile-aggregator | /home/ubuntu/opensmile-aggregator | 8012 | ⚠️ 要確認 |
| api_gen_prompt_mood_chart | /home/ubuntu/watchme-api-vibe-aggregator | 8009 | ✅ 正常 |
| emotion-analysis-feature-extractor-v3 | /home/ubuntu/emotion-analysis-feature-extractor-v3 | 8018 | ✅ 正常 |
