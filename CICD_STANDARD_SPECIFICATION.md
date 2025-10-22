# WatchMe API CI/CD 標準仕様書

## 概要
全WatchMe APIで統一するCI/CDプロセスの標準仕様

## デプロイプロセスの全体像

### フロー概要
```
1. 開発者がコードをpush
   ↓
2. GitHub Actionsが起動
   ↓
3. Dockerイメージをビルド＆ECRへpush
   ↓
4. EC2サーバーへ環境変数を配置
   ↓
5. 既存コンテナを完全削除
   ↓
6. 新規コンテナを起動
   ↓
7. 動作確認
```

### 成功の鍵
- **ECR名の一貫性**: ECR関連の設定では同じECRリポジトリ名を使用（GitHubリポジトリ名とは異なる）
- **削除の完全性**: 既存コンテナを確実に削除してから新規起動
- **環境変数の正確性**: Secretsから.envへの値の伝播を保証

## ⚠️ CI/CD実装の前提条件

### 実装前の必須確認事項

#### ステップ1: ローカル動作確認
```bash
# Dockerイメージのクリーンビルドと動作確認
docker build --no-cache -f Dockerfile.prod -t test-image .
docker run --env-file .env.local test-image

# 動作確認できたらCI/CDへ進む
```

#### ステップ2: 既存環境のクリーンアップ
```bash
# EC2とECRの古いイメージを削除
ssh ubuntu@EC2_HOST 'docker system prune -a -f'
aws ecr batch-delete-image --repository-name REPO_NAME --image-ids imageTag=latest
```

#### ステップ3: ECRリポジトリ名の一貫性確認
```bash
# ECRリポジトリ名が統一されているか確認（GitHubリポジトリ名とは別）
# .github/workflows/deploy-to-ecr.ymlのECR_REPOSITORY値を確認
grep "ECR_REPOSITORY:" .github/workflows/deploy-to-ecr.yml
# docker-compose.prod.ymlのimage値を確認
grep "image:" docker-compose.prod.yml
# これらが同じECRリポジトリを指していることを確認
```

## 🔴 コンテナ管理の基本原則

### コンテナの一意性原則
- **原則**: 1つのコンテナ名は、システム全体で1つしか存在できない
- **問題**: 異なる方法（docker run、docker-compose、systemd）で起動されたコンテナが競合する
- **解決**: デプロイ前に、対象コンテナ名を持つすべてのコンテナを削除する

### コンテナ削除の3層アプローチ
デプロイ時は以下の順序ですべての可能性をカバー：

1. **名前ベースの削除** - docker-compose管理外のコンテナも含めて削除
2. **プロジェクトベースの削除** - docker-composeで管理されているコンテナを削除  
3. **確認と強制削除** - それでも残っているコンテナを強制削除

### 重要な考慮事項
- コンテナ名とプロジェクト名の関係性を理解する
- エラーを隠蔽せず、適切に処理する
- 削除の成功を確認してから次のステップへ進む

## CI/CDの基本原則

### 🎯 CI/CDの価値
- **再現性**: 誰がやっても同じように、自動で、ミスなくデプロイが完了
- **自動化**: 手動作業は初回セットアップの1回のみ
- **追跡可能性**: すべての変更がGitで管理され、履歴が残る
- **整合性**: すべてのコンポーネントが協調して動作

### ⚠️ 避けるべきアンチパターン
- ❌ デプロイのたびにSSHでサーバーに入って手動作業
- ❌ デプロイスクリプトをサーバー上で直接編集
- ❌ 環境変数を手動で設定・更新
- ❌ 「動いているものには触らない」という考え方
- ❌ 個別最適化による全体の不整合

### ✅ 正しいプロセス
1. **初回セットアップ**: EC2上でディレクトリ作成（1回のみ）
2. **コード管理**: すべての設定ファイルをGitで管理
3. **自動デプロイ**: git pushだけですべてが更新される
4. **全体整合性**: すべてのコンポーネントが一貫したルールで動作

## 必要なGitHub Secrets設定
```
AWS_ACCESS_KEY_ID       # AWS認証
AWS_SECRET_ACCESS_KEY   # AWS認証  
EC2_HOST                # デプロイ先EC2
EC2_SSH_PRIVATE_KEY     # SSH接続用
EC2_USER                # SSHユーザー
SUPABASE_URL            # Supabase URL
SUPABASE_KEY            # Supabase APIキー
```

## ディレクトリ構成
```
/home/ubuntu/{api-name}/
├── .env                    # 環境変数ファイル（GitHub Actionsが作成）
├── docker-compose.prod.yml # 本番用Docker Compose設定
├── run-prod.sh            # デプロイスクリプト
└── .github/
    └── workflows/
        └── deploy-to-ecr.yml # CI/CDワークフロー
```

## 0. 初回セットアップ（1回限りの手動作業）

### ⚠️ 重要: CI/CD実装前の必須作業

新しいAPIのCI/CDを実装する際は、**必ず以下の順序で作業を実施してください**。

#### ステップ0: ECRリポジトリの作成

```bash
# AWS CLIでECRリポジトリを作成
aws ecr create-repository \
  --repository-name {ecr-repository-name} \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true

# 例: watchme-emotion-analysis-aggregator
```

**注意**: ECRリポジトリが存在しないとDockerイメージのプッシュが失敗します。

#### ステップ1: EC2サーバーの準備

```bash
# 1. EC2に接続
ssh -i ~/watchme-key.pem ubuntu@EC2_HOST

# 2. アプリケーション用ディレクトリ作成（重要！）
mkdir -p /home/ubuntu/{api-directory-name}

# 3. Dockerネットワークの確認/作成
docker network create watchme-network 2>/dev/null || true

# 4. ディレクトリが作成されたことを確認
ls -la /home/ubuntu/{api-directory-name}
```

**注意**: ディレクトリが存在しないとGitHub ActionsのSCPコマンドが失敗します。

#### ステップ2: GitHub Secretsの設定

以下のSecretsがリポジトリに設定されていることを確認：
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `EC2_SSH_PRIVATE_KEY`
- `EC2_HOST`
- `EC2_USER`
- `SUPABASE_URL`
- `SUPABASE_KEY`

### 初回セットアップのチェックリスト

- [ ] ECRリポジトリが作成されている
- [ ] EC2上にアプリケーションディレクトリが作成されている
- [ ] GitHub Secretsがすべて設定されている
- [ ] Dockerネットワーク `watchme-network` が存在する
- [ ] GitHub Actionsワークフローファイルが作成されている

**これらがすべて完了してから、初めてGitHub Actionsを実行してください。**

## 1. GitHub Actionsワークフロー仕様

### 必須ステップ（deploy-to-ec2ジョブ）
```yaml
# ステップ1: SSHエージェントのセットアップ
# ステップ2: コードのチェックアウト
# ステップ3: Known Hostsの追加
# ステップ4: EC2にディレクトリ作成（初回デプロイ時のみ必要だが、べき等性のため常に実行推奨）
# ステップ5: docker-compose.prod.ymlとrun-prod.shをEC2にコピー
# ステップ6: EC2に.envファイルを作成/更新
# ステップ7: docker-composeでコンテナ再起動
```

### ステップ4: ディレクトリ作成（重要！）

初回デプロイ時にディレクトリが存在しないとSCPが失敗するため、以下のステップを**必ず追加**してください：

```yaml
# ステップ4: EC2にディレクトリを作成（存在確認＆作成）
- name: Create application directory on EC2 if not exists
  env:
    EC2_HOST: ${{ secrets.EC2_HOST }}
    EC2_USER: ${{ secrets.EC2_USER }}
  run: |
    echo "📁 Creating application directory on EC2..."
    ssh ${EC2_USER}@${EC2_HOST} "mkdir -p /home/ubuntu/{api-directory-name}"
    echo "✅ Directory created/verified"
```

**このステップを追加する位置**: 「Known Hostsの追加」の直後、「Update configuration files on EC2」の直前

### ⚠️ 重要：必須要件チェックリスト

CI/CDを正しく動作させるために、以下の3つの要件を必ず満たすこと：

#### 1. クリーンビルドの保証
```yaml
# CI/CDワークフローで必須
docker buildx build \
  --platform linux/arm64 \
  --no-cache \              # ← 必須：キャッシュを無効化
  --push
```

#### 2. リポジトリ名の完全一致
以下の4箇所で同一のECRリポジトリ名を使用すること：
- `.github/workflows/deploy-to-ecr.yml` のECR_REPOSITORY
- `docker-compose.prod.yml` のimage
- `deploy-ecr.sh` のECR_REPOSITORY 
- `run-prod.sh` のECR_REPOSITORY

```bash
# 検証コマンド：すべて同じ名前が表示されること
grep -h "ECR_REPOSITORY\|image:" *.yml *.sh .github/workflows/*.yml | grep -o "watchme-api-[a-z-]*" | sort -u
```

#### 3. 環境変数の正しい展開
GitHub Secretsの値が確実にEC2に渡されること：
```yaml
# 推奨：echoコマンドで確実に展開
echo "SUPABASE_URL=${SUPABASE_URL}" > .env
echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
```

### Dockerイメージビルドの標準テンプレート

```yaml
- name: Delete old images from ECR (optional but recommended)
  run: |
    # 古いlatestタグを削除（エラーは無視）
    aws ecr batch-delete-image \
      --region ${{ env.AWS_REGION }} \
      --repository-name ${{ env.ECR_REPOSITORY }} \
      --image-ids imageTag=latest || true

- name: Build, tag, and push image to Amazon ECR
  env:
    ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
    IMAGE_TAG: ${{ github.sha }}
  run: |
    # 必ず --no-cache オプションを使用
    docker buildx build \
      --platform linux/arm64 \
      --no-cache \
      --push \
      -f Dockerfile.prod \
      -t $ECR_REGISTRY/${{ env.ECR_REPOSITORY }}:$IMAGE_TAG \
      -t $ECR_REGISTRY/${{ env.ECR_REPOSITORY }}:latest \
      .
```

### 環境変数作成ステップ（重要）

#### ⚠️ 環境変数の展開に関する重要な理解

**CI/CDにおける環境変数は3つの段階で扱われます：**

1. **GitHub Actions環境** - `${{ secrets.VARIABLE }}` として取得
2. **シェルスクリプト環境** - `${VARIABLE}` として参照  
3. **リモートサーバー環境** - 実際の値として保存

**推奨方法：echoコマンドを使用**
- シンプルで確実
- インデントの問題を回避
- 変数展開が明確

```yaml
- name: Create/Update .env file on EC2
  env:
    EC2_HOST: ${{ secrets.EC2_HOST }}
    EC2_USER: ${{ secrets.EC2_USER }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: |
    ssh ${EC2_USER}@${EC2_HOST} << 'ENDSSH'
      cd /home/ubuntu/{api-name}
      
      # echoコマンドで確実に環境変数を作成
      echo "SUPABASE_URL=${SUPABASE_URL}" > .env
      echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
    ENDSSH
```

**注意点:**
- SSH内で変数を使用する場合、適切な展開タイミングを意識
- エラー時の値確認のため、適切なログ出力を検討

#### ⚠️ アプリケーションが要求する環境変数の確認

**重要: .envファイルに含める環境変数は、アプリケーションコードによって異なります**

各APIが起動時に必要とする環境変数を正確に把握し、すべて.envに含める必要があります。

**チェック方法:**
```bash
# アプリケーションコードで環境変数のチェックを検索
grep -r "os.getenv\|os.environ" main.py app.py
grep -r "raise.*環境変数\|raise.*設定されていません" main.py app.py
```

**よくある必須環境変数のパターン:**
- **Supabase系API**: `SUPABASE_URL`, `SUPABASE_KEY`
- **AWS S3/Bedrockを使用**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- **OpenAI API**: `OPENAI_API_KEY`
- **カスタムサービス**: API固有の環境変数

**例: AWS認証情報が必要な場合**
```yaml
- name: Create/Update .env file on EC2
  env:
    EC2_HOST: ${{ secrets.EC2_HOST }}
    EC2_USER: ${{ secrets.EC2_USER }}
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: |
    ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
      cd /home/ubuntu/{api-name}
      echo "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}" > .env
      echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}" >> .env
      echo "SUPABASE_URL=${SUPABASE_URL}" >> .env
      echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
    ENDSSH
```

**GitHub Secretsと.envファイルの関係:**
- **GitHub Secrets**: GitHub Actions実行中のみ利用可能
- **.envファイル**: EC2上のDockerコンテナ内で利用可能
- **重要**: GitHub Secretsはコンテナ内に自動的には渡されない
- **必須**: 必要な環境変数をすべて.envファイルに明示的に書き込む

**デバッグ時のヒント:**
起動エラーが発生した場合、コンテナログで環境変数エラーを確認：
```bash
docker logs container-name --tail 100 | grep -i "environment\|env\|設定されていません"
```

### デプロイスクリプトの自動更新

スクリプトを自動更新する場合の考慮事項：
- コードとイメージの整合性を保つ
- チェックアウトのタイミングを適切に設定
- 古いイメージと新しいスクリプトの不整合を防ぐ


## 2. run-prod.sh仕様

### 必須要件
- docker-composeを使用（docker run直接実行は禁止）
- カレントディレクトリの.envを参照
- ハードコードされた認証情報は含めない
- **既存コンテナの完全削除を保証**

### デプロイフローの原則
```
1. ECRから最新イメージを取得
2. 既存コンテナの完全削除（3層アプローチ）
3. 新規コンテナの起動
4. 起動確認
```

### コンテナ削除の実装アプローチ

#### 段階的削除の実装パターン
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

### 削除処理の重要ポイント
- **検索してから削除**: コンテナの存在を確認してから削除
- **ログ出力**: 各段階で何が行われているか明確にする
- **エラー耐性**: 一部の削除が失敗しても処理を継続
- **確実性**: 複数の方法で削除を試みる

### 起動確認の必要性
- コンテナが正常に起動したことを確認
- ヘルスチェックエンドポイントの活用
- 起動失敗時のログ出力

## 3. Dockerfile仕様

### 必須要件

#### 空ディレクトリ問題の対処

**問題**: Gitは空ディレクトリを追跡しないため、Dockerビルド時に必要なディレクトリが存在しない可能性がある

**症状**: 
```
RuntimeError: Directory 'static' does not exist
```

**解決策**: Dockerfile内で必要なディレクトリを明示的に作成

```dockerfile
# アプリケーションコードをコピー
COPY . .

# 必要なディレクトリを作成（FastAPIでstatic/templatesを使う場合）
RUN mkdir -p /app/static /app/templates || true
```

**ポイント**:
- `mkdir -p`で再帰的にディレクトリを作成
- `|| true`で既に存在する場合のエラーを無視
- FastAPIで`StaticFiles`や`Jinja2Templates`を使う場合は必須

## 4. docker-compose.prod.yml仕様

### 必須設定要素
- **image**: ECRのフルパス（レジストリURL/リポジトリ名:タグ）
- **container_name**: 一意のコンテナ名（システム全体で重複不可）
- **env_file**: 環境変数ファイルの参照
- **ports**: ポートマッピング（セキュリティのため127.0.0.1を指定）
- **networks**: 共通ネットワークへの参加

### 設定の整合性
- imageのリポジトリ名は全設定ファイルで統一
- container_nameはデプロイスクリプトと一致
- networksは事前に作成済みのものを使用

## 適用対象API一覧

| API名 | ディレクトリ | ポート | 現状 | 要修正 |
|------|------------|--------|------|--------|
| api-sed-aggregator | /home/ubuntu/api-sed-aggregator | 8010 | ✅ 完全対応 | - |
| api_ast | /home/ubuntu/api_ast | 8017 | ハードコード方式 | 要修正 |
| opensmile-aggregator | /home/ubuntu/opensmile-aggregator | 8012 | 未確認 | 要確認 |
| api_gen_prompt_mood_chart | /home/ubuntu/watchme-api-vibe-aggregator | 8009 | 正常（見本） | デプロイスクリプト自動更新を追加推奨 |

## 修正手順

### 各APIで必要な作業
1. `.github/workflows/deploy-to-ecr.yml`に環境変数作成ステップを追加
2. `run-prod.sh`をdocker-compose方式に統一
3. `docker-compose.prod.yml`の`env_file`設定を確認
4. ハードコードされた認証情報を削除

## 成功判定基準
- GitHub Actions経由でデプロイ成功
- 環境変数が正しく設定される
- 「Invalid API key」エラーが発生しない
- 全APIが同じパターンで動作

## トラブルシューティングチェックリスト

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
  --repository-name watchme-api-sed-aggregator \
  --region ap-southeast-2 \
  --query 'sort_by(imageDetails,& imagePushedAt)[-1].[imageTags[0],imagePushedAt]' \
  --output text
```

#### 3. 必須ステップの実装確認
```bash
# ECR削除ステップがあるか
grep -n "Delete old images from ECR" .github/workflows/deploy-to-ecr.yml

# docker system pruneが使われているか
grep -n "docker system prune" .github/workflows/deploy-to-ecr.yml

# リポジトリ名が統一されているか
grep -h "ECR_REPOSITORY\|image:" *.yml *.sh .github/workflows/*.yml | grep -o "watchme-api-[a-z-]*" | sort -u
```

## デバッグガイド

### コンテナ競合エラーの診断と解決

#### 症状の確認
```
Error: Conflict. The container name "/container-name" is already in use
```

#### 診断手順

##### 1. 既存コンテナの確認
```bash
# EC2サーバー上で実行
docker ps -a | grep container-name
```

##### 2. コンテナの起動方法を特定
- docker-compose管理: `docker-compose ps`で表示される
- docker run起動: docker-composeで管理されていない
- systemd管理: `systemctl status container-name`で確認

##### 3. 解決方法
```bash
# 既存コンテナを完全に削除
docker stop container-name 2>/dev/null || true
docker rm -f container-name 2>/dev/null || true
docker-compose down --remove-orphans

# 新規起動
docker-compose up -d
```

### 設定の一貫性確認

#### ⚠️ 重要：リポジトリ名の違いを理解する

**GitHubリポジトリとECRリポジトリは別物：**
- **GitHubリポジトリ名**: 例 `admin`, `api-sed-aggregator`
- **ECRリポジトリ名**: 例 `watchme-admin`, `watchme-api-sed-aggregator`
- これらは意図的に異なる名前を使用

#### ECRリポジトリ名の一貫性チェック
```bash
# CI/CD内でECRリポジトリ名が一貫しているか確認
# （GitHubリポジトリ名ではなく、ECRリポジトリ名のみをチェック）
grep "ECR_REPOSITORY" .github/workflows/*.yml
grep "image:" docker-compose.prod.yml
# これらが同じECRリポジトリを指していることを確認
```

#### よくあるミス
- ❌ GitHubリポジトリ名をECRリポジトリ名として使用
- ❌ ECR_REPOSITORYとdocker-compose.ymlのimageが不一致
- ✅ 正解: ECR関連の設定はすべて同じECRリポジトリ名を使用

#### 環境変数の確認
```bash
# .envファイルの内容確認（値が正しく展開されているか）
cat .env | grep -E "SUPABASE|AWS"
# 変数記号($)が残っていないことを確認
```

### 問題パターンと対処法

| 症状 | 確認コマンド | 対処法 |
|-----|------------|-------|
| デプロイ成功するが動作しない | `grep -o "watchme-api-[a-z-]*" *.yml *.sh \| sort -u` | リポジトリ名を統一 |
| 環境変数エラー | `cat .env \| grep "\$"` | echoコマンドで環境変数作成 |
| 古いコードが動く | `docker images --no-trunc` | --no-cacheオプション追加 |
| 手動では動くがCI/CDで壊れる | 上記すべて | 設定ファイルの完全一致を確認 |
| コンテナ起動直後にクラッシュ（環境変数不足） | `docker logs container-name \| grep "設定されていません"` | アプリが要求する全環境変数を.envに追加 |

### コンテナ起動直後のクラッシュ（環境変数不足エラー）

#### 症状
```
ValueError: AWS_ACCESS_KEY_IDおよびAWS_SECRET_ACCESS_KEYが設定されていません
RuntimeError: 環境変数XXXXが設定されていません
```

#### 診断手順

##### 1. コンテナログの確認
```bash
# EC2サーバー上で実行
docker logs container-name --tail 100
```

##### 2. アプリケーションコードで必須環境変数を確認
```bash
# ローカル開発環境で実行
cd /path/to/api
grep -rn "os.getenv\|os.environ" main.py app.py
grep -rn "raise.*環境変数\|raise.*設定されていません" *.py
```

##### 3. 現在の.envファイルを確認
```bash
# EC2サーバー上で実行
cat /home/ubuntu/{api-name}/.env
```

#### 解決方法

##### ステップ1: 不足している環境変数を特定
アプリケーションコードを確認し、`os.getenv("VARIABLE_NAME")`で取得している変数をすべてリストアップ

##### ステップ2: GitHub Secretsに値が登録されているか確認
- リポジトリの Settings > Secrets and variables > Actions で確認
- 不足していれば追加

##### ステップ3: deploy-to-ecr.ymlを修正
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
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: |
    ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
      cd /home/ubuntu/{api-name}
      echo "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}" > .env
      echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}" >> .env
      echo "SUPABASE_URL=${SUPABASE_URL}" >> .env
      echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
    ENDSSH
```

##### ステップ4: コミット＆プッシュ
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

## セキュリティ考慮事項
- 認証情報はGitHub Secretsでのみ管理
- .envファイルはgitignoreに含める
- Dockerイメージに認証情報を含めない
- ハードコードは完全に排除
- ログに認証情報を出力しない（デバッグ時も注意）