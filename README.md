# WatchMe Server Configurations

最終更新: 2026-03-06

音声録音から心理・感情分析までを自動実行するプラットフォーム。
EC2サーバーの設定ファイル（`production/`）とドキュメント（`docs/`）を管理するリポジトリ。

> **⚠️ 開発の前提**
>
> - **データベースファースト**: テーブル構造・データは必ずSupabase MCP経由で確認すること（詳細はCLAUDE.md参照）
> - **AWS現状確認ファースト**: インフラ状態（EC2/Lambda/SQS/ECR/CloudWatch）は必ずAWS MCPで確認してから実装・変更すること
> - **MCP優先運用**: 調査・検証は `Supabase MCP + AWS MCP` を第一選択とし、AWS CLIは補助的に使用すること
> - **実装前チェック順序（必須）**:
>   1. Supabase MCPでDB構造・対象レコード確認
>   2. AWS MCPで関連サービスの稼働状況・リソース状況確認
>   3. 影響範囲を確定後に実装
> - **local_date原則**: すべての日付処理はデバイスのローカル日付（`local_date`）を使用。UTCからの変換・計算は禁止

---

## 📊 システム構成

**クライアント**: iOS App / Web Dashboard / Observer Device (M5 Core2)
**サーバー**: EC2 t4g.large (Sydney, 3.24.16.82)
**データベース**: Supabase (PostgreSQL)
**ドメイン**: api.hey-watch.me（DNS: Cloudflare, DNS Onlyモード）

### EC2 APIサービス

| サービス | ポート | 役割 |
|---------|--------|------|
| Vault API | 8000 | S3音声ファイル配信、SKIP機能 |
| Vibe Transcriber | 8013 | Deepgram Nova-2 文字起こし |
| Behavior Features | 8017 | 527種類の音響検出（PaSST） |
| Emotion Features | 8018 | 8感情認識（Kushinada） |
| Aggregator API | 8050 | Spot/Daily/Weekly集計・プロンプト生成 |
| Profiler API | 8051 | LLM分析（OpenAI GPT-5 Nano） |
| Janitor | 8030 | 音声データ自動削除 |
| Admin | 9000 | 管理ツール |
| API Manager | 9001 | API管理 |
| Avatar Uploader | 8014 | アバター画像管理 |
| Demo Generator | 8020 | デモデータ生成 |
| QR Code Generator | 8021 | デバイス共有用QRコード生成 |

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
│   └── setup_server.sh
│
└── docs/                   # ドキュメント（EC2不要）
```

**運用方針**: EC2には `production/` のみデプロイ。`docs/` はEC2に配置しない。

---

## 📚 ドキュメント一覧

| 目的 | ドキュメント |
|------|-------------|
| 🔄 **処理の流れ** | [PROCESSING_ARCHITECTURE.md](./docs/PROCESSING_ARCHITECTURE.md) |
| 🔧 **技術仕様（全サービス・エンドポイント）** | [TECHNICAL_REFERENCE.md](./docs/TECHNICAL_REFERENCE.md) |
| 📝 **デプロイ・運用手順** | [OPERATIONS_GUIDE.md](./docs/OPERATIONS_GUIDE.md) |
| 🚀 **CI/CD実装ガイド** | [CICD_STANDARD_SPECIFICATION.md](./docs/CICD_STANDARD_SPECIFICATION.md) |
| 📈 **スケーラビリティ計画** | [SCALABILITY_ROADMAP.md](./docs/SCALABILITY_ROADMAP.md) |
| ⚠️ **既知の問題** | [KNOWN_ISSUES.md](./docs/KNOWN_ISSUES.md) |
| 🏗️ **アーキテクチャ移行ガイド** | [ARCHITECTURE_AND_MIGRATION_GUIDE.md](./docs/ARCHITECTURE_AND_MIGRATION_GUIDE.md) |
| 🔍 **Spot/Daily分析ガイド** | [SPOT_AND_DAILY_ANALYSIS_GUIDE.md](./docs/SPOT_AND_DAILY_ANALYSIS_GUIDE.md) |
| 🆕 **新規API統合ガイド** | [NEW_API_INTEGRATION_GUIDE.md](./docs/NEW_API_INTEGRATION_GUIDE.md) |
| 💰 **コスト管理** | [COST_MANAGEMENT.md](./docs/COST_MANAGEMENT.md) |
| 🔮 **長期記憶（将来構想）** | [FUTURE_LONG_TERM_MEMORY.md](./docs/FUTURE_LONG_TERM_MEMORY.md) |
| 🖥️ **EC2再起動トラブルシューティング** | [EC2_RESTART_TROUBLESHOOTING.md](./docs/EC2_RESTART_TROUBLESHOOTING.md) |
| 📜 **変更履歴** | [CHANGELOG.md](./docs/CHANGELOG.md) |

---

## 🔗 関連プロジェクト

### 📱 WatchMe iOS App

音声録音とリアルタイム分析結果の閲覧を行うiOSアプリ。

- **リポジトリ**: `/Users/kaya.matsumoto/ios_watchme_v9`
- **技術スタック**: Swift 5.9+ / SwiftUI / Supabase Swift SDK
- **主要機能**: 手動録音・S3アップロード、Spot/Daily/Weekly分析の閲覧、プッシュ通知、QRコードデバイス共有
- **データアクセス**: Supabaseテーブル直接参照（同一DB）
- **詳細**: [ios_watchme_v9/README.md](/Users/kaya.matsumoto/ios_watchme_v9/README.md)

### 💼 WatchMe Business

WatchMeからスピンアウトしたB2B向けサービス。児童発達支援事業所向けに、保護者ヒアリング音声からAIで個別支援計画書を自動生成する。

- **リポジトリ**: `/Users/kaya.matsumoto/projects/watchme/business`
- **技術スタック**: FastAPI (Python) + React PWA (TypeScript)
- **ポート**: Backend 8052 / Frontend 5176
- **インフラ共有**: 同一EC2・同一Supabase DB（`business_*` テーブル）、S3バケット `watchme-business`
- **ASR**: Speechmatics Batch API（話者分離対応）
- **LLM**: OpenAI GPT-4o
- **詳細**: [business/README.md](/Users/kaya.matsumoto/projects/watchme/business/README.md)
