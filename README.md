# WatchMe サーバー設定リポジトリ

このリポジトリは、WatchMeプラットフォームのEC2サーバーで稼働する **インフラストラクチャ**、**Nginx**、**systemd** の設定を一元管理します。

## 🆕 2025年8月28日 重要アップデート

**watchme-networkのインフラ管理を集約化しました！**
- ✅ ネットワーク管理が `docker-compose.infra.yml` に一元化
- ✅ 自動監視・修復システムが稼働中
- ✅ 全APIサービスの接続状態を5分ごとに自動チェック

詳細は [NETWORK-ARCHITECTURE.md](./NETWORK-ARCHITECTURE.md) を参照してください。

## ⚠️ 重要な理解事項

**このリポジトリの役割：**
- ✅ **Dockerネットワークインフラの一元管理** ← NEW!
- ✅ Nginx/systemd設定ファイルのテンプレートと変更履歴の管理
- ✅ ネットワーク監視・自動修復スクリプトの提供 ← NEW!
- ✅ Pull Requestによるレビュープロセスの実施
- ❌ **本番サーバーへの自動デプロイ機能はありません**

**本番環境への反映方法：**
1. このリポジトリで設定を変更し、Pull Requestでレビュー
2. マージ後、**手動で**本番サーバーの設定ファイルを更新
3. 本番サーバー上の設定は `/home/ubuntu/watchme-server-configs/` に配置

## 📚 ドキュメント構成

| ドキュメント | 内容 | 対象読者 |
|------------|------|---------|
| **[README.md](./README.md)** | 全体概要、デプロイ手順、運用ルール | 全員 |
| **[NETWORK-ARCHITECTURE.md](./NETWORK-ARCHITECTURE.md)** 🆕 | ネットワーク設計、移行計画、トラブルシューティング | インフラ/DevOps担当 |
| **[server_overview.md](./server_overview.md)** | サーバー構成、API一覧、エンドポイント詳細 | API開発者 |

## 📁 リポジトリ構造

```
watchme-server-configs/
├── docker-compose.infra.yml    # 🆕 ネットワークインフラ定義
├── systemd/                     # systemdサービスファイル
│   ├── watchme-infrastructure.service  # 🆕 インフラ管理サービス
│   ├── watchme-api-manager.service
│   └── ...
├── sites-available/             # Nginx設定ファイル
│   └── api.hey-watch.me
├── scripts/                     # 🆕 管理・監視スクリプト
│   ├── check-infrastructure.sh # ネットワークヘルスチェック
│   └── network_monitor.py      # Python監視ツール
├── README.md                    # このファイル
├── NETWORK-ARCHITECTURE.md     # 🆕 ネットワーク設計文書
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

### 現在の接続状況（2025年8月28日時点）

#### ✅ 接続済みコンテナ（13個）
```
watchme-scheduler-prod       (172.27.0.2)  # APIスケジューラー
api-transcriber              (172.27.0.3)  # Whisper書き起こし
watchme-api-manager-prod     (172.27.0.4)  # API管理UI
opensmile-aggregator         (172.27.0.5)  # 感情スコア集計
watchme-vault-api            (172.27.0.6)  # Gateway API
api_gen_prompt_mood_chart    (172.27.0.7)  # Vibe Aggregator ← 修正済み
api-gpt-v1                   (172.27.0.8)  # スコアリング
watchme-web-prod             (172.27.0.9)  # Webダッシュボード
vibe-transcriber-v2          (172.27.0.10) # Azure Speech
api_sed_v1-sed_api-1         (172.27.0.11) # 音声イベント検出
opensmile-api                (172.27.0.12) # 音声特徴量抽出
watchme-admin                (172.27.0.13) # 管理画面
api-sed-aggregator           (172.27.0.14) # 音声イベント集計
```

### 段階的移行計画

#### Phase 1: インフラ整備（✅ 完了）
- docker-compose.infra.yml作成
- 監視スクリプト配置
- systemdサービス定義

#### Phase 2: 問題修正（✅ 完了）
- api_gen_prompt_mood_chart を watchme-network に接続
- watchme-vault-api を自動修復

#### Phase 3: 既存サービスの移行（🔄 進行中）

**移行が必要なサービス**:
各サービスの `docker-compose.yml` を以下のように修正する必要があります。

```yaml
# 現在（ネットワーク作成側）
networks:
  watchme-network:
    driver: bridge  # ❌ これが問題

# 修正後（ネットワーク利用側）
networks:
  watchme-network:
    external: true  # ✅ 既存ネットワークを利用
```

**優先度順の移行対象**:
1. ⚠️ `/home/ubuntu/api_whisper_v1/docker-compose.prod.yml`
2. ⚠️ `/home/ubuntu/watchme-docker/docker-compose.prod.yml`
3. ⚠️ `/home/ubuntu/watchme-api-manager/docker-compose.prod.yml`

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

## 2. 運用ルールと作業フロー

### 変更手順

1.  ローカルでこのリポジトリをクローンし、新しいブランチを作成します。
2.  後述のテンプレートに従って、`sites-available/` または `systemd/` に設定ファイルを追加・修正します。
3.  変更をコミットし、GitHubにプッシュします。
4.  Pull Requestを作成し、他の開発者のレビューを受けます。

### デプロイ手順

Pull Requestがマージされた後、EC2サーバーにSSHで接続し、以下の作業を行います。

#### 📝 重要な前提知識
- **このリポジトリはEC2サーバー上にクローンされていません**
- 本番サーバーの設定ファイルは直接編集します（ただし、必ずバックアップを取る）
- 設定内容はこのリポジトリの`sites-available/`フォルダを参考にします

#### 実際のデプロイ手順

##### 1️⃣ EC2サーバーにSSH接続
```bash
# EC2サーバーに接続
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
```

##### 2️⃣ Nginxの設定を変更する場合

```bash
# 1. 現在の設定をバックアップ（必須！）
sudo cp /etc/nginx/sites-available/api.hey-watch.me \
        /etc/nginx/sites-available/api.hey-watch.me.backup.$(date +%Y%m%d_%H%M%S)

# 2. 設定ファイルを編集
#    このリポジトリのsites-available/api.hey-watch.meの内容を参考に編集
sudo nano /etc/nginx/sites-available/api.hey-watch.me

# 3. 文法テスト（最重要）
sudo nginx -t

# 4. エラーがなければリロード
sudo systemctl reload nginx

# 5. 動作確認
curl https://api.hey-watch.me/[追加したパス]/health
```

##### 3️⃣ systemdサービスを変更する場合

```bash
# 1. 現在のサービスファイルをバックアップ（存在する場合）
if [ -f /etc/systemd/system/your-service.service ]; then
    sudo cp /etc/systemd/system/your-service.service \
            /etc/systemd/system/your-service.service.backup.$(date +%Y%m%d_%H%M%S)
fi

# 2. サービスファイルを作成または編集
#    このリポジトリのsystemd/フォルダの内容を参考に作成
sudo nano /etc/systemd/system/your-service.service

# 3. systemdデーモンをリロード
sudo systemctl daemon-reload

# 4. サービスを有効化 & 起動
sudo systemctl enable --now your-service.service

# 5. 状態確認
sudo systemctl status your-service.service
```

#### 🔄 ロールバック手順

問題が発生した場合：

```bash
# Nginxの場合
sudo cp /etc/nginx/sites-available/api.hey-watch.me.backup.[タイムスタンプ] \
        /etc/nginx/sites-available/api.hey-watch.me
sudo nginx -t && sudo systemctl reload nginx

# systemdの場合
sudo cp /etc/systemd/system/your-service.service.backup.[タイムスタンプ] \
        /etc/systemd/system/your-service.service
sudo systemctl daemon-reload
sudo systemctl restart your-service.service
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
# 'api-transcriber' という名前のコンテナにリクエストを送る
API_ENDPOINT = "http://api-transcriber:8001/fetch-and-transcribe"
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

### 🔧 Nginx関連の問題

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

## 📝 変更履歴

| 日付 | 変更内容 | 影響範囲 |
|------|---------|---------|
| 2025-08-28 | watchme-networkインフラ管理システム導入 | 全サービス |
| 2025-08-28 | 監視・自動修復スクリプト追加 | 運用改善 |
| 2025-08-28 | api_gen_prompt_mood_chart接続問題修正 | Vibe Aggregator |
| 2025-08-28 | NETWORK-ARCHITECTURE.md作成 | ドキュメント |

## 🚀 今後の予定

- [ ] 既存サービスの`docker-compose.yml`を段階的に`external: true`へ移行
- [ ] レガシーネットワークの削除
- [ ] systemdによる起動順序の完全制御
- [ ] 監視ダッシュボードの構築
