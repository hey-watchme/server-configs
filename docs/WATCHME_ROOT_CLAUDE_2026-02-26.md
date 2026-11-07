# CLAUDE.md - WatchMe プロジェクト詳細

最終更新: 2026-02-26

## AGENTS Priority

`/Users/kaya.matsumoto/projects/watchme/AGENTS.md` をこのプロジェクトの正本として優先する。

- GitHub アカウント運用
- CLI 利用方針
- MCP の使い分け

は、まず `AGENTS.md` を確認する。

## 🎯 プロジェクト概要

心理・感情モニタリングプラットフォーム（マイクロサービスアーキテクチャ）
- 音声録音から感情分析まで一貫したパイプライン
- React dashboards, Python APIs, iOS apps
- リアルタイム感情・行動分析システム

---

## 🏗️ プロジェクト構造

### メインプロジェクト
```
/Users/kaya.matsumoto/projects/watchme/  # メインディレクトリ
├── api/                # 全APIサービス群
│   ├── vault/         # ✅ Vault API (SKIP機能修正済 11/1)
│   ├── vibe-analysis/ # 音声分析API群
│   ├── behavior-analysis/  # 行動分析API
│   ├── emotion-analysis/   # 感情分析API
│   ├── api-manager/   # API管理UI
│   ├── avatar-uploader/    # アバター管理
│   ├── janitor/       # 音声削除サービス
│   └── demo-generator/     # デモデータ生成
├── server-configs/     # サーバー設定・ドキュメント
│   └── docs/          # 📚 プロジェクト全体のドキュメント
├── admin/             # 管理ツール
├── design/            # デザインファイル
├── device/            # デバイス関連
├── m5core2_recorder/  # M5 Core2録音デバイス
└── web_marketing/     # 製品サイト（Vercel）
```

### 外部プロジェクト
```
/Users/kaya.matsumoto/ios_watchme_v9   # 📱 iOSアプリ（Swift）- 稼働中
/Users/kaya.matsumoto/watchme_v8       # 🌐 Webダッシュボード（React）- 休止中
```

---

## 🎯 システムアーキテクチャ

### データフロー
```
1. 録音デバイス（iOS/Observer） → S3アップロード
2. S3イベント → Lambda (audio-processor) → SQS
3. Lambda (audio-worker) → 3つの分析API並列実行
4. 分析結果 → Supabase保存
5. 累積分析 → プッシュ通知 → iOSアプリ
```

### 主要コンポーネント（EC2上のDocker）
- **Vault API** (:8000) - S3ゲートウェイ、SKIP機能管理
- **Vibe Transcriber** (:8013) - マルチプロバイダーASR文字起こし
- **Behavior Features** (:8017) - 527種類の音響イベント検出
- **Emotion Features** (:8018) - 8感情認識
- **Profiler API** (:8051) - LLM心理分析（Spot/Daily）

---

## 🚨 このプロジェクト固有の絶対ルール

### 開発環境・テストの原則

⚠️ **このプロジェクトは本番環境では全てDockerコンテナで運用されています**

#### 基本方針
- ✅ **本番環境はDockerコンテナで運用**
- ✅ **各APIディレクトリには必ずREADME.mdがある** - 開発手順はそこに記載
- ⚠️ **ローカルでのDockerテストは現在不可**
  - ローカルのDocker環境は動作しない状態
  - コード修正後は構文チェックのみ実施
  - 実際の動作確認は本番環境で行う

#### 現在の開発フロー（実態）
1. **コード修正**
   ```bash
   # 構文チェック
   python3 -m py_compile <filename>.py

   # エンコーディング確認
   file <filename>.py
   ```
2. **GitHub経由で本番デプロイ**
   ```bash
   git add .
   git commit -m "変更内容"
   git push origin main
   ```
3. **GitHub Actionsでデプロイ確認**
   ```bash
   gh run list --repo hey-watchme/<repo-name> --limit 3
   gh run watch  # リアルタイム監視
   ```
4. **本番環境で動作確認**
   ```bash
   # APIヘルスチェック
   curl https://api.hey-watch.me/<endpoint>/health

   # 実際のAPIテスト
   curl -X POST https://api.hey-watch.me/<endpoint> ...
   ```

#### ローカルサーバー再起動ルール

**バックエンドのPythonコード（app.py, services/*.py等）を修正した場合、ローカルサーバーを自動的に再起動すること。**
ユーザーに確認を取らず、修正完了後に即座に再起動する。

```bash
# 再起動手順
lsof -i :<port> -t | xargs kill  # 既存プロセス停止
cd <backend_dir> && python3 app.py &  # バックグラウンドで再起動
sleep 2 && curl -s http://localhost:<port>/health  # ヘルスチェック
```

- **business**: ポート8052、`business/backend/`

#### 将来的な改善点
- ローカルDocker環境の復旧
- ステージング環境の構築
- ローカルでのテスト環境整備

### コーディング規約とエンコーディング対策

#### 📝 言語使用ルール

**ドキュメント類（日本語）**:
- README.md
- CLAUDE.md
- その他の .md ファイル
- コミットメッセージ本文

**コード内（英語のみ）**:
- Python/JavaScript/Swift等のコード内コメント
- 関数・変数のdocstring
- エラーメッセージ

**理由**: 過去にコード内の日本語コメントで文字化け（UTF-8エンコーディングエラー）が発生したため。

#### ✅ ファイル作成後の必須検証

**全てのPythonファイル作成・編集後は必ず以下を実行**:

```bash
# エンコーディング検証
file <filename>.py

# 期待される出力
<filename>.py: Python script text executable, UTF-8 text
# または
<filename>.py: Python script text executable, ASCII text

# ❌ 異常（文字化け）の場合
<filename>.py: data  # ← これが出たら即座に修正が必要
```

**構文チェック**:
```bash
python3 -m py_compile <filename>.py
# エラーが出なければOK
```

#### 🚨 文字化け発見時の対処

1. **即座にSTOP**して報告
2. **該当ファイルを英語コメントで書き直し**
3. **再度 `file` コマンドで検証**
4. **正常になったら git commit**

#### 💡 負荷について

`file` コマンドと `py_compile` は非常に軽量（<1秒）なので、都度実行しても問題なし。

---

#### 📋 チェックリスト（新規Pythonファイル作成時）

```bash
# 1. ファイル作成
# （Writeツールで作成）

# 2. エンコーディング検証
file <filename>.py

# 3. 構文チェック
python3 -m py_compile <filename>.py

# 4. 問題なければコミット
git add <filename>.py
git commit -m "feat: add <filename>"
```

### 環境変数追加時の必須チェックリスト

⚠️ **重要**: 新しい環境変数（APIキー、プロバイダー設定等）を追加する時は**必ず3箇所**を更新すること

#### ✅ 必須手順（3箇所セット）

1. **GitHub Secrets** - リポジトリの Settings > Secrets and variables > Actions
   ```
   例: DEEPGRAM_API_KEY を追加
   ```

2. **docker-compose.prod.yml** - `environment:` セクションに追加
   ```yaml
   environment:
     - DEEPGRAM_API_KEY=${DEEPGRAM_API_KEY}  # ← 追加
   ```

3. **.github/workflows/deploy-to-ecr.yml** - 2箇所を更新
   ```yaml
   # 3-a. env: セクションに追加
   env:
     DEEPGRAM_API_KEY: ${{ secrets.DEEPGRAM_API_KEY }}  # ← 追加

   # 3-b. .env作成スクリプトに追加
   run: |
     ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
       echo "DEEPGRAM_API_KEY=${DEEPGRAM_API_KEY}" >> .env  # ← 追加
     ENDSSH
   ```

#### ❌ よくある失敗パターン

- GitHub Secretsに追加したが、docker-compose.ymlを忘れた
- .github/workflows/*.ymlのenv:には追加したが、echoコマンドを忘れた
- ローカルの.envには追加したが、CI/CDワークフローを更新し忘れた

#### 💡 確認方法

デプロイ後、コンテナ内で環境変数が設定されているか確認：
```bash
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
docker exec {container-name} printenv | grep {変数名}
```

### データベース設計の絶対ルール（Supabase）
- ⚠️ **auth.usersテーブルへの直接参照は絶対禁止**
- ✅ **すべてのユーザー参照は`public.users(user_id)`を使用**
- ✅ 新規テーブル作成時の外部キー：`REFERENCES public.users(user_id) ON DELETE CASCADE`
- ✅ iOS側のユーザーID取得：`userAccountManager.currentUser?.profile?.userId`（.idは使わない）
- 理由：auth.usersはSupabase内部テーブルでアクセス不可のため

### サーバー設定ファイルの運用ルール（重要）

⚠️ **サーバー設定ファイル（`server-configs/`）の変更は必ず以下の手順を守ること**

#### 設定ファイルの場所
- **ローカル**: `/Users/kaya.matsumoto/projects/watchme/server-configs/`
- **本番EC2**: `/home/ubuntu/watchme-server-configs/`（`production/`のみ）

#### 絶対に守るべき変更手順
1. **ローカルで設定ファイルを編集**
   - `server-configs/production/` 配下のファイルを編集
   - systemd、docker-compose、nginx設定など
2. **GitHub にコミット・プッシュ**
   ```bash
   cd /Users/kaya.matsumoto/projects/watchme/server-configs
   git add .
   git commit -m "設定変更の説明"
   git push origin main
   ```
3. **本番EC2で変更を反映**
   ```bash
   ssh -i /Users/kaya.matsumoto/watchme-key.pem ubuntu@3.24.16.82
   cd /home/ubuntu/watchme-server-configs
   git pull origin main
   sudo systemctl restart [service-name]  # 必要に応じて
   ```

### CLI ツールの活用（優先使用）

⚠️ **重要**: このプロジェクトでは以下のCLIツールがインストール済みです。**コマンドラインツールを優先的に使用**してください。

#### ✅ インストール済みCLIツール

| ツール | 用途 | インストール状態 |
|--------|------|---------------|
| **GitHub CLI** (`gh`) | GitHub Actions、PR、Issue管理 | ✅ インストール済み・認証済み |
| **AWS CLI** (`aws`) | EC2、S3、Lambda、ECR操作 | ✅ インストール済み・認証済み |
| **Docker CLI** (`docker`) | コンテナ管理 | ✅ インストール済み |
| **Supabase MCP** | DB参照・SQL実行 | ✅ 設定済み（グローバルMCP + read-only） |

#### 🎯 CLI使用の原則

**基本方針**: ブラウザでできることは、CLIで実行する

##### GitHub CLI (`gh`) の活用

```bash
# CI/CDデプロイ状況確認（git push後）
gh run list --limit 3

# リアルタイム監視
gh run watch

# 失敗ログの即座確認
gh run view --log-failed

# Secretsの確認
gh secret list

# PR作成
gh pr create --title "..." --body "..."
```

**認証設定**: `~/.zshrc` に `GH_TOKEN` を設定済み（セッション間で永続化）

##### AWS CLI (`aws`) の活用

```bash
# Lambda関数の実行ログ確認
aws logs tail /aws/lambda/watchme-audio-worker --follow

# SQSキューの状態確認
aws sqs get-queue-attributes --queue-url ...

# ECRイメージ一覧
aws ecr list-images --repository-name watchme-vault-api
```

##### Docker CLI (`docker`) の活用

```bash
# EC2上のコンテナ確認
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82
docker ps | grep watchme

# ログ確認
docker logs watchme-vault-api --tail 100 -f

# コンテナ内でコマンド実行
docker exec watchme-vault-api printenv | grep API_KEY
```

#### ❌ 避けるべきパターン

- ❌ ブラウザでGitHub Actionsのログを毎回確認
- ❌ AWSコンソールでLambdaログを確認

#### ✅ 推奨パターン

- ✅ `gh run watch` でCI/CD監視
- ✅ `aws logs tail` でLambdaログ確認
- ✅ **Supabase MCPでDB参照・テーブル一覧・SQL実行**（ダッシュボードよりMCP優先）

##### Supabase MCP の活用

**設定**: CodexグローバルMCP（`~/.codex/config.toml`）と `watchme/.vscode/mcp.json` の両方で共通ラッパーを使用
**起動ラッパー**: `~/.codex/bin/start-supabase-mcp.sh`
**トークン管理**: macOS Keychain（service: `codex_supabase_access_token`）から読み込み

```
# プロジェクト一覧
mcp_supabase_list_projects

# テーブル一覧
mcp_supabase_list_tables (project_id: "qvtlwotzuzbavrzqhyvt")

# SQL実行（読み取り専用）
mcp_supabase_execute_sql (project_id: "qvtlwotzuzbavrzqhyvt", query: "SELECT ...")
```

**初回登録（必要な場合のみ）**:
```bash
security add-generic-password -a "$USER" -s codex_supabase_access_token -w '<YOUR_TOKEN>' -U
```

**WatchMe プロジェクトID**: `qvtlwotzuzbavrzqhyvt`

### iOS開発時のビルド検証
- コンパイルチェックのみ行う（シミュレーターやデバイス指定は不要）
- 実際の動作確認はユーザー側で実施
- ビルドコマンドの例：
  ```bash
  # ✅ 正しい：シンプルにコンパイルのみチェック
  xcodebuild -scheme <scheme_name> -sdk iphonesimulator build

  # ❌ 間違い：-destination指定は不要
  xcodebuild -scheme <scheme_name> -destination 'platform=iOS Simulator,name=iPhone 15' build
  ```

---

## 💻 よく使うコマンド

### EC2接続・管理
```bash
# EC2接続
ssh -i ~/watchme-key.pem ubuntu@3.24.16.82

# コンテナ状態確認
docker ps | grep watchme

# ログ確認（例：Vault API）
docker logs watchme-vault-api --tail 100 -f

# コンテナ再起動（例：Vault API）
cd /home/ubuntu/watchme-vault-api
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
```

### デプロイ（GitHub経由）
```bash
# 変更をプッシュ（CI/CD自動実行）
git add .
git commit -m "fix: 説明"
git push origin main
```

### ポート使用中の対処
```bash
lsof -i :8000
kill -9 <PID>
```

---

## 🔧 トラブルシューティング

### 環境変数が反映されない
→ コンテナ再起動が必要

### skippedステータスにならない（Vault API）
→ `/api/vault/app.py`の定数を確認
- SKIP_ENABLED = True
- SKIP_DEVICE_IDS = ['9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93']
- SKIP_HOURS = [23, 0, 1, 2, 3, 4, 5]

### Lambda関数が累積分析をトリガーしない
→ CloudWatchログで確認

---

## 📚 重要ドキュメント

### プロジェクト全体
- `/projects/watchme/server-configs/docs/README.md` - システム全体の構成
- `/projects/watchme/server-configs/docs/PROCESSING_ARCHITECTURE.md` - データ処理フロー
- `/projects/watchme/server-configs/docs/TECHNICAL_REFERENCE.md` - 技術仕様

### 作業手順
- `/projects/watchme/server-configs/docs/OPERATIONS_GUIDE.md` - デプロイ・運用手順
- `/projects/watchme/server-configs/docs/CICD_STANDARD_SPECIFICATION.md` - CI/CD設定

---

## 🚨 重要な設定値

### AWS
- **リージョン**: ap-southeast-2 (Sydney)
- **EC2**: 3.24.16.82 (t4g.small / Name=vault) ※2026-07-05実測。現在は無料枠で$0、終了後は月+約12USD見込み
- **S3バケット**: watchme-vault

### ポート番号（EC2 Docker）
- 8000: Vault API
- 8011: Aggregator API
- 8013: Vibe Transcriber
- 8017: Behavior Features
- 8018: Emotion Features
- 8030: Janitor API
- 8051: Profiler API
- 9000: Admin
- 9001: API Manager
- 8014: Avatar Uploader

### ポート番号（ローカル開発）
- 3001: watchme_v8 (React dashboard)
- 各APIのローカルポートはREADME.md参照

---

## 📁 ディレクトリ詳細

### 🎙️ 音声処理層（EC2 Docker）
- **Vault API** - S3音声ファイル配信ゲートウェイ
- **Behavior Features API** - 527種類の音響イベント検出
- **Emotion Features API** - 8感情認識
- **Vibe Transcriber API** - マルチプロバイダーASR文字起こし

### 📊 集計・分析層（EC2 Docker）
- **Aggregator API** - Spot/Daily集計、プロンプト生成
- **Profiler API** - LLM心理分析（Spot/Daily）

### ⚙️ 管理・インフラ層
- **API Manager** - API管理UI
- **Admin** - 管理ツール
- **Avatar Uploader** - アバター画像管理
- **Janitor API** - 6時間ごと音声削除

### ⏰ AWS Lambda（自動実行）
- **audio-processor** - S3イベント受信、SQSキュー
- **audio-worker** - 分析API実行、結果保存
- **watchme-janitor-trigger** - 6時間ごとJanitor実行
- **demo-data-generator-trigger** - 30分ごとデモデータ生成

### 🗄️ インフラ
- **EC2** - t4g.small (Sydney) - 全APIホスティング
- **S3** - watchme-vault バケット（音声ファイル保存）
- **Supabase** - 認証・データベース
- **Nginx** - リバースプロキシ（api.hey-watch.me）
- **systemd** - 15サービスのプロセス管理
- **Docker Network** - watchme-network (172.27.0.0/16)

### 📚 旧プロジェクト（休止中）
- ~~watchme_v8/~~ - 旧Reactダッシュボード（休止中）
- ~~deep-profile-app-v1/~~ - 旧Next.js 13プロファイル分析（休止中）
- ~~neuroprofile-app/~~ - 旧神経プロファイリングアプリ（休止中）

---

## 📝 追加リソース

- 各APIディレクトリのREADME.md - 個別API仕様・開発手順
- server-configs/docs/ - システム全体の技術ドキュメント
