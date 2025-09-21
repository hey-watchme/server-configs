# リージョン移行ガイド（シドニー → 東京）

最終更新: 2025-09-19

## 📋 移行前チェックリスト

### 現在の構成確認
- [ ] EC2: ap-southeast-2 (シドニー) - t4g.large
- [ ] ECR: ap-southeast-2 - 13リポジトリ
- [ ] Supabase: 外部SaaS（影響なし）
- [ ] S3: 確認必要（おそらく影響小）

## 🚀 移行手順詳細

### Phase 1: 準備作業（1-2時間）

#### 1.1 東京リージョンにECRリポジトリ作成
```bash
# 東京リージョンに切り替え
export AWS_DEFAULT_REGION=ap-northeast-1

# リポジトリ作成スクリプト
REPOS=(
  "watchme-admin"
  "watchme-api-vault"
  "watchme-api-manager"
  "watchme-api-manager-scheduler"
  "watchme-web"
  "watchme-avatar-uploader"
  "watchme-api-transcriber-v2"
  "watchme-api-vibe-scorer"
  "watchme-api-vibe-aggregator"
  "watchme-api-behavior-features"
  "watchme-api-behavior-aggregator"
  "watchme-opensmile-api"
  "watchme-api-opensmile-aggregator"
  "watchme-api-superb"
)

for repo in "${REPOS[@]}"; do
  aws ecr create-repository --repository-name $repo --region ap-northeast-1
done
```

#### 1.2 Dockerイメージの移行
```bash
# シドニーからイメージを取得して東京にプッシュ
SOURCE_REGION="ap-southeast-2"
TARGET_REGION="ap-northeast-1"
ACCOUNT_ID="754724220380"

# ログイン
aws ecr get-login-password --region $SOURCE_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$SOURCE_REGION.amazonaws.com
aws ecr get-login-password --region $TARGET_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$TARGET_REGION.amazonaws.com

# 各イメージを移行
for repo in "${REPOS[@]}"; do
  # Pull from Sydney
  docker pull $ACCOUNT_ID.dkr.ecr.$SOURCE_REGION.amazonaws.com/$repo:latest
  
  # Tag for Tokyo
  docker tag $ACCOUNT_ID.dkr.ecr.$SOURCE_REGION.amazonaws.com/$repo:latest \
             $ACCOUNT_ID.dkr.ecr.$TARGET_REGION.amazonaws.com/$repo:latest
  
  # Push to Tokyo
  docker push $ACCOUNT_ID.dkr.ecr.$TARGET_REGION.amazonaws.com/$repo:latest
done
```

### Phase 2: EC2インスタンス作成（1時間）

#### 2.1 AMI作成とコピー
```bash
# 現在のインスタンスからAMI作成
aws ec2 create-image \
  --instance-id [現在のインスタンスID] \
  --name "watchme-server-$(date +%Y%m%d)" \
  --region ap-southeast-2

# AMIを東京にコピー
aws ec2 copy-image \
  --source-image-id [作成したAMI-ID] \
  --source-region ap-southeast-2 \
  --region ap-northeast-1 \
  --name "watchme-server-tokyo"
```

#### 2.2 新EC2インスタンス起動
```bash
# 東京リージョンでインスタンス起動
aws ec2 run-instances \
  --image-id [コピーしたAMI-ID] \
  --instance-type t4g.large \
  --key-name [キーペア名] \
  --security-group-ids [セキュリティグループ] \
  --subnet-id [サブネットID] \
  --region ap-northeast-1
```

### Phase 3: 設定ファイル更新（1時間）

#### 3.1 リージョン一括置換
```bash
# watchme-server-configs内の全ファイル
cd /home/ubuntu/watchme-server-configs

# バックアップ作成
tar czf configs-backup-$(date +%Y%m%d).tar.gz .

# 一括置換
find . -type f \( -name "*.yml" -o -name "*.service" \) \
  -exec sed -i 's/ap-southeast-2/ap-northeast-1/g' {} \;

# docker-compose-files内
cd docker-compose-files
for file in *.yml; do
  sed -i 's/ap-southeast-2/ap-northeast-1/g' $file
done

# systemdサービス
cd ../systemd
for file in *.service; do
  sed -i 's/ap-southeast-2/ap-northeast-1/g' $file
done
```

#### 3.2 設定の適用
```bash
# セットアップスクリプト実行
cd /home/ubuntu/watchme-server-configs
./setup_server.sh

# systemdリロード
sudo systemctl daemon-reload

# サービス再起動
for service in watchme-*.service api-*.service mood-*.service opensmile-*.service vibe-*.service; do
  sudo systemctl restart $service
done
```

### Phase 4: 動作確認とDNS切り替え（30分）

#### 4.1 動作確認
```bash
# ネットワーク確認
bash scripts/check-infrastructure.sh

# サービス状態確認
docker ps --format "table {{.Names}}\t{{.Status}}"

# APIアクセステスト
curl -I http://[新EC2のIP]/health
```

#### 4.2 DNS切り替え
```bash
# Route53またはお使いのDNSプロバイダで以下を変更：
# api.hey-watch.me → 新EC2のElastic IP
# dashboard.hey-watch.me → 新EC2のElastic IP
# admin.hey-watch.me → 新EC2のElastic IP
```

## ⚠️ 注意事項

### ロールバック計画
1. 旧環境は1週間維持
2. 問題発生時はDNSを元に戻すだけで切り戻し可能
3. データはSupabaseにあるため、データロスの心配なし

### コスト管理
- 移行期間中は両環境が稼働（約2倍のコスト）
- 移行完了後、旧環境を停止してコスト正常化
- AWSクレジット$300は両リージョンで利用可能

### トラブルシューティング

#### ECRログインエラー
```bash
# リージョン指定を確認
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin 754724220380.dkr.ecr.ap-northeast-1.amazonaws.com
```

#### ネットワークエラー
```bash
# watchme-networkの再作成
docker network create watchme-network
python3 scripts/network_monitor.py --fix
```

## 📊 期待される改善効果

| メトリクス | 改善前 | 改善後 | 改善率 |
|-----------|--------|--------|--------|
| API平均応答時間 | 250ms | 30ms | 88%削減 |
| ダッシュボード表示 | 1.5秒 | 0.2秒 | 87%削減 |
| ユーザー体感速度 | もっさり | サクサク | 大幅改善 |
| 音声処理遅延 | 300ms | 40ms | 87%削減 |

## 🎯 成功基準

- [ ] 全13サービスが東京リージョンで稼働
- [ ] レイテンシーが50ms以下
- [ ] 24時間の安定稼働確認
- [ ] 旧環境の安全な停止

## 📅 推奨スケジュール

1. **準備**: 平日午前中（トラフィック少）
2. **移行**: 週末または深夜
3. **監視**: 移行後48時間は注意深く監視
4. **完了**: 1週間後に旧環境停止

---

**作成日**: 2025-09-19
**作成者**: WatchMe Infrastructure Team
**優先度**: 高（商用利用開始前に必須）