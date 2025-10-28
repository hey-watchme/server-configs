# WatchMe 技術仕様書

最終更新: 2025年10月26日 14:00 JST

## 🏗️ システムアーキテクチャ

### AWS EC2仕様 （更新: 2025-10-26）
- **インスタンスタイプ**: t4g.large (一時的アップグレード、以前t4g.small)
- **CPU**: 2 vCPU (AWS Graviton2)
- **メモリ**: 8.0GB RAM (実使用: 7.8GB)
- **ストレージ**: 30GB gp3 SSD
- **リージョン**: ap-southeast-2 (Sydney)
- **IPアドレス**: 3.24.16.82

### リソース状況 （2025-10-28 更新）

#### メモリ使用状況
- **総メモリ**: 7.6GB
- **使用中**: 2.8GB (37%)
- **利用可能**: 4.8GB (63%)
- **Swap使用**: 1.0GB / 2.0GB (50%)
- **バッファ/キャッシュ**: 4.8GB

#### ディスク使用状況
- **総容量**: 29GB
- **使用中**: 26GB (91%)
- **空き容量**: 2.8GB (9%)
- **⚠️ 警告**: ディスク使用率が高い（90%超）
- **推奨**: ストレージ拡張を検討（30GB → 50GB、月額+$1.60）

#### リソース管理の考慮事項

**Kushinada APIへの移行によるリソース影響 (2025-10-26):**

| 項目 | v3 (SUPERB) | v2 (Kushinada) | 差分 |
|------|-------------|----------------|------|
| モデルサイズ | 約400MB | 約1.3GB | +900MB |
| Dockerイメージ | 約3.4GB | 約4.5GB（予想） | +1.1GB |
| 実行時メモリ | 1.5-2GB | 3-3.5GB | +1.5-2GB |
| ピーク時メモリ | 約2.5GB | 約4GB | +1.5GB |

**⚠️ 重要な注意点:**
1. **メモリは現状余裕あり**: 利用可能メモリ5.2GBに対し、Kushinadaは3-3.5GB使用予定
2. **ディスク容量に注意**: 空き6.6GBに対し、新イメージで約1.1GB増加
3. **同時実行数の制限**: メモリ制約により、ワーカー数は1に制限推奨
4. **将来の対策**:
   - 不要なDockerイメージの定期削除（`docker system prune`）
   - 古いログファイルのクリーンアップ
   - 必要に応じてストレージ拡張（30GB → 50GB）を検討

### AWSリージョン構成 （更新: 2025-10-26）

**全てのAWSリソースは `ap-southeast-2` (Sydney) に統一されています。**

| サービス | リージョン | リージョン名 | 備考 |
|---------|-----------|------------|------|
| **EC2** | `ap-southeast-2` | Sydney | サーバー本体 |
| **ECR** | `ap-southeast-2` | Sydney | Dockerイメージレジストリ（13リポジトリ） |
| **Lambda** | `ap-southeast-2` | Sydney | audio-worker, janitor-trigger等 |
| **S3 (watchme-vault)** | `ap-southeast-2` | Sydney | 音声ファイル保管 |
| **EventBridge** | `ap-southeast-2` | Sydney | スケジューラー |

#### 重要な注意点

1. **全リソースをap-southeast-2に統一**
   - 全てのAWSサービスは同じリージョン内に配置されています
   - リージョン間のデータ転送料金は発生しません
   - 混乱を避けるため、全ての`.env`ファイルで`AWS_REGION=ap-southeast-2`を使用

2. **設定の統一**
   - EC2上で動作するAPIは `AWS_REGION=ap-southeast-2` を環境変数で設定
   - Lambda関数も `region_name='ap-southeast-2'` を明示的に指定
   - **重要**: 過去に`us-east-1`が使われていた記述は全て誤りです

3. **リージョン移行計画**
   - 将来的に東京リージョン (`ap-northeast-1`) への移行を検討中
   - 詳細は [REGION_MIGRATION_GUIDE.md](./REGION_MIGRATION_GUIDE.md) を参照

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
172.27.0.17 : behavior-analysis-feature-extractor  (v3 PaSST)
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

| サービス | エンドポイント | ポート | EC2ディレクトリ | systemd | ECRリポジトリ/ローカル | デプロイ方式 | 備考 |
|---------|--------------|--------|---------------|---------|------------------------|------------|------|
| **Vault** | `https://api.hey-watch.me/` | 8000 | /home/ubuntu/watchme-vault-api | watchme-vault-api | watchme-api-vault | ECR | ✅ 2025-09-04移行済み |
| **Admin** | `https://admin.hey-watch.me/` | 9000 | /home/ubuntu/admin | watchme-admin | watchme-admin | ECR | ✅ 稼働中 |
| **API Manager** | `https://api.hey-watch.me/manager/` | 9001 | /home/ubuntu/watchme-api-manager | watchme-api-manager | watchme-api-manager | ECR | ✅ 2025-09-04移行済み |
| **Scheduler** | `https://api.hey-watch.me/scheduler/` | 8015 | /home/ubuntu/watchme-scheduler | watchme-api-manager | watchme-api-manager-scheduler | ECR | ⚠️ 停止中（Lambdaに移行済み） |
| **Janitor** | `/janitor/` | 8030 | /home/ubuntu/janitor-api | janitor-api | watchme-api-janitor | ECR | ✅ EventBridge + Lambda (`watchme-janitor-trigger`) 6時間ごと |
| **Demo Generator** | `/demo/` | 8020 | /home/ubuntu/demo-generator-api | demo-generator-api | watchme-api-demo-generator | ECR | ✅ EventBridge + Lambda (`demo-data-generator-trigger`) 30分ごと |
| **Audio Enhancer** | (未公開) | 8016 | /home/ubuntu/audio-enhancer-api | audio-enhancer-api | watchme-api-audio-enhancer | ローカル | 🚧 現在未使用（音声品質向上） |
| **Avatar Uploader** | (内部) | 8014 | /home/ubuntu/watchme-avatar-uploader | watchme-avatar-uploader | watchme-api-avatar-uploader | ECR | ✅ systemd経由 |
| **Vibe Transcriber** | `/vibe-analysis/transcription/` | 8013 | /home/ubuntu/vibe-analysis-transcriber | vibe-analysis-transcriber | watchme-vibe-analysis-transcriber | ECR | ✅ 2025-10-28統一命名規則 |
| **Vibe Aggregator** | `/vibe-analysis/aggregation/` | 8009 | /home/ubuntu/vibe-analysis-aggregator | vibe-analysis-aggregator | watchme-api-vibe-aggregator | ECR | ✅ 2025-10-22階層化 |
| **Vibe Scorer** | `/vibe-analysis/scoring/` | 8002 | /home/ubuntu/api_gen_prompt_mood_chart | api-gpt-v1 | watchme-api-vibe-scorer | ECR | ✅ 2025-10-22階層化 |
| **Behavior Features** | `/behavior-analysis/features/` | 8017 | /home/ubuntu/behavior-analysis-feature-extractor | behavior-analysis-feature-extractor | watchme-behavior-analysis-feature-extractor | ECR | ✅ 2025-10-28 v3 PaSST移行 |
| **Behavior Aggregator** | `/behavior-aggregator/` | 8010 | /home/ubuntu/api-sed-aggregator | api-sed-aggregator | watchme-api-sed-aggregator | ECR | ✅ 2025-09-04移行済み |
| **Emotion Features** | `/emotion-analysis/features/` | 8018 | /home/ubuntu/emotion-analysis-feature-extractor-v3 | emotion-analysis-feature-extractor-v3 | watchme-emotion-analysis-feature-extractor-v3 | ECR | ✅ 2025-10-26 Kushinada移行 |
| **Emotion Aggregator** | `/emotion-analysis/aggregation/` | 8012 | /home/ubuntu/opensmile-aggregator | emotion-analysis-aggregator | watchme-api-opensmile-aggregator | ECR | ✅ 2025-10-22階層化 |

## 🎙️ 音声処理API詳細

### Emotion Features API（感情認識）

**2025-10-26更新: SUPERB → Kushinada移行完了**

| 項目 | v3 (SUPERB) | v2 (Kushinada - 現行) |
|------|-------------|---------------------|
| **モデル** | wav2vec2-base-superb-er | kushinada-hubert-large-jtes-er |
| **開発元** | Meta AI / SUPERB | 産総研（AIST） |
| **学習データ** | 英語音声（IEMOCAP等） | 日本語音声（JTES） |
| **感情カテゴリ** | 8感情 | 4感情 |
| **パラメータ数** | 95M | 316M |
| **モデルサイズ** | 400MB | 1.3GB |
| **実行時メモリ** | 1.5-2GB | 3-3.5GB |
| **処理時間（60秒音声）** | 30-45秒 | 40-60秒 |
| **anger検出精度** | 低い（誤認識多い） | **高い（84.77%）** |

#### 感情カテゴリ詳細

**Kushinada (v2) - 4感情:**
- `neutral` - 中立
- `joy` - 喜び
- `anger` - 怒り（**高精度**）
- `sadness` - 悲しみ

**処理方式:**
- 10秒セグメントで分析（時系列追跡）
- 各セグメントの感情確率を返却
- OpenSMILE互換データ構造

#### リソース要件

**メモリ:**
- アイドル時: 約500MB
- 推論時: 3-3.5GB（ピーク時）
- 推奨: workers=1（メモリ制約）

**ストレージ:**
- Dockerイメージ: 約4.5GB
- モデルキャッシュ: 約1.3GB
- 合計: 約5.8GB

#### 移行理由（2025-10-26）

1. **日本語音声に特化**: JTESデータセットで学習
2. **怒り検出の精度向上**: 84.77% vs SUPERBの誤認識問題
3. **時系列分析**: 10秒セグメントで感情推移を追跡
4. **実証済み**: ローカルテストで高精度を確認

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

> **運用手順**: 日常監視コマンド、緊急時対応、全体再起動手順などの詳細は [OPERATIONS_GUIDE.md - 監視・メンテナンス](./OPERATIONS_GUIDE.md#5-監視メンテナンス) を参照

## 🔧 設定変更

> **運用手順**: systemd設定変更、Nginx設定変更、デプロイ手順などの詳細は [OPERATIONS_GUIDE.md - サーバー構成の変更手順](./OPERATIONS_GUIDE.md#2-サーバー構成の変更手順) を参照

> **CI/CDプロセス**: GitHub ActionsによるCI/CDプロセスの詳細は [CI/CD標準仕様書](./CICD_STANDARD_SPECIFICATION.md) を参照

### Nginxタイムアウト設定（技術仕様）

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

**504 Gateway Timeout エラーが発生する場合**:
- 症状と解決方法は [OPERATIONS_GUIDE.md - Nginxタイムアウト設定の変更](./OPERATIONS_GUIDE.md#-nginxタイムアウト設定の変更) を参照

---

## 🎯 ベストプラクティス

運用上のベストプラクティスは [OPERATIONS_GUIDE.md - ベストプラクティス](./OPERATIONS_GUIDE.md#6-ベストプラクティス) を参照してください。

主な内容:
- 本番用設定の徹底（docker-compose.prod.yml使用）
- systemd管理の徹底（手動起動を避ける）
- ネットワーク統一（watchme-network）
- ヘルスチェック実装
- 設定の一元管理（Git経由）