# WatchMe Server 変更履歴

## 2025年9月5日（18:00 JST更新）

### systemd管理の完全統一とシステムクリーンアップ

#### サービス管理の改善
- **mood-chart-api.service修正完了**:
  - サービスファイル最終行の不正文字（`EOF < /dev/null`）を削除
  - docker-compose-files/mood-chart-api-docker-compose.prod.yml を新規作成
  - ECRベースの統一管理に移行、systemd自動起動を実現

- **watchme-infrastructure.service設定修正**:
  - [Unit]セクションの誤った RequiredBy 設定を削除
  - systemd警告メッセージを解消

- **watchme-admin.service ECR移行完了**:
  - docker-compose-files/watchme-admin-docker-compose.prod.yml を作成
  - セキュリティ向上: ポートバインドを 0.0.0.0:9000 から 127.0.0.1:9000 に変更
  - Type=simple に変更して正しいプロセス管理を実現

- **watchme-web-app.service ECR移行完了**:
  - docker-compose-files/watchme-web-docker-compose.prod.yml を作成
  - /home/ubuntu/watchme-docker の既存設定を活用
  - ボリュームマウントでデータとアバターを永続化

#### システムクリーンアップ（6GB削減）
- **実施前**: ディスク使用率 69%（20GB/29GB）
- **実施後**: ディスク使用率 50%（14GB/29GB）
- **削減内容**:
  - 重複Dockerイメージ 7個（3.5GB）
  - 未使用Dockerボリューム 2個
  - バックアップディレクトリ 5個
  - Python仮想環境（venv）8個
  - 古いAPIディレクトリ 3個
  - 各種アーカイブファイル

#### システム最終状態
- 全13サービスがsystemd管理下で正常稼働
- サーバー再起動時の自動起動を保証
- 全ポートが127.0.0.1にバインド（セキュリティ向上）
- watchme-networkで全サービスが統一通信

## 2025年9月4日（23:45 JST更新）

### スケジューラー緊急復旧とドキュメント改善
- **watchme-scheduler緊急復旧**:
  - 誤った修正によりスケジューラーが約30分間停止
  - 原因: systemd設定をdocker-compose.prod.ymlに変更（API Managerのみ起動）
  - 解決: docker-compose.all.ymlに戻し、ネットワーク設定も修正（external: true）
  - 現在は両サービス（API Manager + Scheduler）正常稼働中

- **ドキュメント大幅改善**:
  - API Manager READMEにデプロイ時の重要注意事項を追記
  - docker-compose.all.yml使用の必要性を強調
  - トラブルシューティングに「スケジューラーが起動しない」を最優先項目として追加
  - FAQ追加: API ManagerとSchedulerの管理方法を明記

### ネットワーク統合とsystemd設定修正（23:30 JST）
- **watchme-api-manager systemd修正**:
  - ~~docker-compose.all.yml → docker-compose.prod.ymlに修正~~ ※誤った修正、後に戻した
  - 最終的にdocker-compose.all.ymlが正しい設定
  - 8/30から発生していた"No such file or directory"エラーを解決

- **Dockerネットワーク完全統合**:
  - レガシーネットワーク4個を削除（8個→4個に削減）
    - api_sed_v1_default
    - watchme-api-manager_watchme-network
    - watchme-docker_watchme-network
    - watchme-vault-api-docker_vault-network
  - watchme-docker/docker-compose.prod.yml修正（driver: bridge → external: true）
  - 全12サービスがwatchme-network単一ネットワークに統合完了
  - メモリ使用量削減と管理シンプル化を達成

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