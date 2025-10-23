# WatchMe 技術仕様書

最終更新: 2025年10月23日 00:30 JST

## 🏗️ システムアーキテクチャ

### AWS EC2仕様 （更新: 2025-09-19）
- **インスタンスタイプ**: t4g.large (一時的アップグレード、以前t4g.small)
- **CPU**: 2 vCPU (AWS Graviton2)
- **メモリ**: 8.0GB RAM (実使用: 7.8GB) ← 大幅増加
- **ストレージ**: 30GB gp3 SSD
- **リージョン**: ap-southeast-2 (Sydney)
- **IPアドレス**: 3.24.16.82

### リソース状況 （t4g.largeアップグレード後）
- **メモリ使用率**: 未確認 (t4g.small時: ~78%)
- **Swap使用率**: 未確認 (t4g.small時: ~65%)
- **利用可能メモリ**: 6GB以上 (大幅改善)
- **注意**: 将来t4g.smallに戻す可能性あり、リソース管理は継続必要

## 🌐 ネットワーク設計

### watchme-network
- **サブネット**: 172.27.0.0/16
- **ゲートウェイ**: 172.27.0.1
- **管理者**: watchme-infrastructure service
- **設定ファイル**: docker-compose.infra.yml

### 接続コンテナ（IP割り当て）
```
172.27.0.4  : watchme-api-manager-prod
172.27.0.5  : watchme-scheduler-prod
172.27.0.6  : emotion-analysis-aggregator
172.27.0.7  : watchme-vault-api
172.27.0.8  : vibe-analysis-aggregator
172.27.0.9  : vibe-analysis-scorer
172.27.0.10 : watchme-web-prod
172.27.0.11 : vibe-analysis-transcriber-v2
172.27.0.12 : behavior-analysis-sed-aggregator
172.27.0.14 : watchme-admin
172.27.0.15 : watchme-avatar-uploader
172.27.0.17 : behavior-analysis-feature-extractor-v2
172.27.0.18 : emotion-analysis-feature-extractor-v3
172.27.0.30 : janitor-api
```

## 📡 サービス一覧

### クライアントアプリケーション

| サービス | プラットフォーム | 用途 | 録音機能 | 技術スタック | 状態 |
|---------|--------------|------|---------|------------|------|
| **WatchMe App (iOS)** | iOS | ダッシュボード閲覧 + スポット録音分析 | ✅ 手動録音 | Swift | ✅ 本番稼働中 |
| **Observer** | ウェアラブル/据え置き | 定期自動録音デバイス | ✅ 30分ごとに1分間自動録音 | ESP32 (M5 CORE2) / Arduino | 🧪 プロトタイプ運用中 |
| **WatchMe Web** | Web | ダッシュボード閲覧専用 | ❌ なし | React + Vite | ✅ 本番稼働中 |
| **製品サイト** | Web | マーケティング・製品紹介 | - | HTML/CSS/JS (Vercel) | ✅ 公開中 |

### サーバーサイドサービス

| サービス | エンドポイント | ポート | systemd | ECRリポジトリ/ローカル | デプロイ方式 | 備考 |
|---------|--------------|--------|---------|------------------------|------------|------|
| **Vault** | `https://api.hey-watch.me/` | 8000 | watchme-vault-api | watchme-api-vault | ECR | ✅ 2025-09-04移行済み |
| **Admin** | `https://admin.hey-watch.me/` | 9000 | watchme-admin | watchme-admin | ECR | ✅ 稼働中 |
| **API Manager** | `https://api.hey-watch.me/manager/` | 9001 | watchme-api-manager | watchme-api-manager | ECR | ✅ 2025-09-04移行済み |
| **Scheduler** | `https://api.hey-watch.me/scheduler/` | 8015 | watchme-api-manager | watchme-api-manager-scheduler | ECR | ⚠️ 停止中（Lambdaに移行済み） |
| **Janitor** | `/janitor/` | 8030 | janitor-api | watchme-api-janitor | ECR | ✅ EventBridge + Lambda (`watchme-janitor-trigger`) 6時間ごと |
| **Demo Generator** | `/demo/` | 8020 | demo-generator-api | watchme-api-demo-generator | ECR | ✅ EventBridge + Lambda (`demo-data-generator-trigger`) 30分ごと |
| **Audio Enhancer** | (未公開) | 8016 | audio-enhancer-api | watchme-api-audio-enhancer | ローカル | 🚧 現在未使用（音声品質向上） |
| **Avatar Uploader** | (内部) | 8014 | watchme-avatar-uploader | watchme-api-avatar-uploader | ECR | ✅ systemd経由 |
| **Vibe Transcriber** | `/vibe-analysis/transcription/` | 8013 | vibe-analysis-transcriber-v2 | watchme-api-transcriber-v2 | ECR | ✅ 2025-10-22階層化 |
| **Vibe Aggregator** | `/vibe-analysis/aggregation/` | 8009 | vibe-analysis-aggregator | watchme-api-vibe-aggregator | ECR | ✅ 2025-10-22階層化 |
| **Vibe Scorer** | `/vibe-analysis/scoring/` | 8002 | api-gpt-v1 | watchme-api-vibe-scorer | ECR | ✅ 2025-10-22階層化 |
| **Behavior Features** | `/behavior-analysis/features/` | 8017 | behavior-analysis-feature-extractor-v2 | watchme-api-ast | ECR | ✅ 2025-10-22階層化 |
| **Behavior Aggregator** | `/behavior-aggregator/` | 8010 | api-sed-aggregator | watchme-api-sed-aggregator | ECR | ✅ 2025-09-04移行済み |
| **Emotion Features** | `/emotion-analysis/features/` | 8018 | emotion-analysis-feature-extractor-v3 | watchme-api-superb | ECR | ✅ 2025-10-22階層化 |
| **Emotion Aggregator** | `/emotion-analysis/aggregation/` | 8012 | emotion-analysis-aggregator | watchme-api-opensmile-aggregator | ECR | ✅ 2025-10-22階層化 |

## 🚨 トラブルシューティング

### APIエンドポイントの混同に注意

WatchMeでは3種類のエンドポイントがあります：

#### 1. 内部通信用（watchme-network内）
- **形式**: `http://コンテナ名:ポート/endpoint`
- **例**: `http://vibe-analysis-transcriber-v2:8013/fetch-and-transcribe`
- **用途**: watchme-network内でのコンテナ間通信
- **使用者**: API Manager（スケジューラー）など

#### 2. 外部公開用（Nginx経由）
- **形式**: `https://api.hey-watch.me/[階層化パス]/`
- **例**: `https://api.hey-watch.me/vibe-analysis/transcription/`
- **用途**: Lambda関数、外部からのアクセス
- **特徴**: HTTPSで安全、Nginxでルーティング

#### 3. 管理用UI
- **形式**: `https://api.hey-watch.me/manager/`
- **用途**: API Manager UI、Admin画面など
- **ポート**: 9000番台

**⚠️ 注意**: 旧エンドポイント（階層化前）は2025-10-23に削除済み

> その他のトラブルシューティングは [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md#3-トラブルシューティング) を参照

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

> **📘 CI/CDプロセス**: GitHub ActionsによるCI/CDプロセスの詳細は[CI/CD標準仕様書](./CICD_STANDARD_SPECIFICATION.md)を参照

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

### Nginxタイムアウト設定

#### 概要

Nginxがリバースプロキシとして各APIにリクエストを転送する際の**待機時間の上限**を管理しています。
この設定が適切でないと、処理は成功しているのに504エラーが返される問題が発生します。

#### 現在の設定値

| API | パス | タイムアウト | 平均処理時間 | 用途 |
|-----|------|------------|-------------|------|
| **Behavior Features** | /behavior-analysis/features/ | **180秒** | 60-90秒 | 音響イベント検出（大規模モデル） |
| **Emotion Features** | /emotion-analysis/features/ | **180秒** | 30-60秒 | 感情認識処理 |
| **Vibe Transcriber** | /vibe-analysis/transcription/ | **180秒** | 15-30秒 | 音声文字起こし |
| **Vibe Aggregator** | /vibe-analysis/aggregation/ | 60秒（デフォルト） | 5-10秒 | プロンプト生成 |
| **Vibe Scorer** | /vibe-analysis/scoring/ | 60秒（デフォルト） | 10-15秒 | ChatGPT分析 |
| **その他のAPI** | - | 60秒（デフォルト） | < 10秒 | 軽量処理 |

#### タイムアウトの種類と役割

```nginx
location /behavior-analysis/features/ {
    proxy_pass http://localhost:8017/;

    # 3種類のタイムアウト設定
    proxy_connect_timeout 180s;  # 接続確立までの待機時間
    proxy_send_timeout 180s;     # リクエスト送信の待機時間
    proxy_read_timeout 180s;     # レスポンス受信の待機時間（最も重要）
}
```

#### なぜタイムアウト設定が必要か

1. **リソース保護**: 無限待機によるNginxワーカープロセスの枯渇を防ぐ
2. **障害検知**: バックエンドの異常を適切なタイミングで検出
3. **一貫性の確保**: Lambda(180秒) → Nginx(180秒) → API の連鎖を保つ

#### トラブルシューティング

**症状: 504 Gateway Timeout エラー**

**原因**: Nginxのタイムアウトが処理時間より短い

```
実際の処理時間: 90秒
Nginxタイムアウト: 60秒（デフォルト）
結果: 60秒で504エラー（処理は継続中）
```

**解決方法**: 該当APIのlocationブロックにタイムアウト設定を追加

```nginx
# 例: 新しいAPIで長時間処理が必要な場合
location /new-heavy-api/ {
    proxy_pass http://localhost:8020/;
    # ... 他の設定 ...

    # タイムアウトを延長
    proxy_read_timeout 300s;    # 5分まで待機
    proxy_connect_timeout 30s;  # 接続は30秒
    proxy_send_timeout 60s;     # 送信は60秒
}
```

#### 設定変更時の注意事項

1. **影響範囲の確認**
   - 必要なAPIのみタイムアウトを延長（全体への影響を避ける）
   - クライアント側のタイムアウトも確認（Lambda、ブラウザ等）

2. **適切な値の選定**
   - 平均処理時間の2-3倍を目安に設定
   - 過度に長い設定はリソース浪費につながる

3. **変更の適用手順**
   ```bash
   # 1. このリポジトリで設定を変更
   # 2. GitHubにプッシュ
   # 3. 本番サーバーで適用
   ssh ubuntu@[SERVER_IP]
   cd /home/ubuntu/watchme-server-configs
   git pull origin main
   ./setup_server.sh
   sudo nginx -t && sudo systemctl reload nginx
   ```

---

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