# WatchMe API CI/CD 標準仕様書

## 概要
全WatchMe APIで統一するCI/CDプロセスの標準仕様

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

## 1. GitHub Actionsワークフロー仕様

### 必須ステップ
```yaml
# ステップ1: ECRにDockerイメージをプッシュ
# ステップ2: EC2に.envファイルを作成/更新
# ステップ3: docker-composeでコンテナ再起動
```

### 環境変数作成ステップ（重要）
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
      cat > .env << 'EOF'
    SUPABASE_URL=${SUPABASE_URL}
    SUPABASE_KEY=${SUPABASE_KEY}
    EOF
    ENDSSH
```

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
| api-sed-aggregator | /home/ubuntu/api-sed-aggregator | 8010 | ✅ 修正済み | - |
| api_ast | /home/ubuntu/api_ast | 8017 | ハードコード方式 | 要修正 |
| opensmile-aggregator | /home/ubuntu/opensmile-aggregator | 8012 | 未確認 | 要確認 |
| api_gen_prompt_mood_chart | /home/ubuntu/watchme-api-vibe-aggregator | 8009 | 正常（見本） | - |

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

## セキュリティ考慮事項
- 認証情報はGitHub Secretsでのみ管理
- .envファイルはgitignoreに含める
- Dockerイメージに認証情報を含めない
- ハードコードは完全に排除