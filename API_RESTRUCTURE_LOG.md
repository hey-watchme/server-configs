# API階層化リストラクチャリング作業ログ

**作業開始日**: 2025-10-22
**最終更新日**: 2025-10-22 22:20
**目的**: マイクロサービスAPIをドメイン駆動設計に基づいて階層化し、バージョン管理を導入

---

## 📊 現在の進捗状況

- **フェーズ1（ローカル環境）**: ✅ 100%完了
- **フェーズ2（本番準備）**: ✅ 100%完了
- **フェーズ3（本番環境実装）**: 🔄 0%（次回実施）

**全体進捗**: 75% (9/12ステップ完了)

---

## 🎯 次回作業: フェーズ3（本番環境実装）

### 事前準備（オプション）

emotion-analysis系2APIのGitHub Actionsを手動実行してECRイメージを事前作成（推奨）:
- https://github.com/hey-watchme/api-emotion-analysis-feature-extractor-v3/actions
- https://github.com/hey-watchme/api-emotion-analysis-aggregator/actions

**注**: 既にディレクトリとECRリポジトリは作成済みのため、現在は正常にデプロイ可能

---

### 本番環境での作業手順

#### 1. EC2サーバーへSSH接続（所要時間: 1分）

```bash
ssh -i /Users/kaya.matsumoto/watchme-key.pem ubuntu@3.24.16.82
```

---

#### 2. EC2ディレクトリ構造変更（所要時間: 20分）

```bash
cd /home/ubuntu

# 5つのディレクトリをリネーム
mv superb emotion-analysis-feature-extractor-v3  # ⚠️ 既に作成済み
mv opensmile-aggregator emotion-analysis-aggregator  # ⚠️ 既に作成済み
mv api_ast behavior-analysis-feature-extractor-v2
mv vibe-transcriber-v2 vibe-analysis-transcriber-v2
mv watchme-api-vibe-aggregator vibe-analysis-aggregator

# 確認
ls -la | grep -E "emotion|behavior|vibe"
```

**注意**:
- `emotion-analysis-*`の2つは既に新規作成済み
- `superb`と`opensmile-aggregator`は存在しないため、mvではなく既存ディレクトリを使用

---

#### 3. Nginx設定更新（所要時間: 15分）

**ファイル**: `/etc/nginx/sites-available/api.hey-watch.me`

**変更内容**: 新旧エンドポイント並行運用

```nginx
# 新エンドポイント追加（旧エンドポイントも残す）
location /behavior-analysis/features/ {
    proxy_pass http://localhost:8017/;
    # ... 既存設定をコピー
}

location /emotion-analysis/features/ {
    proxy_pass http://localhost:8018/;
    # ... 既存設定をコピー
}

location /emotion-analysis/aggregation/ {
    proxy_pass http://localhost:8012/;
    # ... 既存設定をコピー
}

location /vibe-analysis/transcription/ {
    proxy_pass http://localhost:8013/;
    # ... 既存設定をコピー
}

location /vibe-analysis/aggregation/ {
    proxy_pass http://localhost:8009/;
    # ... 既存設定をコピー
}

location /vibe-analysis/scoring/ {
    proxy_pass http://localhost:8002/;
    # ... 既存設定をコピー
}
```

**設定テスト＆リロード**:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

#### 4. systemdサービス更新（所要時間: 20分）

**新規サービスファイル作成（5個）**:

1. `/etc/systemd/system/behavior-analysis-feature-extractor-v2.service`
2. `/etc/systemd/system/emotion-analysis-feature-extractor-v3.service`
3. `/etc/systemd/system/emotion-analysis-aggregator.service`
4. `/etc/systemd/system/vibe-analysis-transcriber-v2.service`
5. `/etc/systemd/system/vibe-analysis-aggregator.service`

**参考**: `/home/ubuntu/watchme-server-configs/systemd/`の既存ファイルをコピーして修正

**サービス有効化**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable behavior-analysis-feature-extractor-v2
sudo systemctl enable emotion-analysis-feature-extractor-v3
sudo systemctl enable emotion-analysis-aggregator
sudo systemctl enable vibe-analysis-transcriber-v2
sudo systemctl enable vibe-analysis-aggregator
```

**旧サービス無効化（5個）**:
```bash
sudo systemctl stop ast-api
sudo systemctl disable ast-api
# 以下同様に無効化...
```

---

#### 5. GitHub Actions手動実行でデプロイ（所要時間: 30分）

各リポジトリのActionsページから手動実行:
- https://github.com/hey-watchme/api-emotion-analysis-feature-extractor-v3/actions
- https://github.com/hey-watchme/api-emotion-analysis-aggregator/actions
- 他のAPIも同様

---

#### 6. 動作確認とヘルスチェック（所要時間: 30分）

```bash
# コンテナ起動状態確認
docker ps | grep -E "emotion|behavior|vibe"

# 各APIのヘルスチェック
curl http://localhost:8017/health  # behavior-analysis-feature-extractor-v2
curl http://localhost:8018/health  # emotion-analysis-feature-extractor-v3
curl http://localhost:8012/        # emotion-analysis-aggregator
curl http://localhost:8013/health  # vibe-analysis-transcriber-v2
curl http://localhost:8009/health  # vibe-analysis-aggregator
curl http://localhost:8002/health  # vibe-analysis-scorer

# 外部からの疎通確認
curl https://api.hey-watch.me/emotion-features/health
curl https://api.hey-watch.me/behavior-features/health
```

---

**合計所要時間**: 約2時間

---

## 📝 重要な注意事項

### 完了済みの準備作業
- ✅ ECRリポジトリ作成完了（5個）
- ✅ GitHub Actions更新完了（5リポジトリ）
- ✅ emotion-analysis系2APIのCICD完全実装
- ✅ EC2上に`emotion-analysis-*`ディレクトリ作成済み
- ✅ api-managerのコンテナ名参照更新完了（ローカル）

### 次回作業時の確認事項
1. emotion-analysis系2APIのGitHub Actionsが正常にデプロイされているか確認
2. 他のAPIもGitHub Actionsを使用して自動デプロイ推奨
3. 旧エンドポイントは一定期間残す（Lambdaからの移行確認後に削除）

---

## 📚 関連ドキュメント

- [README.md](./README.md) - サーバー設定の全体概要
- [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md) - 統一CI/CDプロセス（初回セットアップ手順追加済み）
- [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md) - 音声処理アーキテクチャ
- [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md) - 運用ガイド
- [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) - 技術仕様

---

**最終更新**: 2025-10-22 22:20
**次回作業者へ**: 上記「次回作業: フェーズ3」の手順に従って実施してください。
