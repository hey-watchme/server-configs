# Avatar Uploader API - Nginx設定デプロイ手順

## 概要
Avatar Uploader APIにHTTPSでアクセスできるようにするため、Nginxリバースプロキシ設定を追加します。

- **変更前**: `http://3.24.16.82:8014` (HTTP、IPアドレス直接)
- **変更後**: `https://api.hey-watch.me/avatar/` (HTTPS、ドメイン名)

## デプロイ手順

### 1. EC2サーバーにSSH接続
```bash
ssh ubuntu@3.24.16.82
```

### 2. 設定リポジトリを更新
```bash
cd /home/ubuntu/watchme-server-configs
git fetch origin
git checkout main
git pull origin main
```

### 3. Nginx設定ファイルをコピー
```bash
# 設定ファイルをNginxディレクトリにコピー
sudo cp sites-available/api.hey-watch.me /etc/nginx/sites-available/

# シンボリックリンクが存在しない場合は作成（初回のみ）
if [ ! -L /etc/nginx/sites-enabled/api.hey-watch.me ]; then
    sudo ln -s /etc/nginx/sites-available/api.hey-watch.me /etc/nginx/sites-enabled/
fi
```

### 4. Nginx設定のテスト
```bash
# 文法チェック（必須）
sudo nginx -t
```

エラーが出た場合は、設定ファイルを修正してから再度テストしてください。

### 5. Nginxをリロード
```bash
# 設定をリロード（サービスは停止しない）
sudo systemctl reload nginx
```

### 6. 動作確認

#### 6.1 ヘルスチェック
```bash
# サーバー内部から確認
curl http://localhost:8014/health

# 外部から確認（HTTPS経由）
curl https://api.hey-watch.me/avatar/health
```

#### 6.2 APIエンドポイントの確認
```bash
# ユーザーアバターのエンドポイント（例）
curl -X POST https://api.hey-watch.me/avatar/v1/users/test-user-id/avatar \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.jpg"
```

### 7. iOSアプリの設定変更

デプロイが成功したら、iOSアプリ側の設定を変更します。

`ios_watchme_v9/ios_watchme_v9/Configuration.swift`:
```swift
// 現在の環境
static var currentURL: String {
    #if DEBUG
    // 本番環境（Nginx経由）を使用
    return productionURL  // "https://api.hey-watch.me/avatar"
    #else
    // リリースビルドでも本番URL
    return productionURL
    #endif
}
```

## トラブルシューティング

### 502 Bad Gatewayが出る場合
```bash
# Avatar Uploaderサービスが起動しているか確認
sudo systemctl status watchme-avatar-uploader

# ポート8014でリッスンしているか確認
sudo lsof -i:8014

# サービスのログを確認
sudo journalctl -u watchme-avatar-uploader -n 50
```

### 404 Not Foundが出る場合
```bash
# Nginxのアクセスログを確認
sudo tail -n 50 /var/log/nginx/access.log | grep avatar

# エラーログを確認
sudo tail -n 50 /var/log/nginx/error.log
```

### CORSエラーが出る場合
ブラウザの開発者ツールでネットワークタブを確認し、プリフライトリクエスト（OPTIONS）が正しく処理されているか確認してください。

## ロールバック手順

問題が発生した場合は、以下の手順で元に戻します：

1. 以前のNginx設定に戻す
```bash
cd /home/ubuntu/watchme-server-configs
git checkout HEAD~1 sites-available/api.hey-watch.me
sudo cp sites-available/api.hey-watch.me /etc/nginx/sites-available/
sudo nginx -t
sudo systemctl reload nginx
```

2. iOSアプリ側も元のEC2直接アクセスに戻す
```swift
// Configuration.swift
return developmentURL  // "http://3.24.16.82:8014"
```

## 確認項目チェックリスト

- [ ] Nginx設定の文法テストが成功
- [ ] Nginxのリロードが成功
- [ ] ヘルスチェックエンドポイントが応答
- [ ] HTTPSでアクセス可能
- [ ] CORSヘッダーが正しく設定されている
- [ ] ファイルアップロードが正常に動作
- [ ] iOSアプリから正常にアップロード可能