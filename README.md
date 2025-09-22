# WatchMe サーバー設定リポジトリ

このリポジトリは、WatchMeプラットフォームのEC2サーバーで稼働する **インフラストラクチャ**、**Nginx**、**systemd** の設定を一元管理します。

## ⚡ クイックスタート

**アプリケーションをデプロイする場合** → [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md#1-アプリケーションのデプロイ手順)  
**サーバー構成を変更する場合** → [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md#2-サーバー構成の変更手順)  
**技術詳細を調べる場合** → [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md)  
**変更履歴を確認する場合** → [CHANGELOG.md](./CHANGELOG.md)

## 🔄 重要：音声処理API移行作業（2025年9月19日）

### 移行の背景
- **SED API（YamNet）** → **AST API**へ移行
  - 理由：より高精度な527種類の音響イベント検出が可能
  - Transformerベースの最新アーキテクチャ
- **OpenSMILE API** → **SUPERB API**へ移行
  - 理由：wav2vec2ベースでより高速・高精度
  - OpenSMILE互換インターフェースを維持

### ⚠️ 正しいポート割り当て（重要）

| API名 | 正しいポート | 用途 | Nginxパス | ECRリポジトリ |
|-------|------------|------|----------|--------------|
| **AST API** | **8017** | 音響イベント検出（SED代替） | /behavior-features/ | watchme-api-ast |
| **SUPERB API** | **8018** | 感情認識（OpenSMILE代替） | /emotion-features/ | watchme-api-superb |
| sed-api（廃止） | 8004 | 旧音響イベント検出 | - | watchme-api-behavior-features |
| opensmile-api（廃止） | 8011 | 旧感情特徴量抽出 | - | watchme-api-opensmile |

### 移行作業手順（リージョン移行時に実施）

#### Step 1: ECRリポジトリの作成（東京リージョン）
```bash
# AST API用
aws ecr create-repository --repository-name watchme-api-ast --region ap-northeast-1

# SUPERB API用  
aws ecr create-repository --repository-name watchme-api-superb --region ap-northeast-1
```

#### Step 2: Dockerイメージのビルドとプッシュ
```bash
# AST API
cd /path/to/api_ast
docker build -f Dockerfile.prod -t watchme-api-ast:latest .
docker tag watchme-api-ast:latest 754724220380.dkr.ecr.ap-northeast-1.amazonaws.com/watchme-api-ast:latest
docker push 754724220380.dkr.ecr.ap-northeast-1.amazonaws.com/watchme-api-ast:latest

# SUPERB API
cd /path/to/api_superb_v1
docker build -f Dockerfile.prod -t watchme-api-superb:latest .
docker tag watchme-api-superb:latest 754724220380.dkr.ecr.ap-northeast-1.amazonaws.com/watchme-api-superb:latest
docker push 754724220380.dkr.ecr.ap-northeast-1.amazonaws.com/watchme-api-superb:latest
```

#### Step 3: docker-compose.prod.yml設定（正しいポート）

**AST API (api_ast/docker-compose.prod.yml):**
```yaml
version: '3.8'
services:
  api:
    image: 754724220380.dkr.ecr.ap-northeast-1.amazonaws.com/watchme-api-ast:latest
    container_name: ast-api
    ports:
      - "127.0.0.1:8017:8017"  # 正しいポート：8017
    networks:
      - watchme-network
    mem_limit: 2g
```

**SUPERB API (api_superb_v1/docker-compose.prod.yml):**
```yaml
version: '3.8'
services:
  api:
    image: 754724220380.dkr.ecr.ap-northeast-1.amazonaws.com/watchme-api-superb:latest
    container_name: superb-api
    ports:
      - "127.0.0.1:8018:8018"  # 正しいポート：8018
    networks:
      - watchme-network
    mem_limit: 1g
```

#### Step 4: Nginx設定更新
```nginx
# AST API (音響イベント検出)
location /behavior-features/ {
    proxy_pass http://localhost:8017/;  # AST APIのポート
    # ... 他の設定
}

# SUPERB API (感情認識)
location /emotion-features/ {
    proxy_pass http://localhost:8018/;  # SUPERB APIのポート
    # ... 他の設定
}
```

#### Step 5: systemdサービス設定
新しいサービスファイルを作成：
- `/etc/systemd/system/watchme-ast-api.service`
- `/etc/systemd/system/watchme-superb-api.service`

### ⚠️ 移行時の注意事項

1. **ポートの混同を避ける**
   - AST = 8017（セブンティーン）
   - SUPERB = 8018（エイティーン）

2. **旧APIの停止タイミング**
   - 新APIが正常動作を確認してから停止
   - データ移行が必要な場合は事前に実施

3. **メモリ制限**
   - AST API: 2GB推奨（モデルが大きい）
   - SUPERB API: 1GB推奨

4. **ヘルスチェック**
   - AST: `curl http://localhost:8017/health`
   - SUPERB: `curl http://localhost:8018/health`

## 🚨 重要：リージョン移行予定（商用利用開始前に実施必須）

### 現在の状況と移行の必要性
- **現在**: ap-southeast-2 (シドニー) リージョンで稼働中
- **目標**: ap-northeast-1 (東京) リージョンへ移行
- **理由**: 日本ユーザー向けのレイテンシー改善（150-200ms → 20-30ms）
- **優先度**: **高** - 商用利用開始前に必ず実施

### パフォーマンスへの影響
| 操作 | シドニー（現在） | 東京（移行後） | 体感差 |
|-----|----------------|--------------|--------|
| API応答 | 250ms | 30ms | ワンテンポの差 |
| ダッシュボード初期表示 | 1.5秒 | 0.2秒 | 明確に速い |
| リアルタイム音声処理 | 300ms遅延 | 40ms遅延 | 大幅改善 |
| iOSアプリ操作 | もっさり | サクサク | UX大幅向上 |

### 移行作業の概要（所要時間: 4-5時間）
1. **影響範囲**: EC2インスタンス + ECR（13リポジトリ）
2. **影響なし**: Supabase（DB）、S3（ストレージ）は独立
3. **設定変更**: 39ファイルで `ap-southeast-2` → `ap-northeast-1` 変更
4. **AWSクレジット**: $300クレジットは継続利用可能

### 移行チェックリスト
```bash
□ 東京リージョンにECRリポジトリ作成（15個に増加）
  - 既存13個
  - 新規: watchme-api-ast
  - 新規: watchme-api-superb
□ Dockerイメージを東京ECRへコピー
□ 東京にEC2インスタンス作成（t4g.large）
□ 全設定ファイルのリージョン変更
□ DNS切り替え
□ 動作確認後、シドニー環境停止
```

**📅 実施時期**: 顧客がいない今のうちに早急に実施推奨（2025年9月中）

### ✅ 2025年9月19日 修正完了事項

**ポート設定の修正が完了しました：**

1. **AST API - 正常稼働中**
   - ポート: 8017（統一）
   - docker-compose.prod.ymlでポートマッピング: `127.0.0.1:8017:8017`
   - Nginx: `/behavior-features/` → `localhost:8017`
   - ディレクトリ: `/home/ubuntu/api_ast/`

2. **SUPERB API - 正常稼働中**
   - ポート: 8018
   - Nginx: `/emotion-features/` → `localhost:8018`
   - ディレクトリ: `/home/ubuntu/api_superb_v1/`

**東京リージョン移行時の注意：**
- AST APIは内部・外部ともに8017を使用
- SUPERB APIは内部・外部ともに8018を使用
- この設定で統一されています

## 🖥️ サーバーインフラ構成 【重要】

### AWS EC2インスタンス仕様
- **インスタンスタイプ**: t4g.large (一時的にアップグレード済み、以前はt4g.small)
- **CPU**: 2 vCPU (AWS Graviton2 Processor - Neoverse-N1)
- **メモリ**: 8.0GB RAM (実使用可能: 7.8GB)
- **ストレージ**: 30GB gp3 SSD
- **ネットワーク**: 最大 5 Gigabit
- **リージョン**: ap-southeast-2 (Sydney)
- **更新日**: 2025-09-19 (t4g.smallからt4g.largeへアップグレード)

### ⚠️ **リソース状況（t4g.largeへアップグレード後）**

**メモリ状況（大幅改善）**:
- **総メモリ**: 7.8GB (OS込み)
- **以前の使用量**: ~1.4GB (t4g.small時代は78%使用率)
- **Swap**: 2.0GB (必要に応じて調整可能)
- **利用可能**: 6GB以上（余裕あり）
- **注意**: 将来t4g.smallに戻す可能性あり

**Whisper API メモリ使用状況**:
- **アイドル時**: ~580MB (メモリ制限1GB中 57%使用)
- **処理中**: 800MB-1GB（制限値まで使用）
- **⚠️ 重要**: baseモデルでも580MB必要、largeモデルは不可

### 💡 メモリ管理のベストプラクティス

1. **新しいコンテナ追加時の必須チェック**:
   ```bash
   # メモリ使用量確認
   docker stats --no-stream
   free -h
   
   # 必要に応じてメモリ制限設定
   docker run --memory="500m" --cpus="0.5" ...
   ```

2. **メモリ不足時の対応手順**:
   ```bash
   # 不要なコンテナを一時停止
   docker stop <低優先度コンテナ>
   
   # Dockerリソースクリーンアップ
   docker system prune -f
   docker image prune -a -f
   ```

## ⚠️ 重要な理解事項

**このリポジトリの役割：**
- ✅ **Dockerネットワークインフラの一元管理** ← NEW!
- ✅ Nginx/systemd設定ファイルのテンプレートと変更履歴の管理
- ✅ ネットワーク監視・自動修復スクリプトの提供 ← NEW!
- ✅ Pull Requestによるレビュープロセスの実施
- ✅ **インフラリソース管理と制約情報** ← NEW!
- ❌ **本番サーバーへの自動デプロイ機能はありません**

**本番環境への反映方法：**
1. このリポジトリで設定を変更し、Pull Requestでレビュー
2. マージ後、**手動で**本番サーバーの設定ファイルを更新
3. 本番サーバー上の設定は `/home/ubuntu/watchme-server-configs/` に配置

## 📚 ドキュメント構成

| ドキュメント | 内容 | 読者 |
|------------|------|------|
| **[PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md)** | 🆕 音声処理の全体フロー、API依存関係、データの流れ | 開発者・設計者 |
| **[OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md)** | デプロイ手順、トラブルシューティング、日常運用 | 開発者・運用担当 |
| **[TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md)** | システム仕様、ネットワーク設計、API一覧 | エンジニア |
| **[CHANGELOG.md](./CHANGELOG.md)** | 全変更履歴（時系列） | 全員 |

## 📁 リポジトリ構造

```
watchme-server-configs/
├── docker-compose.infra.yml    # ネットワークインフラ定義
├── docker-compose-files/        # 各サービスのdocker-compose設定
│   ├── api-gpt-v1-docker-compose.prod.yml
│   ├── api-sed-aggregator-docker-compose.prod.yml
│   ├── mood-chart-api-docker-compose.prod.yml
│   ├── opensmile-api-docker-compose.prod.yml
│   ├── opensmile-aggregator-docker-compose.prod.yml
│   ├── sed-api-docker-compose.prod.yml
│   ├── vibe-transcriber-v2-docker-compose.prod.yml
│   ├── watchme-admin-docker-compose.prod.yml
│   └── watchme-web-docker-compose.prod.yml
├── systemd/                     # systemdサービスファイル（全13サービス）
│   ├── watchme-infrastructure.service  # インフラ管理サービス
│   ├── api-gpt-v1.service
│   ├── api-sed-aggregator.service
│   ├── mood-chart-api.service
│   ├── opensmile-api.service
│   ├── opensmile-aggregator.service
│   ├── vibe-transcriber-v2.service
│   ├── watchme-admin.service
│   ├── watchme-api-manager.service
│   ├── watchme-avatar-uploader.service
│   ├── watchme-behavior-yamnet.service
│   ├── watchme-vault-api.service
│   ├── watchme-web-app.service
│   └── watchme-docker.service
├── sites-available/             # Nginx設定ファイル
│   └── api.hey-watch.me
├── scripts/                     # 管理・監視スクリプト
│   ├── check-infrastructure.sh # ネットワークヘルスチェック
│   └── network_monitor.py      # Python監視ツール
├── README.md                    # このファイル
├── NETWORK-ARCHITECTURE.md     # ネットワーク設計文書
└── server_overview.md          # サーバー全体構成
```

---

## 🌐 ネットワークインフラストラクチャ管理【NEW!】

### watchme-networkの概要

**watchme-network** は、全マイクロサービスが相互通信するための共有Dockerネットワークです。

- **サブネット**: 172.27.0.0/16
- **ゲートウェイ**: 172.27.0.1
- **管理者**: watchme-infrastructure service
- **作成日**: 2025年8月6日

### 現在の接続状況（2025年9月19日更新）

#### ⚠️ 重要：音声処理APIの置き換え（2025年9月19日）

**従来のAPI（廃止予定）:**
- `sed-api` (ポート8004) → **AST APIに置き換え**
- `opensmile-api` (ポート8011) → **SUPERB APIに置き換え**

**新しいAPI構成:**
- **AST API** (ポート8017): Audio Spectrogram Transformer - 527種類の音響イベント検出
- **SUPERB API** (ポート8018): wav2vec2ベースの感情認識 - OpenSMILE互換

#### ✅ 接続済みコンテナ（15個） - 新API追加後の構成
```
watchme-api-manager-prod     (172.27.0.4)  # API管理UI
watchme-scheduler-prod       (172.27.0.5)  # スケジューラー
opensmile-aggregator         (172.27.0.6)  # 感情スコア集計
watchme-vault-api            (172.27.0.7)  # Gateway API
api_gen_prompt_mood_chart    (172.27.0.8)  # Vibe Aggregator
api-gpt-v1                   (172.27.0.9)  # スコアリング
watchme-web-prod             (172.27.0.10) # Webダッシュボード
vibe-transcriber-v2          (172.27.0.11) # Azure Speech
ast-api                      (172.27.0.17) # 音声イベント検出（新）※8017ポート
superb-api                   (172.27.0.18) # 感情認識（新）※8018ポート
watchme-admin                (172.27.0.14) # 管理画面
api-sed-aggregator           (172.27.0.15) # 音声イベント集計
watchme-avatar-uploader      (172.27.0.16) # アバターアップロード

# 廃止予定（移行後削除）
sed-api                      (172.27.0.12) # 旧音声イベント検出 → AST APIへ移行
opensmile-api                (172.27.0.13) # 旧音声特徴量抽出 → SUPERB APIへ移行
```

#### 💡 システム状態（2025年9月5日時点）
- **全13サービスがsystemd管理下で稼働**
- **サーバー再起動時の自動起動を保証**
- **全ポートが127.0.0.1にバインド（セキュリティ向上）**
- **ディスク使用率: 50%（14GB/29GB）** - クリーンアップで6GB削減

### 段階的移行計画

#### Phase 1: インフラ整備（✅ 完了）
- docker-compose.infra.yml作成
- 監視スクリプト配置
- systemdサービス定義

#### Phase 2: 問題修正（✅ 完了）
- api_gen_prompt_mood_chart を watchme-network に接続
- watchme-vault-api を自動修復

#### Phase 3: systemd移行（✅ 2025/09/03 完了）
- opensmile-api: systemd管理に移行完了
- opensmile-aggregator: systemd管理に移行完了
- api-sed-aggregator: systemd管理に移行完了
- vibe-transcriber-v2: systemd新規作成・移行完了

#### Phase 4: ネットワーク統合（✅ 2025/09/04 完了）

**実施内容**:
- レガシーネットワーク4個を削除
  - api_sed_v1_default
  - watchme-api-manager_watchme-network  
  - watchme-docker_watchme-network
  - watchme-vault-api-docker_vault-network
- 全サービスがwatchme-networkに統合完了

**修正したサービス**:
- ✅ `/home/ubuntu/watchme-docker/docker-compose.prod.yml` - external: trueに修正済み
- ✅ watchme-api-manager systemd設定 - docker-compose.all.yml → docker-compose.prod.ymlに修正

### インフラ管理コマンド

```bash
# ネットワーク状態の確認
bash /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh

# Python監視ツールで詳細確認
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py

# 自動修復モードで実行
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix

# JSON形式で出力
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --json
```

### 自動監視設定（推奨）

```bash
# Cronジョブ設定（5分ごとに自動チェック）
crontab -e
*/5 * * * * /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh
```

---

## 1. 設計思想：2層のルーティングを理解する【最重要】

このサーバーの構成を理解する上で最も重要なのは、Nginxによる**「2層のルーティング」**の概念です。ここを理解しないと、過去に発生したような障害が再発します。

**ホテルの受付**に例えてみましょう。

1.  **公開URL (`location`)**: お客様が知っている部屋番号 (例: **201号室**)
    - これは `location /scheduler/` のような、外部に公開されるクリーンなURLパスです。

2.  **内部パス (`proxy_pass`)**: スタッフだけが知っている実際の部屋の場所 (例: **A棟3階の奥**)
    - これは `proxy_pass http://localhost:8015/api/scheduler/` のような、コンテナ内部でアプリケーションが実際にリクエストを待っているパスです。

フロント（受付）にいるNginxの仕事は、お客様の「**201号室**に行きたい」というリクエストを、スタッフ用の「**A棟3階の奥**へご案内」という指示に正しく変換することです。

### ⚠️最大の注意点：`proxy_pass` の挙動

Nginxでは、`proxy_pass` にパス（例: `/api/scheduler/`）を指定すると、`location` のパス（`/scheduler/`）が**置き換えられます**。

**過去の障害事例：**

- **ブラウザのリクエスト**: `https://.../scheduler/status/whisper`

- **間違っていた設定**: `proxy_pass http://localhost:8015/;`
  - `/scheduler/` が `/` に置き換えられ、転送先は `http://...:8015/status/whisper` となり、404エラーが発生した。

- **正しい設定**: `proxy_pass http://localhost:8015/api/scheduler/;`
  - `/scheduler/` が `/api/scheduler/` に置き換えられ、転送先は `http://...:8015/api/scheduler/status/whisper` となり、正常にAPIが応答した。

**新しいサービスを追加する際は、必ずこの「公開URL」と「内部パス」の2つを意識してください。**

### 1.1. ファイル構造の不一致に注意 (フロントエンドアプリ)

Reactなどのフレームワークでは、ビルド設定（例: `vite.config.js` の `base` オプション）によって、生成される `index.html` 内のJS/CSSへのパスに `/manager/` のようなプレフィックスが付くことがあります。

しかし、Dockerコンテナ内のWebサーバー（Nginx）から見ると、これらのファイルはルートからの相対パス (`/assets/...`) に配置されています。この**「ビルドが作るパス」**と**「コンテナ内の実際のパス」**の不一致を吸収するために、各アプリケーションのコンテナ内に、専用のNginx設定が必要になる場合があります。

新しいフロントエンドをデプロイする際は、ビルド後のパス構造をよく確認し、必要であればそのアプリの `Dockerfile` と `nginx.conf` も調整してください。

---

## 2. 運用ルールと作業フロー【推奨】

このリポジトリの設定を本番サーバーに反映させるための、推奨ワークフローです。
**サーバー上のファイルを直接編集するのではなく、常にこのGitリポジリを起点として作業を行ってください。**

### サーバーへの初回セットアップ手順

新しいEC2サーバーを構築した際に、最初に一度だけ実行する手順です。

1.  **リポジトリをクローン**
    ```bash
    # EC2サーバーにSSH接続
    ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

    # 適切な場所にリポジトリをクローン
    cd /home/ubuntu
    git clone git@github.com:matsumotokaya/watchme-server-configs.git
    ```

2.  **初期設定スクリプトを実行**
    ```bash
    # クローンしたディレクトリに移動
    cd /home/ubuntu/watchme-server-configs

    # スクリプトに実行権限を付与
    chmod +x setup_server.sh

    # 初期設定スクリプトを実行
    ./setup_server.sh
    ```
    これにより、リポジトリ内のすべてのNginxおよびsystemdの設定が、OSの適切な場所に自動でリンクされ、サービスが有効化されます。

### 設定変更時のデプロイ手順

一度セットアップが完了したサーバーで、Nginxやsystemdの設定を変更・追加する際の標準的な手順です。

1.  **ローカルで変更作業**
    - ローカルPCでこのリポジトリを修正し、GitHub上でPull Requestを作成・マージします。

2.  **本番サーバーで変更を反映**
    ```bash
    # EC2サーバーにSSH接続
    ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

    # リポジトリのディレクトリに移動
    cd /home/ubuntu/watchme-server-configs

    # 最新の変更を取得
    git pull origin main

    # セットアップスクリプトを再実行して、変更を自動で適用
    ./setup_server.sh
    ```
    `setup_server.sh`は何度実行しても安全です。新しいファイルはリンクを作成し、既存のファイルはリンクを更新し、最後に各種サービスをリロードして変更を完全に適用します。

---

### 緊急時の手動復旧手順（非推奨）

万が一、上記の方法が使えない場合にのみ、以下の手動手順で作業を行ってください。作業ミスを防ぐため、可能な限り`setup_server.sh`の使用を推奨します。

```bash
# 1. 現在の設定をバックアップ（必須！）
sudo cp /etc/nginx/sites-available/api.hey-watch.me \
        /etc/nginx/sites-available/api.hey-watch.me.backup.$(date +%Y%m%d_%H%M%S)

# 2. 設定ファイルを編集（このリポジトリの内容を参考に手動で編集）
sudo nano /etc/nginx/sites-available/api.hey-watch.me

# 3. 文法テスト（最重要）
sudo nginx -t

# 4. エラーがなければリロード
sudo systemctl reload nginx
```

---

## 3. テンプレート：新しいAPIサービスの追加

新しいAPIサービスを追加する際は、以下の**3つの設定**が必要です。

### ⓪ 【最重要】Docker Composeでネットワーク設定

**必ず** docker-compose.yml に以下のネットワーク設定を追加してください：

```yaml
version: '3.8'

services:
  your-service:
    # ... サービス設定 ...
    networks:
      - watchme-network  # 必須！

networks:
  watchme-network:
    external: true  # 必ず external: true を使用
```

⚠️ **注意**: `driver: bridge` は使用しないでください（ネットワーク作成側になってしまいます）

### ① Nginx設定の追加

`sites-available/api.hey-watch.me` ファイルに、以下のブロックを追記します。

```nginx
# [サービス名] API
location /[公開URLパス]/ {
    # 注意: パスの最後にスラッシュを付けること

    # 内部のAPIがリッスンしているポートとパスを指定
    # パスがない場合は http://localhost:[ポート番号]/ でOK
    proxy_pass http://localhost:[ポート番号]/[内部APIパス]/;

    # --- 以下は定型句 ---
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # CORS設定（必要に応じて）
    add_header "Access-Control-Allow-Origin" "*";
    add_header "Access-Control-Allow-Methods" "GET, POST, OPTIONS";
    add_header "Access-Control-Allow-Headers" "Content-Type, Authorization";
    
    # OPTIONSリクエストの処理（必要に応じて）
    if ($request_method = "OPTIONS") {
        return 204;
    }
}
```

#### 実例：Avatar Uploader APIの追加

```nginx
# Avatar Uploader API
location /avatar/ {
    proxy_pass http://localhost:8014/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # CORS設定
    add_header "Access-Control-Allow-Origin" "*";
    add_header "Access-Control-Allow-Methods" "GET, POST, DELETE, OPTIONS";
    add_header "Access-Control-Allow-Headers" "Content-Type, Authorization";
    
    # OPTIONSリクエストの処理
    if ($request_method = "OPTIONS") {
        return 204;
    }
    
    # ファイルアップロード用の設定
    client_max_body_size 10M;  # 10MBまでの画像アップロードを許可
}
```

### ② systemdサービスファイルの作成

`systemd/` ディレクトリに、`[サービス名].service` という名前で新しいファイルを作成します。

```ini
[Unit]
Description=[サービスの説明]
After=docker.service watchme-infrastructure.service  # インフラの後に起動
Requires=docker.service watchme-infrastructure.service

[Service]
TimeoutStartSec=0

# 常にECRから最新のイメージを取得
ExecStartPre=-/usr/bin/docker-compose -f [docker-compose.prod.ymlへの絶対パス] pull -q

# Docker Composeでコンテナを起動
ExecStart=/usr/bin/docker-compose -f [docker-compose.prod.ymlへの絶対パス] up

# サービス停止時にコンテナを停止
ExecStop=/usr/bin/docker-compose -f [docker-compose.prod.ymlへの絶対パス] down

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3.2. コンテナ間通信のルール

サービスAのコンテナから、サービスBのコンテナのAPIを呼び出すなど、コンテナ間で通信を行う場合は、**ホスト名としてサービス名（コンテナ名）を使用してください。**

`host.docker.internal` や `localhost` は、環境によって挙動が異なるため、使用を避けるべきです。

**前提条件:**
- 通信する全てのサービスが、`docker-compose.yml` 内で同じ `networks` に所属していること。（例: `watchme-net`）

**実装例（Pythonの場合）:**
```python
# 例: 'vibe-transcriber-v2' という名前のコンテナにリクエストを送る
API_ENDPOINT = "http://vibe-transcriber-v2:8013/transcribe"
response = requests.post(API_ENDPOINT, json=data)
```

---

## 4. トラブルシューティング

### 🌐 ネットワーク関連の問題

#### 症状: APIコンテナ間の通信エラー
```
ERROR: API接続エラー - コンテナ名 'xxx' が解決できません
```

**解決方法：**
```bash
# 1. ネットワーク接続状態を確認
bash /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh

# 2. 自動修復を実行
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix

# 3. 手動で接続（必要な場合）
docker network connect watchme-network [container-name]
```

#### 症状: Vibe Aggregatorが動作しない

**確認手順：**
```bash
# cronログ確認
sudo tail -100 /var/log/scheduler/cron.log | grep vibe-aggregator

# コンテナログ確認
docker logs api_gen_prompt_mood_chart --tail 50

# 手動実行テスト
docker exec watchme-scheduler-prod python /app/run-api-process-docker.py vibe-aggregator --date 2025-08-28
```

### 💾 メモリ不足関連の問題 【2025年8月30日追加】

#### 症状: Dockerイメージプル/コンテナ起動時の "no space left on device"
```
failed to register layer: write /usr/lib/aarch64-linux-gnu/libLLVM.so.19.1: no space left on device
```

**根本原因**: ディスク容量不足（95%以上使用）
**解決手順**:
```bash
# 1. 現在のディスク使用状況確認
df -h

# 2. Dockerリソース大量クリーンアップ
sudo docker container prune -f    # 停止コンテナ削除
sudo docker image prune -a -f     # 未使用イメージ削除
sudo docker volume prune -f       # 未使用ボリューム削除
sudo docker system prune -a -f    # 包括的クリーンアップ

# 3. 効果確認
df -h  # 10GB以上削減されることを確認
```

#### 症状: コンテナが起動するがすぐに停止する（メモリ不足）
```bash
# コンテナが見つからない、またはステータスがExited (137)
```

**根本原因**: メモリ使用量が制限を超過（OOM Killer作動）
**解決手順**:
```bash
# 1. メモリ使用状況確認
docker stats --no-stream
free -h

# 2. 重要度の低いコンテナを一時停止
docker stop opensmile-aggregator api-sed-aggregator

# 3. メモリ制限付きで起動（例）
docker run -d --name [container-name] \
  --network watchme-network \
  -p [port]:[port] \
  --memory="1g" --cpus="1.0" \  # リソース制限重要
  --env-file /path/to/.env \
  --restart unless-stopped \
  [IMAGE_URI]
```

#### 症状: ECR認証エラー "authorization token has expired"
```
pull access denied ... may require 'docker login': denied: Your authorization token has expired
```

**解決手順**:
```bash
# ECRに再ログイン
aws ecr get-login-password --region ap-southeast-2 | \
  sudo docker login --username AWS --password-stdin \
  754724220380.dkr.ecr.ap-southeast-2.amazonaws.com
```

### 🔧 Nginx関連の問題

#### 症状: 502 Bad Gateway エラー
外部からAPIアクセス時に502エラーが発生する場合の診断手順：

1. **コンテナの生存確認**
   ```bash
   # コンテナが実際に動作しているか確認
   docker ps | grep [コンテナ名]
   
   # 内部からの直接アクセステスト
   curl http://localhost:[ポート]/
   ```

2. **Nginx設定の確認（最重要）**
   ```bash
   # 現在の設定を確認
   grep -A 5 "location /[API名]/" /etc/nginx/sites-available/api.hey-watch.me
   
   # ⚠️ よくある間違い：
   # 例： proxy_pass http://localhost:[port]/;  # Nginxがホスト上にある場合
   # 例： proxy_pass http://[container-name]:[port]/;  # Nginxがコンテナの場合
   ```
   
   **重要**: Nginxがホスト上で直接動作している場合は`localhost`が正しい

3. **ポートマッピングの確認**
   ```bash
   # ポートが正しくマッピングされているか確認
   sudo lsof -i:[ポート番号]
   docker port [コンテナ名]
   ```

4. **Nginxログ確認**
   ```bash
   sudo tail -n 50 /var/log/nginx/error.log
   sudo tail -n 50 /var/log/nginx/access.log | grep "[API名]"
   ```

#### その他のNginx問題

404エラーなどの問題が発生した場合、以下の手順で問題を切り分けてください。

1.  **APIは生きているか？ (サーバー内部から確認)**
    - サービスがダウンしているのが原因かもしれません。まず、サーバー内部から直接APIを叩いてみます。
    ```bash
    # 1. ポート番号を確認
    sudo lsof -i:[ポート番号]

    # 2. 内部から直接curlで叩く
    curl http://localhost:[ポート番号]/[内部APIパス]/[任意のエンドポイント]
    ```
    - ここで応答がなければ、問題はNginxではなく、APIアプリケーション自体にあります。サービスのログを確認してください。

2.  **Nginxのログは何か言っているか？**
    - APIが生きているのにエラーが出る場合、Nginxのログにヒントがあるはずです。
    ```bash
    # エラーログの最新50行を確認
    sudo tail -n 50 /var/log/nginx/error.log

    # アクセスログで、該当のリクエストがどのように記録されているか確認
    sudo tail -n 50 /var/log/nginx/access.log | grep "[公開URLパス]"
    ```

3.  **設定は正しくリロードされているか？**
    - 設定ファイルを変更した後は、`sudo nginx -t` でテストし、`sudo systemctl reload nginx` を実行したか再確認してください。単純なリロード忘れもよくある原因です。

---

## 📊 現在稼働中のサービス一覧（2025年9月19日更新）

### 音声処理API群

| サービス名 | ポート | 用途 | Nginxパス | コンテナ名 | 状態 |
|-----------|--------|------|----------|-----------|------|
| **AST API** | 8017 | 音響イベント検出（527種類） | /behavior-features/ | ast-api | ✅ 稼働中 |
| **SUPERB API** | 8018 | 感情認識（8感情） | /emotion-features/ | superb-api | ✅ 稼働中 |
| Whisper API | 8013 | 音声文字起こし | /vibe-transcriber/ | vibe-transcriber-v2 | ✅ 稼働中 |
| ~~SED API~~ | ~~8004~~ | ~~音響イベント検出~~ | - | - | ❌ 廃止（AST APIへ移行） |
| ~~OpenSMILE API~~ | ~~8011~~ | ~~感情特徴量抽出~~ | - | - | ❌ 廃止（SUPERB APIへ移行） |

### 集計・分析API群

| サービス名 | ポート | 用途 | Nginxパス | コンテナ名 | 状態 |
|-----------|--------|------|----------|-----------|------|
| Vibe Aggregator | 8009 | プロンプト生成 | /vibe-aggregator/ | api_gen_prompt_mood_chart | ✅ 稼働中 |
| Vibe Scorer | 8002 | 心理スコア生成 | /vibe-scorer/ | api-gpt-v1 | ✅ 稼働中 |
| SED Aggregator | 8010 | 音声イベント集計 | /behavior-aggregator/ | api-sed-aggregator | ✅ 稼働中 |
| OpenSMILE Aggregator | 8012 | 感情スコア集計 | /emotion-aggregator/ | opensmile-aggregator | ✅ 稼働中 |

### インフラ・管理系

| サービス名 | ポート | 用途 | Nginxパス | コンテナ名 | 状態 |
|-----------|--------|------|----------|-----------|------|
| Vault API | 8000 | ファイル管理Gateway | /vault/ | watchme-vault-api | ✅ 稼働中 |
| API Manager | 9001 | API管理UI | /manager/ | watchme-api-manager-prod | ✅ 稼働中 |
| Scheduler | 8015 | スケジューラー | /scheduler/ | watchme-scheduler-prod | ✅ 稼働中 |
| Admin Panel | 9000 | 管理画面 | /admin/ | watchme-admin | ✅ 稼働中 |
| Web Dashboard | 3001 | ダッシュボード | / | watchme-web-prod | ✅ 稼働中 |
| Avatar Uploader | 8014 | アバター管理 | /avatar/ | watchme-avatar-uploader | ✅ 稼働中 |

### メモリ使用状況（概算）

| カテゴリ | サービス | メモリ使用量 |
|----------|----------|--------------|
| 重量級 | AST API | ~2.0GB |
| | SUPERB API | ~1.5GB |
| | Whisper API | ~1.0GB |
| 中量級 | 各種Aggregator | ~500MB each |
| 軽量級 | Web/Admin UI | ~200MB each |
| **合計** | | **約6.5GB / 7.8GB** |

## 5. よくある質問とベストプラクティス

### Q: watchme-networkとは何ですか？

**A: 全マイクロサービス間の通信を可能にするDockerの仮想ネットワークです。**
- 172.27.0.0/16のプライベートIPアドレス空間
- コンテナ名でのDNS解決が可能
- 外部からはアクセス不可（セキュア）
- `docker-compose.infra.yml`で一元管理

### Q: 新しいAPIがネットワークに繋がらない！

**A: docker-compose.ymlの設定を確認してください：**
```yaml
networks:
  watchme-network:
    external: true  # これが必須！
```

エラーが続く場合：
```bash
# 監視スクリプトで自動修復
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix
```

### Q: API ManagerとSchedulerはどのように管理されている？

**A: 現在は1つのdocker-compose.all.ymlで両方を管理しています。**
- **API Manager (UI)**: ポート9001で稼働
- **Scheduler**: ポート8015で稼働
- **重要**: systemdは`docker-compose.all.yml`を使用（両方起動）
- **注意**: `docker-compose.prod.yml`は使用しない（API Managerのみ起動してしまう）

**今後の改善案**（検討中）:
- 2つのサービスを独立したディレクトリに分離
- それぞれ独自のdocker-compose.prod.ymlを持つ
- systemdサービスも2つに分離

### Q: このリポジトリの設定ファイルをそのまま本番にコピーすればいい？

**A: いいえ、直接コピーはできません。**
- このリポジトリはテンプレートと変更履歴の管理用です
- 本番サーバーには既に動作中の設定があり、それを参考に**手動で編集**する必要があります
- 必ず現在の設定をバックアップしてから編集してください

### Q: なぜ本番サーバーにこのリポジトリをクローンしないの？

**A: セキュリティとシンプルさのため。**
- 本番サーバーに不要なGitリポジトリを置かない
- 設定ファイルは`/etc/`配下に直接存在するのが標準的
- 変更履歴はこのGitHubリポジトリで管理

### Q: 新しいAPIを追加する時の手順は？

**A: 以下の手順で進めます：**
1. このリポジトリで新しいブランチを作成
2. `sites-available/api.hey-watch.me`にlocation設定を追加
3. Pull Requestを作成してレビュー
4. マージ後、本番サーバーで手動で同じ設定を追加
5. `sudo nginx -t`でテスト → `sudo systemctl reload nginx`

### Q: Whisper APIのメモリ使用量が心配です。今後どうすべき？

**A: 【重要】現在のt4g.smallでは限界に近い状況です。**

**現在の状況**:
- Whisper API: 580MB (アイドル時) → 1GB (処理時)
- 全システム: 1.4GB/1.8GB使用 (78%使用率)
- 利用可能: 約400MB未満

**今後の選択肢**:

1. **短期的解決策（現状維持）**:
   - baseモデルのみ使用継続
   - 必要時に低優先度コンテナを一時停止
   - リソース制限の厳格化

2. **中長期的解決策（推奨）**:
   - **t4g.medium** (4GB RAM) へのアップグレード検討
   - **t4g.large** (8GB RAM) なら複数のWhisperモデル同時実行可能
   - コスト: t4g.small ($13.3/月) → t4g.medium ($26.6/月)

3. **代替案**:
   - OpenAI Whisper API (外部サービス) への移行
   - Whisper処理を別サーバーに分離

**⚠️ 注意**: largeモデルは現在の環境では動作不可（2GB以上必要）

### Q: 設定を間違えてサービスが落ちた！

**A: バックアップから復元：**
```bash
# バックアップファイルを探す
ls -la /etc/nginx/sites-available/*.backup.*

# 最新のバックアップから復元
sudo cp /etc/nginx/sites-available/api.hey-watch.me.backup.[最新のタイムスタンプ] \
        /etc/nginx/sites-available/api.hey-watch.me

# テストとリロード
sudo nginx -t && sudo systemctl reload nginx
```

### Q: スケジューラーが動かなくなった！

**A: よくある原因と解決方法：**

**原因1: docker-compose.prod.ymlを使ってしまった**
```bash
# 診断: スケジューラーコンテナが存在しない
docker ps | grep scheduler
# 何も表示されない場合

# 解決方法:
cd /home/ubuntu/watchme-api-manager
docker-compose -f docker-compose.all.yml up -d
```

**原因2: ネットワーク設定の誤り**
```bash
# docker-compose.all.ymlの最後を確認
tail -5 docker-compose.all.yml
# external: trueであることを確認（driver: bridgeはNG）
```

### Q: どのポートが使われているか確認したい

**A: 以下のコマンドで確認：**
```bash
# 使用中のポート一覧
sudo lsof -i -P -n | grep LISTEN

# 特定のポートを確認
sudo lsof -i:8014

# Nginxの設定で使用しているポートを確認
grep -E "proxy_pass|listen" /etc/nginx/sites-available/api.hey-watch.me
```

## 🛠️ メンテナンス用コマンド集（2025年9月19日追加）

### サービス状態確認
```bash
# 全コンテナの状態確認
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"

# メモリ使用状況
docker stats --no-stream

# ネットワーク接続確認
docker network inspect watchme-network | jq '.[0].Containers | keys'
```

### AST APIの管理
```bash
# 再起動
cd /home/ubuntu/api_ast && docker-compose restart

# ログ確認
docker logs ast-api --tail 50 -f

# ヘルスチェック
curl http://localhost:8017/health
```

### SUPERB APIの管理
```bash
# 再起動
cd /home/ubuntu/api_superb_v1 && docker-compose restart

# ログ確認
docker logs superb-api --tail 50 -f

# ヘルスチェック
curl http://localhost:8018/health
```

### トラブル時の緊急対応
```bash
# メモリ逼迫時（優先度の低いサービスを停止）
docker stop api-sed-aggregator opensmile-aggregator

# ディスク容量不足時
docker system prune -a -f
docker image prune -a -f

# ネットワーク問題時
python3 /home/ubuntu/watchme-server-configs/scripts/network_monitor.py --fix
```

### ベストプラクティス

1. **ネットワーク設定を最優先** 🆕
   - 新しいサービスは必ず`watchme-network`に`external: true`で参加
   - デプロイ後は`check-infrastructure.sh`で接続確認
   - 問題があれば`network_monitor.py --fix`で自動修復

2. **常にバックアップを取る**
   - 設定変更前に必ず`backup.$(date +%Y%m%d_%H%M%S)`形式でバックアップ

3. **段階的にテスト**
   - まず`nginx -t`で文法チェック
   - 次に`curl`で内部から動作確認
   - 最後に外部からHTTPS経由で確認

4. **ドキュメント化**
   - 新しいサービスを追加したら、このREADMEも更新
   - server_overview.mdにもエンドポイント情報を追加
   - NETWORK-ARCHITECTURE.mdに接続状態を記録 🆕

5. **ポート番号の管理**
   - 8000番台: メインAPI
   - 8001-8099: マイクロサービス
   - 9000番台: 管理ツール
   - 新しいサービスは既存のポートと重複しないよう確認

## 🚀 今後の予定

- [ ] 既存サービスの統一ネットワーク移行完了
- [ ] 監視ダッシュボードの構築
