# WatchMe サーバー設定リポジトリ

このリポジトリは、WatchMeプラットフォームのEC2サーバーで稼働する、**Nginx** と **systemd** の設定ファイルのテンプレートと変更履歴を管理します。

## ⚠️ 重要な理解事項

**このリポジトリの役割：**
- ✅ 設定ファイルのテンプレートと変更履歴の管理
- ✅ Pull Requestによるレビュープロセスの実施
- ❌ **本番サーバーへの自動デプロイ機能はありません**

**本番環境への反映方法：**
1. このリポジトリで設定を変更し、Pull Requestでレビュー
2. マージ後、**手動で**本番サーバーの設定ファイルを更新
3. 本番サーバー上の設定ファイルは`/etc/nginx/`や`/etc/systemd/`に直接存在します

## 📚 ドキュメント構成

- **このファイル（README.md）**: Nginx/systemd設定の変更方法、作業手順
- **[server_overview.md](./server_overview.md)**: サーバー構成、API一覧、エンドポイント詳細、トラブルシューティング
  - 🔍 **API開発者の方は `server_overview.md` を先にお読みください**

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

新しいAPIサービスを追加する際は、以下の2つのファイルをテンプレートとして使用してください。

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
After=docker.service
Requires=docker.service

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

## 4. トラブルシューティングのヒント

Nginx関連で404エラーなどの問題が発生した場合、以下の手順で問題を切り分けてください。

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

1. **常にバックアップを取る**
   - 設定変更前に必ず`backup.$(date +%Y%m%d_%H%M%S)`形式でバックアップ

2. **段階的にテスト**
   - まず`nginx -t`で文法チェック
   - 次に`curl`で内部から動作確認
   - 最後に外部からHTTPS経由で確認

3. **ドキュメント化**
   - 新しいサービスを追加したら、このREADMEも更新
   - server_overview.mdにもエンドポイント情報を追加

4. **ポート番号の管理**
   - 8000番台: メインAPI
   - 8001-8099: マイクロサービス
   - 9000番台: 管理ツール
   - 新しいサービスは既存のポートと重複しないよう確認
