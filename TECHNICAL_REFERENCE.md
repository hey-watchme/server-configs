# WatchMe 技術仕様書

最終更新: 2025年9月4日 17:30 JST

## 🏗️ システムアーキテクチャ

### AWS EC2仕様
- **インスタンスタイプ**: t4g.small
- **CPU**: 2 vCPU (AWS Graviton2)
- **メモリ**: 2.0GB RAM (実使用: 1.8GB)
- **ストレージ**: 30GB gp3 SSD
- **リージョン**: ap-southeast-2 (Sydney)
- **IPアドレス**: 3.24.16.82

### リソース制約
- **メモリ使用率**: ~78% (1.4GB/1.8GB)
- **Swap使用率**: ~65% (1.3GB/2.0GB)
- **利用可能メモリ**: 400MB未満
- **注意**: 新しいサービス追加時はメモリ制限必須

## 🌐 ネットワーク設計

### watchme-network
- **サブネット**: 172.27.0.0/16
- **ゲートウェイ**: 172.27.0.1
- **管理者**: watchme-infrastructure service
- **設定ファイル**: docker-compose.infra.yml

### 接続コンテナ（IP割り当て）
```
172.27.0.2  : watchme-scheduler-prod
172.27.0.3  : (旧)api-transcriber - 削除済み
172.27.0.4  : watchme-api-manager-prod
172.27.0.5  : opensmile-aggregator
172.27.0.6  : watchme-vault-api
172.27.0.7  : api_gen_prompt_mood_chart
172.27.0.8  : api-gpt-v1
172.27.0.9  : watchme-web-prod
172.27.0.10 : vibe-transcriber-v2
172.27.0.11 : sed-api (旧: api_sed_v1-sed_api-1)
172.27.0.12 : opensmile-api
172.27.0.13 : watchme-admin
172.27.0.14 : api-sed-aggregator
```

## 📡 サービス一覧

| サービス | エンドポイント | ポート | systemd | ECRリポジトリ/ローカル | デプロイ方式 | 備考 |
|---------|--------------|--------|---------|------------------------|------------|------|
| **Gateway API** | `https://api.hey-watch.me/` | 8000 | watchme-vault-api | ローカル | Docker | ECRリポジトリなし |
| **API Manager UI** | `https://api.hey-watch.me/manager/` | 9001 | watchme-api-manager | watchme-api-manager | ？ | ECRリポジトリあり、確認必要 |
| **Scheduler** | `https://api.hey-watch.me/scheduler/` | 8015 | watchme-api-manager | watchme-api-manager-scheduler | ？ | ECRリポジトリあり、確認必要 |
| **Web Dashboard** | `https://dashboard.hey-watch.me/` | 3001 | watchme-web-app | watchme-web | ECR | ✅ 5週間前から稼働中 |
| **Admin Panel** | `https://admin.hey-watch.me/` | 9000 | watchme-admin | watchme-admin | ECR | ✅ 稼働中 |
| **Avatar Uploader** | (内部) | 8014 | watchme-avatar-uploader | watchme-api-avatar-uploader | ECR | ✅ systemd経由 |
| **Azure Speech** | `/vibe-transcriber-v2/` | 8013 | vibe-transcriber-v2 | watchme-api-transcriber-v2 | ECR | ✅ 稼働中 |
| **Prompt Generator** | `/vibe-aggregator/` | 8009 | mood-chart-api | watchme-api-vibe-aggregator | ECR | ✅ 稼働中 |
| **Psychology Scorer** | `/vibe-scorer/` | 8002 | api-gpt-v1 | watchme-api-vibe-scorer | ECR | ✅ 2025-09-04移行済み |
| **Behavior Detection** | `/behavior-features/` | 8004 | watchme-behavior-yamnet | watchme-api-behavior-features | ECR | ✅ 2025-09-04移行済み |
| **Behavior Aggregator** | `/behavior-aggregator/` | 8010 | api-sed-aggregator | watchme-api-behavior-aggregator | Docker | ❌ リポジトリあり、未移行 |
| **Emotion Features** | `/emotion-features/` | 8011 | opensmile-api | watchme-opensmile-api | ECR | ✅ 2025-09-04移行済み |
| **Emotion Aggregator** | `/emotion-aggregator/` | 8012 | opensmile-aggregator | watchme-api-opensmile-aggregator | ECR | ✅ 2025-09-04移行済み |

## 🔄 コンテナ間通信エンドポイント

スケジューラーが各APIを呼び出す際の正確な情報：

| API | コンテナ名 | ポート | エンドポイント | メソッド |
|-----|-----------|--------|---------------|----------|
| Azure Speech | `vibe-transcriber-v2` | 8013 | `/fetch-and-transcribe` | POST |
| Prompt Generator | `api_gen_prompt_mood_chart` | 8009 | `/generate-mood-prompt-supabase` | GET |
| Psychology Scorer | `api-gpt-v1` | 8002 | `/analyze-vibegraph-supabase` | POST |
| Behavior Detection | `sed-api` | 8004 | `/fetch-and-process-paths` | POST |
| Behavior Aggregator | `api-sed-aggregator` | 8010 | `/analysis/sed` | POST |
| Emotion Features | `opensmile-api` | 8011 | `/process/emotion-features` | POST |
| Emotion Aggregator | `opensmile-aggregator` | 8012 | `/analyze/opensmile-aggregator` | POST |

## 🚨 トラブルシューティング

### 問題: コンテナが起動しない

```bash
# 1. 構文確認
docker-compose -f docker-compose.prod.yml config

# 2. ポート競合確認
sudo lsof -i:[ポート番号]
# 競合がある場合: kill -9 [PID]

# 3. 環境変数確認
ls -la .env
cat .env | head -5

# 4. 詳細ログ
sudo journalctl -u [サービス名].service -f
```

### 問題: ヘルスチェック失敗（unhealthy）

```bash
# 1. curlの存在確認
docker exec [コンテナ名] which curl

# 2. 手動ヘルスチェック
docker exec [コンテナ名] curl -f http://localhost:8000/health

# 3. 使用Dockerfile確認
grep dockerfile docker-compose.prod.yml
```

**解決策:** Dockerfile.prodにcurlをインストール

### 問題: ネットワーク接続エラー

```bash
# 1. ネットワーク接続確認
docker network inspect watchme-network | grep [コンテナ名]

# 2. 手動接続テスト
docker exec [コンテナA] ping -c 1 [コンテナB]

# 3. 設定確認
grep -A 5 "networks:" docker-compose.prod.yml
```

**解決策:**
- `external: true` の設定確認
- 手動接続: `docker network connect watchme-network [コンテナ名]`

### 問題: サーバー再起動後に起動しない

```bash
# 1. 有効化確認
sudo systemctl is-enabled [サービス名].service

# 2. 依存関係確認
sudo systemctl list-dependencies [サービス名].service

# 3. 有効化
sudo systemctl enable [サービス名].service
```

### 問題: APIが404エラー

**原因**: 3種類のエンドポイントの混同

1. **管理用**: `https://api.hey-watch.me/scheduler/status/`
2. **内部通信用**: `http://コンテナ名:ポート/endpoint`
3. **外部公開用**: `https://api.hey-watch.me/vibe-transcriber/`

**解決策**: 適切なエンドポイントを使用

## 📊 監視・メンテナンス

### 日常監視コマンド

```bash
# システム全体の状態
free -h && df -h

# 全サービス状態
sudo systemctl status watchme-*.service | grep -E "●|Active|failed"

# 全コンテナ状態  
docker ps --format "table {{.Names}}\t{{.Status}}"

# ネットワーク状態
/home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh
```

### 緊急時対応

**メモリ不足時:**
```bash
# 低優先度サービス停止
sudo systemctl stop watchme-admin.service

# リソースクリーンアップ
docker system prune -f
```

**全体再起動時:**
```bash
# 順序: インフラ → 個別サービス
sudo systemctl restart watchme-infrastructure.service
sleep 30
sudo systemctl restart watchme-vault-api.service
sudo systemctl restart watchme-api-manager.service
```

## 🔧 設定変更手順

### systemd設定変更

```bash
# 1. ローカルで編集
cd /Users/kaya.matsumoto/projects/watchme/watchme-server-configs
nano systemd/[サービス名].service

# 2. コミット・プッシュ
git add systemd/[サービス名].service
git commit -m "fix: [サービス名]設定を修正"
git push origin main

# 3. サーバーで反映
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
cd /home/ubuntu/watchme-server-configs
git pull origin main
./setup_server.sh
sudo systemctl restart [サービス名].service
```

### Nginx設定変更

```bash
# 1. 設定テスト
sudo nginx -t

# 2. 反映
sudo systemctl reload nginx

# 3. 確認
curl -I https://api.hey-watch.me/
```

## 🎯 ベストプラクティス

1. **必ず本番用設定を使用**
   - `docker-compose.prod.yml`
   - `Dockerfile.prod`

2. **systemd管理を徹底**
   - 手動起動は避ける
   - 必ず有効化する

3. **ネットワーク統一**
   - `watchme-network` のみ使用
   - `external: true` 必須

4. **ヘルスチェック実装**
   - 全APIに `/health` エンドポイント
   - Dockerfileにcurlインストール

5. **設定の一元管理**
   - 変更は必ずGit経由
   - 直接編集禁止

## 🐳 ECRリポジトリ一覧

| サービス名 | ECRリポジトリ | イメージURI |
|-----------|-------------|------------|
| **Admin Panel** | watchme-admin | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-admin:latest |
| **Avatar Uploader** | watchme-avatar-uploader | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-avatar-uploader:latest |
| **Azure Speech** | watchme-api-transcriber-v2 | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-transcriber-v2:latest |
| **Psychology Scorer** | watchme-api-vibe-scorer | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-vibe-scorer:latest |
| **Behavior Detection** | watchme-api-behavior-features | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-behavior-features:latest |
| **Emotion Features** | watchme-opensmile-api | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-opensmile-api:latest |
| **Emotion Aggregator** | watchme-api-opensmile-aggregator | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-opensmile-aggregator:latest |
| **Prompt Generator** | watchme-api-vibe-aggregator | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-api-vibe-aggregator:latest |
| **Web Dashboard** | watchme-web | 754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-web:latest |

### ECR移行状況サマリー
#### ✅ 移行済み（9サービス）
- Admin Panel, Avatar Uploader, Azure Speech, Prompt Generator
- Psychology Scorer, Behavior Detection, Emotion Features, Emotion Aggregator
- Web Dashboard

#### ❌ 未移行（リポジトリあり）（3サービス）
- **Behavior Aggregator** (api-sed-aggregator) - リポジトリ: watchme-api-behavior-aggregator
- **API Manager UI** - リポジトリ: watchme-api-manager
- **Scheduler** - リポジトリ: watchme-api-manager-scheduler

#### ❌ 未移行（リポジトリなし）（1サービス）
- **Gateway API** (watchme-vault-api) - ECRリポジトリ作成必要

### 未使用ECRリポジトリ
- watchme-api-transcriber（旧バージョン、v2が稼働中）