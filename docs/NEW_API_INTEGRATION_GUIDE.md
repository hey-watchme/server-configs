# 新規API導入 標準手順書

最終更新: 2026-01-12

---

## 🎯 目的

新しい外部API（ASR、LLM、翻訳など）を導入する際の標準手順を定義し、**推測による実装を防ぐ**。

---

## ⚠️ 基本原則

### 絶対に守るべきルール

1. **公式ドキュメントを必ず読む**（推測で実装しない）
2. **不明点があれば即座にSTOP**（推測で進めない）
3. **バージョン番号はPyPIで確認**（存在確認必須）
4. **公式サンプルコードを完全にコピー**（独自解釈しない）
5. **環境変数は3箇所セットで設定**（GitHub Secrets + Workflow + docker-compose）

---

## 📋 導入手順（チェックリスト）

### Phase 1: 事前調査（実装前）

#### 1-1. 公式ドキュメントの確認

```bash
# 必ず以下を確認
✅ 公式サイトのドキュメント（Getting Started）
✅ PyPI（パッケージが存在するか、最新バージョン）
✅ GitHub リポジトリ（公式サンプルコード）
✅ API仕様書（認証方法、エンドポイント）
```

**確認すべき項目**:
- [ ] パッケージ名（正確な名前）
- [ ] 最新バージョン（PyPIで確認）
- [ ] Python バージョン要件
- [ ] 認証方法（APIキー、トークンなど）
- [ ] 依存パッケージ
- [ ] 公式サンプルコード

**ツール**:
```bash
# PyPIでバージョン確認
WebSearch: "{package-name} pypi latest version"
WebFetch: https://pypi.org/project/{package-name}/

# 公式ドキュメント確認
WebFetch: {official-docs-url}
```

#### 1-2. APIキーの取得

```bash
✅ 公式サイトでアカウント作成
✅ APIキー発行
✅ 利用制限・料金を確認
✅ テスト用のサンプルデータを確認
```

**ローカル環境に保存**:
```bash
# backend/.env に追加
{API_NAME}_API_KEY=your_key_here
```

---

### Phase 2: ローカル実装・テスト

#### 2-1. パッケージインストール

```bash
# requirements.txt に追加（PyPIで確認したバージョン）
{package-name}=={version}

# ローカルでインストール
pip3 install {package-name}=={version}
```

**確認**:
```bash
# パッケージがインストールされたか確認
pip3 show {package-name}
```

#### 2-2. プロバイダー実装

**ファイル作成**:
```
backend/services/asr_providers/{provider_name}_provider.py
```

**実装方針**:
- ✅ **公式サンプルコードを完全にコピー**
- ✅ 独自解釈・推測を一切しない
- ✅ 不明なパラメータは公式ドキュメントで確認
- ❌ 「たぶんこうだろう」で実装しない

**テンプレート**:
```python
import os
from typing import BinaryIO, Dict, Any
import logging

logger = logging.getLogger(__name__)

class {ProviderName}Service:
    """
    {API Name} Service
    Official docs: {URL}
    """

    def __init__(self):
        api_key = os.getenv("{API_NAME}_API_KEY")
        if not api_key:
            raise ValueError("{API_NAME}_API_KEY environment variable not set")
        self.api_key = api_key
        logger.info("{API Name} initialized")

    async def process(self, input_data: Any) -> Dict[str, Any]:
        """
        Process data using {API Name}
        Following official example: {URL}
        """
        try:
            # 公式サンプルコードをここにコピー
            pass
        except Exception as e:
            logger.error(f"{API Name} error: {str(e)}")
            raise
```

#### 2-3. ローカルテスト

**テストスクリプト作成**:
```python
# test-{provider}.py
import asyncio
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')

async def test():
    # 公式サンプルコードをコピー
    pass

asyncio.run(test())
```

**実行**:
```bash
# ローカルでテスト実行
python3 test-{provider}.py
```

**確認項目**:
- [ ] APIキーが正しく読み込まれるか
- [ ] APIリクエストが成功するか
- [ ] レスポンスが期待通りか
- [ ] エラーハンドリングが動作するか

---

### Phase 3: 環境変数設定（3箇所セット）

#### 3-1. GitHub Secrets に追加

```bash
gh secret set {API_NAME}_API_KEY --body "your_key_here" --repo {org}/{repo}
```

#### 3-2. GitHub Actions ワークフローに追加

**ファイル**: `.github/workflows/deploy-to-ecr.yml`

**2箇所を更新**:

```yaml
# 1. env: セクションに追加
env:
  {API_NAME}_API_KEY: ${{ secrets.{API_NAME}_API_KEY }}

# 2. .env作成スクリプトに追加
run: |
  ssh ${EC2_USER}@${EC2_HOST} << ENDSSH
    echo "{API_NAME}_API_KEY=${ {API_NAME}_API_KEY}" >> .env
  ENDSSH
```

#### 3-3. docker-compose.prod.yml に追加

```yaml
environment:
  - {API_NAME}_API_KEY=${ {API_NAME}_API_KEY}
```

**確認チェックリスト**:
- [ ] GitHub Secrets に追加済み
- [ ] Workflow の `env:` に追加済み
- [ ] Workflow の `echo` コマンドに追加済み
- [ ] docker-compose.prod.yml に追加済み

---

### Phase 4: 本番デプロイ・検証

#### 4-1. デプロイ

```bash
# コミット・プッシュ
git add .
git commit -m "feat: add {API Name} integration"
git push origin main

# デプロイ状況確認
gh run list --limit 1
```

#### 4-2. デプロイ完了確認

```bash
# GitHub Actions でデプロイ成功を確認
gh run list --limit 1

# コンテナが起動しているか確認
ssh -i ~/watchme-key.pem ubuntu@{EC2_HOST}
docker ps | grep {container-name}
```

#### 4-3. 環境変数確認

```bash
# コンテナ内で環境変数が設定されているか確認
docker exec {container-name} printenv | grep {API_NAME}
```

**期待される出力**:
```
{API_NAME}_API_KEY=your_key_here
```

#### 4-4. 本番環境でテスト実行

```bash
# テストスクリプトをコンテナにコピー
docker cp test-{provider}.py {container-name}:/app/

# コンテナ内で実行
docker exec {container-name} python3 /app/test-{provider}.py
```

**確認項目**:
- [ ] 環境変数が正しく読み込まれるか
- [ ] APIリクエストが成功するか
- [ ] レスポンスが期待通りか
- [ ] エラーが発生しないか

---

## 🚨 よくある失敗パターン

### 失敗例 1: バージョン番号を推測

❌ **間違い**:
```txt
# 「新しいSDKだから3.0.0だろう」と推測
speechmatics-batch==3.0.0
```

✅ **正しい**:
```bash
# PyPIで確認してから記載
WebFetch: https://pypi.org/project/speechmatics-batch/
# → 最新版: 0.4.4
speechmatics-batch==0.4.4
```

---

### 失敗例 2: 存在しないクラスをimport

❌ **間違い**:
```python
# 「たぶんこういうクラスがあるだろう」と推測
from speechmatics.batch import OperatingPoint
```

✅ **正しい**:
```python
# 公式サンプルコードを確認してからimport
# → OperatingPointは存在しない
from speechmatics.batch import AsyncClient, TranscriptionConfig, FormatType
```

---

### 失敗例 3: パラメータ名を推測

❌ **間違い**:
```python
# 「sensitivityだろう」と推測
speaker_diarization_config={"sensitivity": 0.5}
```

✅ **正しい**:
```python
# 公式ドキュメントで確認
# → 正しいキー名は "speaker_sensitivity"
speaker_diarization_config={"speaker_sensitivity": 0.5}
```

---

### 失敗例 4: 環境変数の設定漏れ

❌ **間違い**:
```yaml
# GitHub Secrets に追加したが、Workflow に追加し忘れ
```

✅ **正しい**:
```bash
# 3箇所セットで設定
1. GitHub Secrets
2. Workflow (env: + echo)
3. docker-compose.prod.yml
```

---

## 📝 導入完了チェックリスト

### 実装前
- [ ] 公式ドキュメント確認済み
- [ ] PyPIでバージョン確認済み
- [ ] 公式サンプルコード確認済み
- [ ] APIキー取得済み

### 実装中
- [ ] requirements.txt に追加（正しいバージョン）
- [ ] プロバイダー実装（公式サンプルコードベース）
- [ ] ローカルテスト成功
- [ ] 構文チェック・エンコーディング確認

### デプロイ前
- [ ] GitHub Secrets 追加済み
- [ ] Workflow 2箇所更新済み
- [ ] docker-compose.prod.yml 更新済み

### デプロイ後
- [ ] デプロイ成功確認
- [ ] コンテナ起動確認
- [ ] 環境変数設定確認
- [ ] 本番環境でテスト成功

---

## 💡 不明点がある場合の対処

### 原則: 推測せず、即座にSTOP

**不明点の例**:
- パッケージの正確な名前がわからない
- バージョン番号がわからない
- パラメータの正しい名前がわからない
- 公式サンプルコードが見つからない

**対処法**:
1. **即座に作業を停止**
2. **WebSearch / WebFetch で確認**
3. **それでも不明な場合は質問**

❌ **禁止行動**:
- 「たぶんこうだろう」と推測で実装
- 「とりあえず試してみる」で進める
- エラーが出ても無視して進める

✅ **正しい行動**:
- 「〇〇が不明です。公式ドキュメントのURLを教えてください」
- 「PyPIで確認します」
- 「公式サンプルコードを読みます」

---

## 🔗 参考リンク

- **CI/CD標準仕様**: [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md)
- **環境変数管理**: [CICD_STANDARD_SPECIFICATION.md#環境変数管理の原則](./CICD_STANDARD_SPECIFICATION.md#-環境変数管理の原則)
- **トラブルシューティング**: [CICD_STANDARD_SPECIFICATION.md#トラブルシューティング](./CICD_STANDARD_SPECIFICATION.md#トラブルシューティング)

---

## 📚 過去の導入事例

### 成功例
- Deepgram ASR（公式ドキュメント確認済み）
- Groq Whisper（公式サンプルコードベース）

### 失敗→修正例
- **Speechmatics Batch API**（2026-01-12）
  - 失敗: バージョン3.0.0指定（存在しない）
  - 失敗: OperatingPointクラス使用（存在しない）
  - 失敗: sensitivityキー使用（正しくはspeaker_sensitivity）
  - 修正: 公式ドキュメント確認後、0.4.4に修正

---

**最終更新**: 2026-01-12
