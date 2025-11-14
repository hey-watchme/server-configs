# 実装計画：エラーハンドリングとユーザー体験改善

**作成日**: 2025年10月20日
**最終更新**: 2025年10月21日 09:05

---

## 📋 実装状況サマリー

### ✅ 完了したタスク（2025年10月21日）

1. **Vibe Aggregatorに失敗処理エンドポイント追加**
   - エンドポイント: `POST /create-failed-record`
   - 処理内容: Azure失敗時にdashboardテーブルに失敗レコードを作成
   - vibe_score: `0`（未処理`null`と区別するため）
   - status: `'completed'`（累積分析をトリガーするため）

2. **Lambda関数（watchme-audio-worker）修正**
   - Azure失敗時に`/create-failed-record`を自動呼び出し
   - 失敗レコード作成後も累積分析をトリガー

3. **累積分析API修正**
   - `status='completed'`の全データを取得（vibe_scoreの有無に関係なく）
   - 失敗レコードも累積分析に含める

4. **Azure APIレスポンスのファイル単位判定実装** ✅ **完了（2025年10月21日 09:05）**
   - `processed_files`/`error_files`リストから該当ファイルの成功/失敗を判定
   - HTTP 200でもファイル単位でエラーを検出可能に
   - クォーター超過時も正確に失敗を検出
   - **実装場所**: `lambda_function.py` Line 95-164

5. **デプロイ完了**
   - Vibe Aggregator: GitHubにpush → CI/CD自動デプロイ
   - Lambda関数: AWSにデプロイ完了（2025年10月21日 09:05）

---

## 🔧 残タスク

### **Task 1: ~~Azure APIレスポンスからファイル単位で成功/失敗を判定~~** ✅ **完了**

~~**優先度**: 高~~

**実装完了**:
```python
# Lambda関数内の判定ロジック（lambda_function.py Line 95-164）
processed_files = response_data.get('processed_files', [])
error_files = response_data.get('error_files', [])

if file_path in processed_files:
    azure_success = True  # ✅ 成功
elif file_path in error_files:
    azure_success = False  # ❌ 失敗（クォーター超過など）
else:
    # summary.errorsで判定
    errors_count = response_data.get('summary', {}).get('errors', 0)
    azure_success = (errors_count == 0)
```

**デプロイ状況**: ✅ 完了（2025年10月21日 09:05）

---

### **Task 2: プッシュ通知の動作確認**

**優先度**: 中

**状況**:
- SNS Platform Application（サンドボックス）を有効化済み
- 次の音声アップロードで通知が届くか確認が必要

---

### **Task 3: フロントエンド（iOSアプリ）でエラー表示改善**

**優先度**: 中

**現在の状況**:
- dashboardテーブルの`summary`に失敗メッセージが入っている
- アプリ側で特別な表示をしていない可能性

**改善案**:
- `vibe_score=0`かつ`summary`に「失敗」が含まれる場合に特別な表示
- または専用のエラー表示UI

---

### **Task 4: 手動再処理の仕組み（低優先度）**

**優先度**: 低

**方法**:
- Claude Codeなどのエージェントに直接操作してもらう
- 大量データの扱いは今後の課題

---

## 🎯 データフロー（現在の実装）

### **成功時**
```
Lambda → Azure API → 成功
→ Vibe Aggregator → Vibe Scorer
→ dashboardテーブル（vibe_score=数値, status='completed'）
→ 累積分析 → プッシュ通知
```

### **失敗時**
```
Lambda → Azure API → 失敗
→ /create-failed-record
→ dashboardテーブル（vibe_score=0, status='completed', summary="分析失敗..."）
→ 累積分析 → プッシュ通知
```

---

## 📊 データの3つの状態

| 状態 | vibe_score | 意味 |
|------|-----------|------|
| **未処理** | `null` | まだその時間帯に到達していない |
| **失敗** | `0` | 処理済みだが分析失敗 |
| **正常** | 数値（-100〜100） | 正常に分析完了 |

---

## 📝 重要なポイント

1. **HTTP 200とerrors:1の関係**
   - Azure APIはバッチ処理API
   - API自体が成功してもファイル単位で失敗する場合がある
   - `processed_files`と`error_files`でファイル単位の成功/失敗を判定

2. **失敗時もフローを止めない設計**
   - 失敗レコード作成後も累積分析を実行
   - 条件分岐を最小化し、シンプルなフロー維持

3. **再処理の簡便さ**
   - audio_filesテーブルの`transcriptions_status`を参照
   - 再処理時は単にupsertで上書き

---

## 🔗 関連ファイル

- Lambda関数: `/Users/kaya.matsumoto/projects/watchme/server-configs/lambda-functions/watchme-audio-worker/lambda_function.py`
- Vibe Aggregator: `/Users/kaya.matsumoto/api_gen-prompt_mood-chart_v1/main.py`
- アーキテクチャ: `/Users/kaya.matsumoto/projects/watchme/server-configs/PROCESSING_ARCHITECTURE.md`

---

*次のセッションではTask 1（Azure APIレスポンスのファイル単位判定）の実装を優先*
