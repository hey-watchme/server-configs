# WatchMe Server 変更履歴

## 2025年9月3日（17:20 JST更新）

### systemdサービスの完全移行 - 4つのrestart:noサービス修正
- **opensmile-api**: systemdサービス化完了
  - docker-compose.prod.yml作成
  - watchme-network接続設定追加
  - サーバー再起動時の自動復旧を保証
- **opensmile-aggregator**: systemdサービス化完了
  - docker-compose.prod.yml作成
  - watchme-network接続設定追加
- **api-sed-aggregator**: systemd設定修正完了
  - docker runからdocker-composeへ移行
  - watchme-network接続設定追加
- **vibe-transcriber-v2**: 新規systemdサービス作成
  - ECRベースサービスのsystemd管理実装
  - docker-compose.prod.yml作成
  - イメージ名修正（vibe-transcriber-v2 → watchme-api-transcriber-v2）
- **docker-compose v2対応**: 全systemdファイルを/usr/local/bin/docker-composeパスに統一

### APIデプロイメントガイド作成、watchme-vault-api完全修正
- **watchme-vault-api修正完了**: Docker化とsystemd管理への完全移行
  - systemdサービスファイルをDocker対応に更新
  - docker-compose.prod.ymlを使用した本番運用に切り替え
  - ヘルスチェック問題を解決（curlインストール済みのDockerfile.prod使用）
  - サーバー再起動時の自動起動を保証
- **不要Dockerリソース削除**: 約1.5GB回収（イメージ614MB + ビルドキャッシュ901MB）
- **レガシーネットワーク3個削除**: 自動クリーンアップで削除済み
- **API_DEPLOYMENT_GUIDE.md作成**: デプロイ標準手順書
- **ドキュメント構成見直し**: 4つから3つに統合（運用ガイド・技術仕様・変更履歴）

## 2025年9月2日

### Whisper API削除完了 - Azure Speechへ完全移行
- api_transcriber (Whisper API v1) を本番環境から完全削除
- Azure Speech Service API (vibe-transcriber-v2) への移行完了
- systemdサービス設定をクリーンアップ
- ネットワーク設定を整理

## 2025年8月30日

### Whisper API本番デプロイ完了とトラブルシューティング文書化
- Whisper API (api_whisper_v1) デプロイ完了
- インフラ構成情報とリソース制約の詳細化

## 2025年8月28日

### ネットワークインフラ集約化
- **watchme-networkのインフラ管理を集約化**
- ネットワーク管理が `docker-compose.infra.yml` に一元化
- 自動監視・修復システムが稼働開始
- 全APIサービスの接続状態を5分ごとに自動チェック
- NETWORK-ARCHITECTURE.md 初版作成

## 2025年8月26日

### Azure Speech Service API統合機能拡張
- **Azure Speech Service API統合機能拡張**: WatchMeシステムとの完全統合を実装
  - エンドポイント: `/vibe-transcriber-v2/` → port 8013
  - **新機能**: デバイスID + 日付によるバッチ処理インターフェース
  - **Supabase統合**: `audio_files`テーブルからファイル情報を自動取得
  - **AWS S3統合**: 音声ファイルを直接取得して文字起こし実行
  - **後方互換性**: 既存のfile_pathsインターフェースも継続サポート

## 2025年8月25日

### Vault API拡張 - 音声ファイル管理機能追加
- **Vault API 拡張**: API Manager統合用の音声ファイル管理機能を追加
  - `GET /api/audio-files` - 音声ファイル一覧取得（フィルタリング・ページネーション対応）
  - `GET /api/audio-files/presigned-url` - 署名付きURL生成（ブラウザ再生・ダウンロード用）
  - `GET /api/devices` - 登録デバイス一覧取得
  - S3メタデータ統合: ファイル存在確認・サイズ・更新日時の自動取得
  - 処理ステータス表示: 転写・行動分析・感情分析の処理状況を一覧表示
  - セキュリティ強化: 署名付きURLによる一時的・安全なファイルアクセス

## 2025年8月21日

### watchme-admin管理画面完全リニューアル
- **watchme-admin管理画面**: 完全リニューアル版をECRからデプロイ
  - Docker化完了: `754724220380.dkr.ecr.ap-southeast-2.amazonaws.com/watchme-admin:latest`
  - 統一ネットワーク（watchme-network）への移行完了
  - FastAPIベースの新アーキテクチャに刷新
  - systemdサービス設定をECR対応に更新

## 2025年8月12日

### ネットワーク設計文書化とVibe Scorer修復
- Vibe Scorer（心理スコアリング）のネットワーク接続修復
- ネットワーク設計詳細の文書化
- コンテナ間通信の問題解決

## 2025年8月10日

### エンドポイント3層構造の整理
- 管理用・内部通信用・外部公開用エンドポイントの明確化
- スケジューラーAPIエンドポイントエラーの修正
- API実行エンドポイント一覧の整備

## 2025年8月9日

### ポート番号統一とopensmile-api修正
- 全サービスの公開ポートとコンテナ内部ポートを統一
- opensmile-apiの設定修正完了

## 2025年8月8日

### スケジューラーネットワーク修復
- スケジューラーのネットワーク接続問題を解決
- watchme-networkへの接続確立

## 2025年8月6日

### 統一ネットワーク作成
- watchme-network (172.27.0.0/16) 作成
- 初期コンテナの接続開始

---

**注意**: この履歴は主要な変更のみを記録しています。詳細な技術情報は [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) を参照してください。