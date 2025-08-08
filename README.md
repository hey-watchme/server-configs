# WatchMe サーバー設定リポジトリ

このリポジトリは、WatchMeプラットフォームのEC2サーバーで稼働する、**Nginx** と **systemd** の全ての設定ファイルを一元管理します。

**サーバー上の設定ファイルを直接編集することは固く禁止します。** 全ての変更は、このリポジトリへのPull Requestを通じて行われなければなりません。

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

1.  **設定リポジトリを更新**
    ```bash
    # このリポジトリがクローンされているディレクトリに移動
    cd /path/to/watchme-server-configs 
    git pull origin main
    ```

2.  **変更内容を反映**
    - **Nginxの場合**:
        ```bash
        # 1. 設定ファイルをコピー
        sudo cp sites-available/api.hey-watch.me /etc/nginx/sites-available/

        # 2. 文法テスト (最重要)
        sudo nginx -t

        # 3. テスト成功後、設定をリロード
        sudo systemctl reload nginx
        ```
    - **systemdの場合**:
        ```bash
        # 1. 設定ファイルをコピー
        sudo cp systemd/your-service.service /etc/systemd/system/

        # 2. systemdデーモンをリロード
        sudo systemctl daemon-reload

        # 3. サービスを有効化 & 起動
        sudo systemctl enable --now your-service.service
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
