# API階層化リストラクチャリング作業ログ

**作業開始日**: 2025-10-22
**担当**: Claude Code
**目的**: マイクロサービスAPIをドメイン駆動設計に基づいて階層化し、バージョン管理を導入

---

## 📋 作業概要

### 目標構造

```
/Users/kaya.matsumoto/projects/watchme/api/
  ├── behavior-analysis/          # 行動分析ドメイン
  │   ├── feature-extractor-v1/   # YamNet（レガシー）
  │   ├── feature-extractor-v2/   # AST（本番稼働中）
  │   └── aggregator/             # 集計API
  │
  ├── emotion-analysis/           # 感情分析ドメイン
  │   ├── feature-extractor-v1/   # OpenSMILE（レガシー）
  │   ├── feature-extractor-v2/   # Kushinada（検証中）
  │   ├── feature-extractor-v3/   # SUPERB（本番稼働中）
  │   └── aggregator/             # 感情スコア集計
  │
  └── vibe-analysis/              # 気分分析ドメイン
      ├── transcriber-v1/         # Whisper（レガシー）
      ├── transcriber-v2/         # Azure Speech（本番稼働中）
      ├── aggregator/             # プロンプト生成（本番稼働中）
      └── scorer/                 # ChatGPT分析（本番稼働中）
```

### 設計原則

1. **ドメイン駆動設計（DDD）**: 機能ドメインごとに階層化
2. **バージョン管理**: モデル変更に対応できるよう永続的にバージョンを保持
3. **機能ベース命名**: 技術（モデル名）ではなく、機能で命名
4. **引き継ぎ可能性**: コンテキスト跨ぎでも作業継続可能な記録

---

## 🎯 フェーズ1: ローカル環境のリストラクチャリング

### ステップ1: pending_接頭辞の削除

**目的**: 非公式マーカー`pending_`を削除し、正式なAPI名に統一

**対象ディレクトリ**:
- [ ] `pending_api-sed` → `api-sed`
- [ ] `pending_opensmile` → `opensmile`
- [ ] `pending_kushinada` → `kushinada`
- [ ] `pending_api_whisper_v1` → `api-whisper-v1`
- [ ] `pending_audio-enhancer` → `audio-enhancer`
- [ ] `pending_api_asc_v1` → `api-asc-v1`

**実行コマンド**:
```bash
cd /Users/kaya.matsumoto/projects/watchme/api

mv pending_api-sed api-sed
mv pending_opensmile opensmile
mv pending_kushinada kushinada
mv pending_api_whisper_v1 api-whisper-v1
mv pending_audio-enhancer audio-enhancer
mv pending_api_asc_v1 api-asc-v1
```

**状態**: ✅ 完了 (2025-10-22 13:57)

**結果**:
- ✅ `pending_api-sed` → `api-sed`
- ✅ `pending_opensmile` → `opensmile`
- ✅ `pending_kushinada` → `kushinada`
- ✅ `pending_api_whisper_v1` → `api-whisper-v1`
- ✅ `pending_audio-enhancer` → `audio-enhancer`
- ✅ `pending_api_asc_v1` → `api-asc-v1`

---

### ステップ2: behavior-analysis ドメイン構築

**目的**: 行動分析関連のAPIを統合

**対象**:
- [ ] `api-sed` → `behavior-analysis/feature-extractor-v1/` (YamNet)
- [ ] `ast` → `behavior-analysis/feature-extractor-v2/` (AST・本番)
- [ ] `api-sed-aggregator` → `behavior-analysis/aggregator/`

**実行コマンド**:
```bash
cd /Users/kaya.matsumoto/projects/watchme/api

mkdir -p behavior-analysis

mv api-sed behavior-analysis/feature-extractor-v1
mv ast behavior-analysis/feature-extractor-v2
mv api-sed-aggregator behavior-analysis/aggregator
```

**影響範囲**:
- ECRリポジトリ: `watchme-api-ast` → `watchme-behavior-analysis-feature-extractor-v2`
- エンドポイント: `/behavior-features/` → `/behavior-analysis/features/` (後日変更)
- Dockerコンテナ名: `ast-api` → `behavior-analysis-feature-extractor-v2`

**状態**: ✅ 完了 (2025-10-22 13:57)

**結果**:
- ✅ `api-sed` → `behavior-analysis/feature-extractor-v1/`
- ✅ `ast` → `behavior-analysis/feature-extractor-v2/`
- ✅ `api-sed-aggregator` → `behavior-analysis/aggregator/`

---

### ステップ3: emotion-analysis ドメイン構築

**目的**: 感情分析関連のAPIを統合

**対象**:
- [ ] `opensmile` → `emotion-analysis/feature-extractor-v1/` (OpenSMILE)
- [ ] `kushinada` → `emotion-analysis/feature-extractor-v2/` (Kushinada)
- [ ] `superb` → `emotion-analysis/feature-extractor-v3/` (SUPERB・本番)
- [ ] `opensmile-aggregator` → `emotion-analysis/aggregator/`

**実行コマンド**:
```bash
cd /Users/kaya.matsumoto/projects/watchme/api

mkdir -p emotion-analysis

mv opensmile emotion-analysis/feature-extractor-v1
mv kushinada emotion-analysis/feature-extractor-v2
mv superb emotion-analysis/feature-extractor-v3
mv opensmile-aggregator emotion-analysis/aggregator
```

**影響範囲**:
- ECRリポジトリ: `watchme-superb-api` → `watchme-emotion-analysis-feature-extractor-v3`
- エンドポイント: `/emotion-features/` → `/emotion-analysis/features/` (後日変更)
- Dockerコンテナ名: `superb-api` → `emotion-analysis-feature-extractor-v3`

**状態**: ✅ 完了 (2025-10-22 13:57)

**結果**:
- ✅ `opensmile` → `emotion-analysis/feature-extractor-v1/`
- ✅ `kushinada` → `emotion-analysis/feature-extractor-v2/`
- ✅ `superb` → `emotion-analysis/feature-extractor-v3/`
- ✅ `opensmile-aggregator` → `emotion-analysis/aggregator/`

---

### ステップ4: vibe-analysis ドメイン構築

**目的**: 気分分析関連のAPIを統合（外部ディレクトリも含む）

**対象**:
- [ ] `api-whisper-v1` → `vibe-analysis/transcriber-v1/` (Whisper)
- [ ] `/Users/kaya.matsumoto/api_azure-speech_v1` → `vibe-analysis/transcriber-v2/` (Azure・本番)
- [ ] `vibe-aggregator` → `vibe-analysis/aggregator/` (プロンプト生成・本番)
- [ ] `/Users/kaya.matsumoto/api_gpt_v1` → `vibe-analysis/scorer/` (ChatGPT・本番)

**実行コマンド**:
```bash
cd /Users/kaya.matsumoto/projects/watchme/api

mkdir -p vibe-analysis

mv api-whisper-v1 vibe-analysis/transcriber-v1
mv /Users/kaya.matsumoto/api_azure-speech_v1 vibe-analysis/transcriber-v2
mv vibe-aggregator vibe-analysis/aggregator
mv /Users/kaya.matsumoto/api_gpt_v1 vibe-analysis/scorer
```

**影響範囲**:
- ECRリポジトリ:
  - `watchme-api-transcriber-v2` → `watchme-vibe-analysis-transcriber-v2`
  - `watchme-api-vibe-aggregator` → `watchme-vibe-analysis-aggregator`
  - (scorer用の新規作成が必要)
- エンドポイント:
  - `/vibe-transcriber-v2/` → `/vibe-analysis/transcription/` (後日変更)
  - `/vibe-aggregator/` → `/vibe-analysis/aggregation/` (後日変更)
  - `/vibe-scorer/` → `/vibe-analysis/scoring/` (後日変更)

**状態**: ✅ 完了 (2025-10-22 13:57)

**結果**:
- ✅ `api-whisper-v1` → `vibe-analysis/transcriber-v1/`
- ✅ `/Users/kaya.matsumoto/api_azure-speech_v1` → `vibe-analysis/transcriber-v2/`
- ✅ `vibe-aggregator` → `vibe-analysis/aggregator/`
- ✅ `/Users/kaya.matsumoto/api_gpt_v1` → `vibe-analysis/scorer/`

---

### ステップ5: Git設定の確認

**目的**: 各リポジトリのGit設定が正常か確認

**確認コマンド**:
```bash
cd /Users/kaya.matsumoto/projects/watchme/api/behavior-analysis/feature-extractor-v2
git status
git remote -v

cd /Users/kaya.matsumoto/projects/watchme/api/emotion-analysis/feature-extractor-v3
git status
git remote -v

cd /Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/transcriber-v2
git status
git remote -v

cd /Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/aggregator
git status
git remote -v

cd /Users/kaya.matsumoto/projects/watchme/api/vibe-analysis/scorer
git status
git remote -v
```

**状態**: ✅ 完了 (2025-10-22 13:58)

**結果**: 全てのGitリポジトリが正常に動作確認済み
- ✅ `behavior-analysis/feature-extractor-v2`: `git@github.com:hey-watchme/api-sed-ast.git`
- ✅ `emotion-analysis/feature-extractor-v3`: `git@github.com:hey-watchme/api-superb.git`
- ✅ `vibe-analysis/transcriber-v2`: `git@github.com:hey-watchme/api-asr-azure.git`
- ✅ `vibe-analysis/aggregator`: `git@github.com:hey-watchme/api-vibe-aggregator.git`
- ✅ `vibe-analysis/scorer`: `git@github.com:matsumotokaya/watchme-api-whisper-gpt.git`

---

### ステップ6: venv再作成（絶対パス解消）

**目的**: 移動後の絶対パス参照エラーを解消

**対象**: 本番稼働中の全API

**実行手順（各ディレクトリで）**:
```bash
# 例: behavior-analysis/feature-extractor-v2
cd /Users/kaya.matsumoto/projects/watchme/api/behavior-analysis/feature-extractor-v2

# 既存venvを削除
rm -rf venv

# 新規作成
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
pip install -r requirements.txt

# 動作確認
python main_supabase.py
```

**状態**: ❌ 不要（2025-10-22 確認）

**理由**:
- 本番環境: 完全にDockerコンテナで運用
- ローカルテスト: Docker Composeで実施
- venvディレクトリ: 過去の開発時の名残で、現在は使用していない
- ディレクトリ移動してもDocker内部では影響なし

---

## 🎯 フェーズ2: 本番環境の更新

### 事前調査（2025-10-22）

#### Lambda関数のエンドポイント確認

**確認結果**: Lambda関数は環境変数`API_BASE_URL`（`https://api.hey-watch.me`）経由でNginxを通してAPIを呼び出すため、**コンテナ名の変更による影響なし**。

**詳細**:
- `watchme-audio-worker`: 7つのAPIエンドポイントを使用（すべてHTTPS経由）
- `watchme-dashboard-summary-worker`: `/vibe-aggregator/generate-dashboard-summary`を使用
- `watchme-dashboard-analysis-worker`: `/vibe-scorer/analyze-dashboard-summary`を使用
- 詳細は`PROCESSING_ARCHITECTURE.md`の「Lambda関数が呼び出すAPIエンドポイント」セクションに記載

#### コンテナ間参照の確認

**確認対象**:
- ✅ `/api/vault` - 参照なし
- ✅ `/api/janitor` - 参照なし
- ✅ `/api/demo-generator` - 参照なし
- ⚠️ `/api/api-manager/scheduler/run-api-process-docker.py` - **7つのコンテナ名を直接参照**

**api-managerが参照するコンテナ名**:
```python
"http://api_gen_prompt_mood_chart:8009/..."  # → vibe-analysis-aggregator
"http://api-gpt-v1:8002/..."                 # → vibe-analysis-scorer
"http://ast-api:8017/..."                    # → behavior-analysis-feature-extractor-v2
"http://superb-api:8018/..."                 # → emotion-analysis-feature-extractor-v3
"http://vibe-transcriber-v2:8013/..."        # → vibe-analysis-transcriber-v2
"http://api-sed-aggregator:8010/..."         # → （変更なし）
"http://opensmile-aggregator:8012/..."       # → （変更なし）
```

**結論**: api-managerのコンテナ名参照を同時に更新する必要あり。

---

### ステップ7: 新規ECRリポジトリの作成

**方針変更**: ECRリポジトリは名前変更不可のため、新規作成し、旧リポジトリは後で削除

**理由**: AWS Console/CLIともにECRリポジトリの名前変更機能は存在しない

**作成リポジトリ**:
- ✅ `watchme-behavior-analysis-feature-extractor-v2`
- ✅ `watchme-emotion-analysis-feature-extractor-v3`
- ✅ `watchme-vibe-analysis-transcriber-v2`
- ✅ `watchme-vibe-analysis-aggregator`
- ✅ `watchme-vibe-analysis-scorer`

**状態**: ✅ 完了 (2025-10-22 17:14)

**実行コマンド** (AWS CLI):

```bash
# リージョン: ap-southeast-2 (Sydney)

# 1. behavior-analysis-feature-extractor-v2
aws ecr create-repository \
  --repository-name watchme-behavior-analysis-feature-extractor-v2 \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true

# 2. emotion-analysis-feature-extractor-v3
aws ecr create-repository \
  --repository-name watchme-emotion-analysis-feature-extractor-v3 \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true

# 3. vibe-analysis-transcriber-v2
aws ecr create-repository \
  --repository-name watchme-vibe-analysis-transcriber-v2 \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true

# 4. vibe-analysis-aggregator
aws ecr create-repository \
  --repository-name watchme-vibe-analysis-aggregator \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true

# 5. vibe-analysis-scorer
aws ecr create-repository \
  --repository-name watchme-vibe-analysis-scorer \
  --region ap-southeast-2 \
  --image-scanning-configuration scanOnPush=true
```

**作成結果**:
- ✅ `watchme-behavior-analysis-feature-extractor-v2` - 2025-10-22 17:14:09
- ✅ `watchme-emotion-analysis-feature-extractor-v3` - 2025-10-22 17:14:16
- ✅ `watchme-vibe-analysis-transcriber-v2` - 2025-10-22 17:14:24
- ✅ `watchme-vibe-analysis-aggregator` - 2025-10-22 17:14:29
- ✅ `watchme-vibe-analysis-scorer` - 2025-10-22 17:14:35

**注意事項**:
- 旧リポジトリ(`watchme-api-ast`等)は削除せず残しておく（動作確認後に削除）
- 次のGitHub Actionsデプロイ時に新リポジトリへイメージがプッシュされる
- 旧リポジトリのイメージは手動コピー不要

---

### ステップ8: GitHub Actions更新

**対象**: 5つのGitHubリポジトリの`.github/workflows/deploy-to-ecr.yml`

| リポジトリ | 現在のECR_REPOSITORY | 新ECR_REPOSITORY | 状態 |
|-----------|---------------------|------------------|------|
| `api-sed-ast` | `watchme-api-ast` | `watchme-behavior-analysis-feature-extractor-v2` | ✅ 完了 |
| `api-superb` | なし | `watchme-emotion-analysis-feature-extractor-v3` | ✅ 完了 (新規作成) |
| `api-asr-azure` | `watchme-api-transcriber-v2` | `watchme-vibe-analysis-transcriber-v2` | ✅ 完了 |
| `api-vibe-aggregator` | `watchme-api-vibe-aggregator` | `watchme-vibe-analysis-aggregator` | ✅ 完了 |
| `watchme-api-whisper-gpt` | `watchme-api-vibe-scorer` | `watchme-vibe-analysis-scorer` | ✅ 完了 |

**変更内容**: ECR_REPOSITORY環境変数の値を変更

**状態**: ✅ 完了 (2025-10-22 17:20)

**実施内容**:

1. **behavior-analysis-feature-extractor-v2** (api-sed-ast)
   - コミット: 83c90d6
   - ファイル: `.github/workflows/deploy-to-ecr.yml`
   - 変更: ECR_REPOSITORY を `watchme-behavior-analysis-feature-extractor-v2` に更新

2. **emotion-analysis-feature-extractor-v3** (api-superb)
   - コミット: 0f68140
   - ファイル: `.github/workflows/deploy-to-ecr.yml` (新規作成)
   - 内容: ECR_REPOSITORY = `watchme-emotion-analysis-feature-extractor-v3`

3. **vibe-analysis-transcriber-v2** (api-asr-azure)
   - コミット: 0458ad4
   - ファイル: `.github/workflows/deploy-to-ecr.yml`
   - 変更: ECR_REPOSITORY を `watchme-vibe-analysis-transcriber-v2` に更新

4. **vibe-analysis-aggregator** (api-vibe-aggregator)
   - コミット: be8ee8c
   - ファイル: `.github/workflows/deploy-to-ecr.yml`
   - 変更: ECR_REPOSITORY を `watchme-vibe-analysis-aggregator` に更新

5. **vibe-analysis-scorer** (watchme-api-whisper-gpt)
   - コミット: 9b8bc0a
   - ファイル: `.github/workflows/deploy-ecr.yml`
   - 変更: ECR_REPOSITORY を `watchme-vibe-analysis-scorer` に更新

**注意事項**:
- 次回のGitHub Actionsデプロイ時に、新しいECRリポジトリへイメージが自動プッシュされる
- EC2上のdocker-compose.prod.ymlを更新するまで、デプロイは行わないこと

---

### ステップ9: EC2ディレクトリ構造変更とdocker-compose更新

**ディレクトリ変更**:
- [ ] `/home/ubuntu/api_ast` → `/home/ubuntu/behavior-analysis-feature-extractor-v2`
- [ ] `/home/ubuntu/superb` → `/home/ubuntu/emotion-analysis-feature-extractor-v3`
- [ ] `/home/ubuntu/vibe-transcriber-v2` → `/home/ubuntu/vibe-analysis-transcriber-v2`
- [ ] `/home/ubuntu/vibe-aggregator` → `/home/ubuntu/vibe-analysis-aggregator`
- [ ] `/home/ubuntu/api_gpt_v1` → `/home/ubuntu/vibe-analysis-scorer`

**docker-compose.prod.ymlのコンテナ名変更**:
- [ ] `ast-api` → `behavior-analysis-feature-extractor-v2`
- [ ] `superb-api` → `emotion-analysis-feature-extractor-v3`
- [ ] `vibe-transcriber-v2` → `vibe-analysis-transcriber-v2`
- [ ] `api_gen_prompt_mood_chart` → `vibe-analysis-aggregator`
- [ ] `api-gpt-v1` → `vibe-analysis-scorer`

**注意**: Gitリモート設定は保持すること

**状態**: 🔄 未実行

---

### ステップ9.5: api-managerのコンテナ名参照更新

**対象ファイル**: `/Users/kaya.matsumoto/projects/watchme/api/api-manager/scheduler/run-api-process-docker.py`

**変更箇所**:
```python
# 行82: vibe-aggregator
"endpoint": "http://vibe-analysis-aggregator:8009/generate-mood-prompt-supabase"

# 行88: vibe-scorer
"endpoint": "http://vibe-analysis-scorer:8002/analyze-vibegraph-supabase"

# 行104: behavior-features (AST API)
"endpoint": "http://behavior-analysis-feature-extractor-v2:8017/fetch-and-process-paths"

# 行113: emotion-features (SUPERB API)
"endpoint": "http://emotion-analysis-feature-extractor-v3:8018/process/emotion-features"

# 行122: azure-transcriber
"endpoint": "http://vibe-analysis-transcriber-v2:8013/fetch-and-transcribe"

# 行133: timeblock-prompt
"endpoint": "http://vibe-analysis-aggregator:8009/generate-timeblock-prompt"

# 行146: timeblock-analysis
"endpoint": "http://vibe-analysis-scorer:8002/analyze-timeblock"

# 行156: dashboard-summary
"endpoint": "http://vibe-analysis-aggregator:8009/generate-dashboard-summary"

# 行163: dashboard-summary-analysis
"endpoint": "http://vibe-analysis-scorer:8002/analyze-dashboard-summary"
```

**実施日**: 2025-10-22

**コミット**: `b577745` (api-manager)

**状態**: ✅ 完了

**注意**: この変更はローカル環境のみ。本番環境では、EC2上のコンテナ名変更と同時に適用される必要があります。

---

### ステップ10: Nginx設定更新

**ファイル**: `/etc/nginx/sites-available/api.hey-watch.me`

**変更内容**: 新旧エンドポイントの並行運用（段階的移行）

| 現在のエンドポイント | 新エンドポイント | proxy_pass先（コンテナ名は変更） |
|-------------------|----------------|--------------------------------|
| `/vibe-transcriber-v2/` | `/vibe-analysis/transcription/` | `http://localhost:8013/` |
| `/behavior-features/` | `/behavior-analysis/features/` | `http://localhost:8017/` |
| `/emotion-features/` | `/emotion-analysis/features/` | `http://localhost:8018/` |
| `/behavior-aggregator/` | `/behavior-analysis/aggregation/` | `http://localhost:8010/` |
| `/emotion-aggregator/` | `/emotion-analysis/aggregation/` | `http://localhost:8012/` |
| `/vibe-aggregator/` | `/vibe-analysis/aggregation/` | `http://localhost:8009/` |
| `/vibe-scorer/` | `/vibe-analysis/scoring/` | `http://localhost:8002/` |

**注意**: 旧エンドポイントも一定期間残すこと（後日削除）

**状態**: 🔄 未実行

---

### ステップ11: systemdサービス更新

**対象**: 5つのsystemdサービスファイルのディレクトリパス変更

| サービスファイル | 変更内容 |
|----------------|---------|
| `behavior-analysis-feature-extractor-v2.service`（新規作成） | `/home/ubuntu/behavior-analysis-feature-extractor-v2/docker-compose.prod.yml` |
| `emotion-analysis-feature-extractor-v3.service`（新規作成） | `/home/ubuntu/emotion-analysis-feature-extractor-v3/docker-compose.prod.yml` |
| `vibe-analysis-transcriber-v2.service`（新規作成） | `/home/ubuntu/vibe-analysis-transcriber-v2/docker-compose.prod.yml` |
| `vibe-analysis-aggregator.service`（新規作成） | `/home/ubuntu/vibe-analysis-aggregator/docker-compose.prod.yml` |
| `vibe-analysis-scorer.service`（新規作成） | `/home/ubuntu/vibe-analysis-scorer/docker-compose.prod.yml` |

**旧サービスファイルの無効化**:
- `ast-api.service`
- `superb-api.service`
- `vibe-transcriber-v2.service`
- `vibe-aggregator.service`
- `api-gpt-v1.service`

**状態**: 🔄 未実行

---

### ステップ12: Lambda関数の確認

**確認結果**: Lambda関数は環境変数`API_BASE_URL`経由でHTTPSエンドポイントを使用するため、**変更不要**。

**詳細**:
- すべてのLambda関数は`https://api.hey-watch.me`を基準にエンドポイントを構築
- Nginxのリバースプロキシを経由するため、コンテナ名の変更による影響なし
- エンドポイントパスは将来的に変更予定だが、新旧並行運用するため影響なし

**状態**: ✅ 確認完了（変更不要）

---

## 📝 作業メモ・注意事項

### リスク管理
- ✅ 外部利用者なし → 長時間のサービス停止OK
- ✅ バージョン管理により、旧モデルも永続保持
- ⚠️ コンテナ間通信はコンテナ名で参照（IP不可）
- ⚠️ watchme-networkは継続使用（変更なし）

### CICD状況（2025-10-22確認）

| API | CICD状態 | 対応状況 |
|-----|---------|---------|
| behavior-analysis-feature-extractor-v2 | ✅ あり | 正常動作 |
| emotion-analysis-feature-extractor-v3 | ✅ あり | 手動実行が必要 |
| emotion-analysis/aggregator | ❌ なし | **将来タスク: CICD実装が必要** |

**将来タスク**: emotion-analysis/aggregatorのCICD実装
- 現在は本番稼働中で安定しているため、本番移行後に別タスクとして実施
- 参考: behavior-analysis/aggregatorやemotion-analysis/feature-extractor-v3のワークフロー

### 次回作業時の引き継ぎポイント
1. このログファイルの「状態」列を確認
2. 未実行（🔄）のステップから再開
3. 完了したら ✅ に変更
4. エラーが発生したら ❌ を記録し、詳細をメモ

---

## 🔄 進捗状況（2025-10-22 19:30 更新）

- **フェーズ1（ローカル）**: 100% (6/6ステップ完了) - ✅ 完了
- **フェーズ2（本番準備）**: 100% 完了 ✅
  - 事前調査: 100% 完了 ✅
  - ローカル準備: 100% 完了 ✅
  - **emotion-analysis系のCICD実装**: 100% 完了 ✅ **NEW!**
    - ✅ emotion-analysis-feature-extractor-v3のCICD作成 (2025-10-22 19:00)
    - ✅ emotion-analysis-aggregatorのCICD作成 (2025-10-22 19:20)
    - ✅ 両リポジトリのコミット＆プッシュ完了
  - ECR & GitHub Actions: 100% 完了 ✅
    - ✅ ステップ7: ECRリポジトリ作成 (2025-10-22 17:14)
    - ✅ ステップ8: GitHub Actions更新 (2025-10-22 17:20)
- **フェーズ3（本番環境実装）**: 0% (0/4ステップ) - 🔄 **次のセッションで実施**
    - 🔄 ステップ9: EC2ディレクトリ構造変更
    - 🔄 ステップ10: Nginx設定更新
    - 🔄 ステップ11: systemdサービス更新
    - 🔄 ステップ12: 動作確認
- **全体進捗**: 75% (9/12ステップ完了)

### ✅ 完了した作業（2025-10-22 19:30更新）

#### セッション1（午前）: 事前調査とローカル準備
1. **事前調査**
   - Lambda関数のエンドポイント確認
   - コンテナ間参照の確認（vault, janitor, demo-generator, api-manager）
   - PROCESSING_ARCHITECTURE.mdの更新（コンテナ名列追加、Lambda関数詳細追加）

2. **ローカル環境の準備**
   - api-managerのコンテナ名参照を新名称に更新（10箇所）
   - コミット完了:
     - `b577745` (api-manager)
     - `4494fda` (server-configs)

#### セッション2（夕方）: emotion-analysis系CICD実装
3. **リポジトリ名変更**
   - `api-superb` → `api-emotion-analysis-feature-extractor-v3` (オーガニゼーション移動)
   - `watchme-opensmile-aggregator` → `api-emotion-analysis-aggregator` (オーガニゼーション移動)

4. **emotion-analysis-feature-extractor-v3のCICD実装**
   - docker-compose.prod.yml更新（ECRリポジトリ名、コンテナ名）
   - run-prod.sh新規作成（CICD標準仕様準拠）
   - GitHub Actions workflow完全実装
   - コミット: `1623eaf`

5. **emotion-analysis-aggregatorのCICD実装**
   - docker-compose.prod.yml更新（ECRリポジトリ名、コンテナ名、env_file方式に変更）
   - run-prod.sh更新（CICD標準仕様準拠、3層削除アプローチ実装）
   - GitHub Actions workflow新規作成
   - コミット: `01b0832`

6. **重要な変更点**
   - 両APIとも`env_file: .env`方式に統一（environmentからの移行）
   - ポートバインディングを`127.0.0.1`に変更（セキュリティ向上）
   - コンテナ削除時に旧コンテナ名も削除する処理を追加

### 🔜 次回作業のチェックリスト（2025-10-22 19:30更新）

**準備完了** ✅:
- ✅ 影響範囲の特定完了
- ✅ 作業手順の文書化完了
- ✅ コンテナ名参照箇所の特定完了
- ✅ api-managerの更新完了（ローカル）
- ✅ **emotion-analysis系2APIのCICD実装完了** ← NEW!
- ✅ ECRリポジトリ作成完了（5個）
- ✅ GitHub Actions更新完了（5リポジトリ）

**次回セッションで実施すること**:

#### 事前準備（オプション）
- [ ] emotion-analysis系2APIのGitHub Actionsを手動実行してECRイメージを事前作成
  - https://github.com/hey-watchme/api-emotion-analysis-feature-extractor-v3/actions
  - https://github.com/hey-watchme/api-emotion-analysis-aggregator/actions
  - （注: EC2ディレクトリがないためデプロイは失敗するが、ECRプッシュは成功する）

#### 本番環境での実施（一連の流れで実施）

1. [ ] **EC2サーバーへSSH接続**
   ```bash
   ssh -i /Users/kaya.matsumoto/watchme-key.pem ubuntu@3.24.16.82
   ```

2. [ ] **EC2ディレクトリ構造変更**（所要時間: 20分）
   ```bash
   # 既存ディレクトリのバックアップ（念のため）
   cd /home/ubuntu

   # 5つのディレクトリをリネーム
   mv superb emotion-analysis-feature-extractor-v3
   mv opensmile-aggregator emotion-analysis-aggregator
   mv api_ast behavior-analysis-feature-extractor-v2
   mv vibe-transcriber-v2 vibe-analysis-transcriber-v2
   mv watchme-api-vibe-aggregator vibe-analysis-aggregator

   # （api_gpt_v1は既に移動済みのため不要）
   ```

3. [ ] **各ディレクトリでの初期化**（所要時間: 15分）
   ```bash
   # emotion-analysis-feature-extractor-v3
   cd /home/ubuntu/emotion-analysis-feature-extractor-v3
   # 必要ファイルは GitHub Actionsが自動配置するため何もしない

   # emotion-analysis-aggregator
   cd /home/ubuntu/emotion-analysis-aggregator
   # 同上
   ```

4. [ ] **Nginx設定更新**（所要時間: 15分）
   - ファイル: `/etc/nginx/sites-available/api.hey-watch.me`
   - 新旧エンドポイント並行運用
   - 設定テスト: `sudo nginx -t`
   - リロード: `sudo systemctl reload nginx`

5. [ ] **systemdサービス更新**（所要時間: 20分）
   - 新規サービスファイル作成（5個）
   - 旧サービス無効化（5個）
   - サービス再起動

6. [ ] **GitHub Actions手動実行でデプロイ**（所要時間: 30分）
   - 各リポジトリで手動実行
   - デプロイの成功を確認

7. [ ] **動作確認とヘルスチェック**（所要時間: 30分）
   - 各APIのヘルスチェック
   - コンテナ起動状態確認
   - Lambdaからの疎通確認

**合計所要時間**: 約2.5時間（EC2作業開始から完了まで）

**注意事項**:
- emotion-analysis系2APIは新しいCICDパイプラインが完成しているため、GitHub Actionsからの自動デプロイが可能
- 他のAPIも同様にGitHub Actionsを使用して自動デプロイ推奨

---

## 📚 関連ドキュメント

- [README.md](./README.md) - サーバー設定の全体概要
- [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md) - 音声処理アーキテクチャ
- [OPERATIONS_GUIDE.md](./OPERATIONS_GUIDE.md) - 運用ガイド
- [TECHNICAL_REFERENCE.md](./TECHNICAL_REFERENCE.md) - 技術仕様

---

---

## 📝 次回作業者への引き継ぎ事項（2025-10-22作成）

### 🎯 現状サマリー

**完了事項**:
- ✅ フェーズ1（ローカルリストラクチャリング）: 83%完了
- ✅ フェーズ2事前調査: 100%完了
- ✅ ローカル環境のapi-manager更新: 100%完了

**次のステップ**:
本番環境（EC2）でのリストラクチャリング実施

### 📋 作業開始前の確認事項

1. **必須ドキュメントの確認**
   - このファイル（API_RESTRUCTURE_LOG.md）を最初から最後まで読む
   - PROCESSING_ARCHITECTURE.mdの「コンテナ名の重要性」セクションを確認
   - server-configs/README.mdでEC2インフラ構成を確認

2. **影響範囲の理解**
   - Lambda関数: 影響なし（HTTPSエンドポイント経由のため）
   - api-manager: ✅ 更新済み（ローカルのみ、本番反映待ち）
   - 他サービス（vault, janitor, demo-generator）: 影響なし

3. **リスク確認**
   - サービス停止時間: 約2時間を見込む
   - 外部利用者なし: 長時間停止OK
   - バックアップ: ECR履歴あり、ディレクトリは手動バックアップ推奨

### 🚀 次回作業の流れ

#### ステップ1: ECRリポジトリのリネーム（15分）

AWSマネジメントコンソール > ECR で以下を実施:

| 現在のECR | 新ECR | 操作 |
|----------|-------|------|
| `watchme-api-ast` | `watchme-behavior-analysis-feature-extractor-v2` | リネーム |
| `watchme-superb-api` | `watchme-emotion-analysis-feature-extractor-v3` | リネーム |
| `watchme-api-transcriber-v2` | `watchme-vibe-analysis-transcriber-v2` | リネーム |
| `watchme-api-vibe-aggregator` | `watchme-vibe-analysis-aggregator` | リネーム |
| なし | `watchme-vibe-analysis-scorer` | 新規作成 |

#### ステップ2: GitHub Actionsの更新（10分）

以下5リポジトリの`.github/workflows/deploy-to-ecr.yml`で`ECR_REPOSITORY`環境変数を変更:

1. `api-sed-ast` → `watchme-behavior-analysis-feature-extractor-v2`
2. `api-superb` → `watchme-emotion-analysis-feature-extractor-v3`
3. `api-asr-azure` → `watchme-vibe-analysis-transcriber-v2`
4. `api-vibe-aggregator` → `watchme-vibe-analysis-aggregator`
5. `watchme-api-whisper-gpt` → `watchme-vibe-analysis-scorer`

各リポジトリでコミット＆プッシュ。

#### ステップ3〜7: EC2サーバーでの作業（90分）

詳細は上記「次回作業のチェックリスト」を参照。

**重要**: EC2作業は一連の流れで実施すること（中断しない）。

### ⚠️ トラブルシューティング

**問題**: コンテナが起動しない

→ ログ確認: `docker logs <container_name>`
→ ネットワーク確認: `docker network inspect watchme-network`

**問題**: Nginxエラー

→ 設定テスト: `sudo nginx -t`
→ ログ確認: `sudo tail -f /var/log/nginx/error.log`

**問題**: api-managerがコンテナに接続できない

→ コンテナ名を確認: `docker ps | grep <container_name>`
→ ネットワーク接続確認: `docker exec api-manager ping <container_name>`

### 📞 問題が発生した場合

1. このログファイルに詳細を記録
2. 状態を ❌ に変更
3. エラーメッセージ、スタックトレース、実行コマンドを記録
4. 可能であればロールバック手順も記録

### 🎓 学んだこと（次回作業者への知見）

- Lambda関数はHTTPSエンドポイント経由なので、コンテナ名変更の影響を受けない
- api-managerのようなスケジューラーは、コンテナ名を直接参照する可能性が高い
- ドメイン駆動設計では、コンテナ名を機能ベースにすることで、将来のモデル変更に強くなる

---

**最終更新**: 2025-10-22
**作業実施者**: Claude Code
**次回作業者へ**: 上記「次回作業の流れ」に従って実施してください。不明点があればこのログファイル全体を参照してください。
