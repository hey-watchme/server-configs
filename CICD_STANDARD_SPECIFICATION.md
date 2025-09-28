# WatchMe API CI/CD 標準仕様書

## 概要
全WatchMe APIで統一するCI/CDプロセスの標準仕様

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
# ステップ1: ECRにDockerイメージをプッシュ
# ステップ2: EC2に.envファイルを作成/更新
# ステップ3: デプロイスクリプトをEC2に自動更新
# ステップ4: docker-composeでコンテナ再起動
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

- name: Update deploy scripts on EC2
  env:
    EC2_HOST: ${{ secrets.EC2_HOST }}
    EC2_USER: ${{ secrets.EC2_USER }}
  run: |
    echo "📦 Updating deploy scripts on EC2..."
    
    # Checkoutステップで取得したファイルをEC2にコピー
    scp -o StrictHostKeyChecking=no \
      ./run-prod.sh \
      ./docker-compose.prod.yml \
      ${EC2_USER}@${EC2_HOST}:/home/ubuntu/{api-name}/
    
    # 実行権限を付与
    ssh ${EC2_USER}@${EC2_HOST} "chmod +x /home/ubuntu/{api-name}/run-prod.sh"
    
    echo "✅ Deploy scripts updated successfully"
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

## トラブルシューティング

### よくある問題と解決方法

#### 「Invalid API key」エラーが解決しない
**症状：** GitHub Actions成功後も環境変数エラーが続く

**診断方法：**
1. EC2上の.envファイルの内容を確認
   ```bash
   ssh ubuntu@EC2_HOST "cat /home/ubuntu/api-name/.env"
   # 期待値: SUPABASE_KEY=eyJhbGci... (実際のキー)
   # 問題: SUPABASE_KEY=${SUPABASE_KEY} (変数が展開されていない)
   ```

2. コンテナ内の環境変数を確認
   ```bash
   docker exec container-name env | grep SUPABASE
   # 問題例: SUPABASE_KEY=your-supabase-key-here
   ```

**根本原因と解決策：**

| 原因 | 症状 | 解決策 |
|------|------|--------|
| ヒアドキュメントのインデント問題 | .envに`${SUPABASE_KEY}`が書き込まれる | echoコマンドを使用 |
| .envファイルのパス不一致 | 環境変数が読み込まれない | docker-compose.ymlとrun-prod.shで同じパスを使用 |
| Dockerイメージにデフォルト値がハードコード | 常に同じエラー | Dockerfileに環境変数を含めない |

## セキュリティ考慮事項
- 認証情報はGitHub Secretsでのみ管理
- .envファイルはgitignoreに含める
- Dockerイメージに認証情報を含めない
- ハードコードは完全に排除
- ログに認証情報を出力しない（デバッグ時も注意）