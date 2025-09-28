# WatchMe 運用ガイド

最終更新: 2025年9月6日

## 🎯 このガイドの目的

このガイドは、WatchMeプラットフォームにおける、**2つの異なるデプロイ作業**の手順を明確に分離して定義します。
作業の目的に応じて、必ず対応する手順を参照してください。

---

## 1. アプリケーションのデプロイ手順

### 👉 この手順を使う時

-   **各APIのソースコード（Python, JSなど）を修正した**
-   **`.env`ファイル（環境変数）の内容を更新した**

上記のように、サービスの「中身」だけが変更され、`docker-compose.yml`や`systemd`の`.service`ファイルに**変更がない**場合に、この手順を実行します。

### ワークフロー

> **📘 CI/CD詳細**: GitHub ActionsによるCI/CDプロセスの詳細は[CI/CD標準仕様書](./CICD_STANDARD_SPECIFICATION.md)を参照

1.  **CI/CDの完了確認:**
    対象APIのGitリポジトリで、CI/CD（GitHub Actions）が完了し、新しいバージョンタグが付いたDockerイメージがECRにプッシュされたことを確認します。

2.  **本番サーバーへ接続:**
    ```bash
    ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
    ```

3.  **サービスの再起動:**
    以下のコマンドで、対象のサービスを再起動します。`systemd`が、ECRから新しいイメージを自動で`pull`して、コンテナを安全に入れ替えてくれます。

    ```bash
    # 例: avatar-uploaderを再起動する場合
    sudo systemctl restart watchme-avatar-uploader.service
    ```

4.  **動作確認:**
    `systemctl status`コマンドで、サービスが`active (running)`になっていることを確認します。

    ```bash
    sudo systemctl status watchme-avatar-uploader.service
    ```

---

## 2. サーバー構成の変更手順

### 👉 この手順を使う時

-   **`docker-compose.yml`ファイルを修正した**（ポート番号、ボリューム、イメージ名など）
-   **`systemd`の`.service`ファイルを修正した**（依存関係、実行コマンドなど）
-   **Nginxの設定ファイル（`sites-available/`）を修正した**
-   **新しいサービスをシステムに追加した**

上記のように、インフラやサービスの「設計図」に関わる変更を行った場合に、この手順を実行します。

### ワークフロー

1.  **Gitリポジトリでの変更:**
    この`watchme-server-configs`リポジトリで設定ファイルを修正し、変更を`main`ブランチに`push`します。

2.  **本番サーバーへ接続:**
    ```bash
    ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
    ```

3.  **設定の反映:**
    サーバー上でリポジトリの最新の状態を取得し、セットアップスクリプトを実行して、変更をシステム全体に反映させます。

    ```bash
    cd /home/ubuntu/watchme-server-configs
    git pull origin main
    ./setup_server.sh
    ```

4.  **（もし新しいサービスを追加した場合のみ）サービスの有効化:**
    `setup_server.sh`は設定をリンクするだけです。新しいサービスをOS起動時に自動起動させるには、以下のコマンドで「有効化」する必要があります。

    ```bash
    sudo systemctl enable --now <new-service-name>.service
    ```

5.  **動作確認:**
    関連するサービスの`systemctl status`を確認します。
