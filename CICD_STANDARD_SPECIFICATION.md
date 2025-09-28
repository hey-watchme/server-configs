# WatchMe API CI/CD 標準仕様書

## 概要
全WatchMe APIで統一するCI/CDプロセスの標準仕様

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

#### ステップ3: 設定の一貫性確認
```bash
# リポジトリ名の統一確認（最重要）
grep -h "ECR_REPOSITORY\|image:" *.yml *.sh .github/workflows/*.yml | grep -o "watchme-api-[a-z-]*" | sort -u
# 出力が1行だけであることを確認
```

## CI/CDの基本原則

### 🎯 CI/CDの価値
- **再現性**: 誰がやっても同じように、自動で、ミスなくデプロイが完了
- **自動化**: 手動作業は初回セットアップの1回のみ
- **追跡可能性**: すべての変更がGitで管理され、履歴が残る

### ⚠️ 避けるべきアンチパターン
- ❌ デプロイのたびにSSHでサーバーに入って手動作業
- ❌ デプロイスクリプトをサーバー上で直接編集
- ❌ 環境変数を手動で設定・更新
- ❌ 「動いているものには触らない」という考え方

### ✅ 正しいプロセス
1. **初回セットアップ**: EC2上でディレクトリ作成（1回のみ）
2. **コード管理**: すべての設定ファイルをGitで管理
3. **自動デプロイ**: git pushだけですべてが更新される

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

### EC2サーバーの準備
```bash
# 1. EC2に接続
ssh -i ~/watchme-key.pem ubuntu@EC2_HOST

# 2. アプリケーション用ディレクトリ作成
mkdir -p /home/ubuntu/{api-name}

# 3. Dockerネットワークの確認/作成
docker network create watchme-network 2>/dev/null || true

# 4. 初回のみ: 必要なファイルを配置
# ※ 以降はCI/CDで自動更新される
```

## 1. GitHub Actionsワークフロー仕様

### 必須ステップ
```yaml
# ステップ1: 古いDockerイメージを削除（クリーンビルドのため）
# ステップ2: Dockerイメージをクリーンビルド（--no-cache必須）
# ステップ3: ECRにDockerイメージをプッシュ
# ステップ4: EC2に.envファイルを作成/更新
# ステップ5: docker-composeでコンテナ再起動
```

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

**変数展開のメカニズム：**
- シェルスクリプトでは、変数の展開タイミングをコントロールすることが重要
- ヒアドキュメントの区切り文字をクォートすると、変数は展開されずに文字列として扱われる
- SSH経由でリモートサーバーに値を渡す場合、適切な展開タイミングの制御が必要
- **重要**: ヒアドキュメントのインデントに注意！インデントされたEOFは認識されません

```yaml
- name: Create/Update .env file on EC2
  env:
    EC2_HOST: ${{ secrets.EC2_HOST }}
    EC2_USER: ${{ secrets.EC2_USER }}
    SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
    SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
  run: |
    ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
      cd /home/ubuntu/{api-name}
      
      # 方法1: echoコマンドで直接書き込み（推奨）
      echo "SUPABASE_URL=${SUPABASE_URL}" > .env
      echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
      
      # 方法2: ヒアドキュメントを使用（インデントに注意）
      # cat > .env << EOF
      # SUPABASE_URL=${SUPABASE_URL}
      # SUPABASE_KEY=${SUPABASE_KEY}
      # EOF
    ENDSSH

### デプロイスクリプトの自動更新（オプション）

**注意：** デプロイスクリプトを自動更新する場合は、`deploy`ジョブでコードをチェックアウトする必要があります。
`deploy-to-ec2`ジョブでのみチェックアウトすると、古いイメージと新しいスクリプトの不整合が発生します。

```yaml
# ❌ 間違い：deploy-to-ec2ジョブでのみチェックアウト
deploy-to-ec2:
  steps:
    - uses: actions/checkout@v4  # ここでチェックアウトは遅い
    - name: Update scripts...

# ✅ 正解：deployジョブでもチェックアウト
deploy:
  steps:
    - uses: actions/checkout@v4  # 最初にチェックアウト
    - name: Build image...       # 最新コードでビルド
```

**⚠️ よくある間違い:**
```yaml
# ❌ 間違い: インデントされたEOFは終了マーカーとして認識されない
cat > .env << EOF
  SUPABASE_URL=${SUPABASE_URL}
  SUPABASE_KEY=${SUPABASE_KEY}
  EOF  # <- インデントされているため認識されない

# ✅ 正解: echoコマンドを使用（推奨）
echo "SUPABASE_URL=${SUPABASE_URL}" > .env
echo "SUPABASE_KEY=${SUPABASE_KEY}" >> .env
```

### ⚠️ YAMLとヒアドキュメントの罠（2025年9月29日追記）

**問題：** GitHub ActionsのYAML内でヒアドキュメントを使用する際、YAMLのインデントルールとシェルのヒアドキュメントルールが衝突する

**症状：** 
- `You have an error in your yaml syntax on line XXX` エラーが繰り返し発生
- インデントを修正しても別のエラーが発生する無限ループ

**原因：**
1. YAMLルール: `run: |`ブロック内のすべての行は同じインデントが必要
2. シェルルール: ヒアドキュメントの終了文字は行頭にある必要がある（と思われがち）

**解決策：YAMLブロック内では終了文字もインデントする**
```yaml
run: |
  ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
    cd /home/ubuntu/api-name
    echo "KEY=${VALUE}" > .env
  ENDSSH  # ← YAMLブロックに合わせてインデント（8スペース）
```

**重要な学習：**
- GitHub ActionsのYAML内では、ヒアドキュメントの終了文字も**YAMLブロックのインデントに合わせる**
- これは通常のシェルスクリプトとは異なる動作
- 混乱を避けたい場合は、echoコマンドの直接使用を推奨

**重要な原則：**
- 環境変数の値をリモートサーバーに渡す際は、変数展開が正しく行われることを確認
- セキュリティを保ちながら、値が正しく伝播することを両立させる
- デバッグ時は、変数が展開されているか、文字列として扱われているかを必ず確認

## 2. run-prod.sh仕様

### 必須要件
- docker-composeを使用（docker run直接実行は禁止）
- カレントディレクトリの.envを参照
- ハードコードされた認証情報は含めない

### 標準テンプレート
```bash
#!/bin/bash
set -e

# ECRから最新イメージをプル
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin ${ECR_REGISTRY}
docker pull ${ECR_REGISTRY}/${ECR_REPOSITORY}:latest

# Docker Composeで再起動
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# ヘルスチェック
sleep 5
curl -f http://localhost:{PORT}/health
```

## 3. docker-compose.prod.yml仕様

### 必須設定
```yaml
services:
  api:
    image: {ECR_IMAGE_URL}
    container_name: {container-name}
    env_file:
      - .env  # カレントディレクトリの.envを参照
    ports:
      - "127.0.0.1:{PORT}:{PORT}"
    networks:
      - watchme-network
```

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

## トラブルシューティングチェックリスト（2025年9月29日追加）

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

### 問題診断の体系的アプローチ

#### レベル1: 基本診断（5分で確認）
```bash
# 1. 設定の一貫性
grep -h "ECR_REPOSITORY\|image:" *.yml *.sh .github/workflows/*.yml | grep -o "watchme-api-[a-z-]*" | sort -u
# → 出力が1行のみであることを確認

# 2. 環境変数の状態
ssh ubuntu@EC2_HOST 'cat /home/ubuntu/api-name/.env | grep -c "=\$"'
# → 0が返ることを確認（変数展開されていない$が残っていない）

# 3. 実行中のイメージ
ssh ubuntu@EC2_HOST 'docker ps --format "table {{.Image}}\t{{.Status}}"'
# → 正しいECRリポジトリのイメージが動いていることを確認
```

#### レベル2: 詳細診断（問題が解決しない場合）
```bash
# イメージの詳細確認
ssh ubuntu@EC2_HOST 'docker inspect $(docker ps -q) | jq ".[0].Config.Env"'

# コンテナ内のコード確認
ssh ubuntu@EC2_HOST 'docker exec $(docker ps -q) cat /app/main.py | head -20'

# 最新ログの確認
ssh ubuntu@EC2_HOST 'docker logs $(docker ps -q) --tail 50'
```

#### レベル3: 完全リセット（最終手段）
```bash
# すべてをクリーンにして再構築
ssh ubuntu@EC2_HOST 'docker-compose down && docker system prune -a -f'
aws ecr batch-delete-image --repository-name REPO_NAME --image-ids imageTag=latest
# その後、CI/CDを再実行
```

### 問題パターンと対処法

| 症状 | 確認コマンド | 対処法 |
|-----|------------|-------|
| デプロイ成功するが動作しない | `grep -o "watchme-api-[a-z-]*" *.yml *.sh \| sort -u` | リポジトリ名を統一 |
| 環境変数エラー | `cat .env \| grep "\$"` | echoコマンドで環境変数作成 |
| 古いコードが動く | `docker images --no-trunc` | --no-cacheオプション追加 |
| 手動では動くがCI/CDで壊れる | 上記すべて | 設定ファイルの完全一致を確認 |

## セキュリティ考慮事項
- 認証情報はGitHub Secretsでのみ管理
- .envファイルはgitignoreに含める
- Dockerイメージに認証情報を含めない
- ハードコードは完全に排除
- ログに認証情報を出力しない（デバッグ時も注意）