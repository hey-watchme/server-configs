# WatchMe Server Configurations

EC2サーバーの設定ファイルとドキュメントを管理するリポジトリ

---

## 📁 ディレクトリ構造

```
server-configs/
├── production/              # 本番環境設定ファイル（EC2に配置）
│   ├── systemd/            # systemd サービス定義
│   ├── docker-compose-files/ # Docker Compose設定
│   ├── sites-available/    # Nginx設定
│   ├── lambda-functions/   # AWS Lambda関数ソース
│   ├── scripts/            # デプロイ・運用スクリプト
│   ├── docker-compose.infra.yml
│   └── setup_server.sh
│
└── docs/                   # ドキュメント（EC2不要）
    ├── README.md           # 詳細なドキュメント
    ├── TECHNICAL_REFERENCE.md
    ├── OPERATIONS_GUIDE.md
    └── ...
```

---

## 🚀 運用方針

### ローカル環境
- **すべてのファイル**を管理（`production/` + `docs/`）
- ドキュメントの編集・更新
- 設定ファイルの変更

### EC2本番環境
- **`production/`のみ**をデプロイ
- ドキュメント（`docs/`）は配置しない
- 設定ファイルは`/home/ubuntu/watchme-server-configs/`に配置

---

## 📋 EC2での配置先

### systemd設定
```
production/systemd/xxx.service
  ↓ シンボリックリンク
/etc/systemd/system/xxx.service
```

### docker-compose設定
```
production/docker-compose-files/xxx.yml
  ↓ systemdから直接参照
/home/ubuntu/watchme-server-configs/production/docker-compose-files/xxx.yml
```

### nginx設定
```
production/sites-available/api.hey-watch.me
  ↓ シンボリックリンク
/etc/nginx/sites-available/api.hey-watch.me
```

---

## 🔧 セットアップ手順

### EC2初回セットアップ

```bash
# 1. production/のみをクローン（sparse-checkout）
cd /home/ubuntu
git clone --no-checkout git@github.com:hey-watchme/server-configs.git watchme-server-configs
cd watchme-server-configs
git sparse-checkout init --cone
git sparse-checkout set production
git checkout main

# 2. セットアップスクリプト実行
cd production
./setup_server.sh
```

### 設定変更の反映

```bash
# EC2で
cd /home/ubuntu/watchme-server-configs
git pull origin main

# 必要に応じてサービス再起動
sudo systemctl restart [service-name]
```

---

## 📚 ドキュメント

詳細なドキュメントは [`docs/`](./docs/) ディレクトリを参照：

- **[README.md](./docs/README.md)** - システム全体の概要
- **[TECHNICAL_REFERENCE.md](./docs/TECHNICAL_REFERENCE.md)** - 技術仕様
- **[OPERATIONS_GUIDE.md](./docs/OPERATIONS_GUIDE.md)** - 運用ガイド
- **[PROCESSING_ARCHITECTURE.md](./docs/PROCESSING_ARCHITECTURE.md)** - 処理アーキテクチャ
- **[API_NAMING_UNIFICATION_TASK.md](./docs/API_NAMING_UNIFICATION_TASK.md)** - API命名統一タスク

---

## ⚠️ 重要な注意事項

1. **本番環境には`production/`のみをデプロイ**
   - ドキュメントファイル（`docs/`）はEC2に配置しない

2. **設定ファイルの変更手順**
   - ローカルで`production/`内のファイルを編集
   - コミット・プッシュ
   - EC2で`git pull`
   - サービス再起動

3. **ドキュメントの更新**
   - ローカルで`docs/`内を編集
   - コミット・プッシュ
   - EC2では不要（pullしない）

---

**更新日**: 2025-10-30
**リポジトリ**: `git@github.com:hey-watchme/server-configs.git`
