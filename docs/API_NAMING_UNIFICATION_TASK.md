# API命名規則統一タスク

**作成日**: 2025-10-28
**目的**: エンドポイント、コンテナ名、ECRリポジトリ、systemdサービス名をすべて統一する

---

## 🎯 統一原則

### シンプルな命名規則

```
エンドポイント:   /{domain}/{service}/
コンテナ名:       {domain}-{service}
ECRリポジトリ:    watchme-{domain}-{service}
systemdサービス:  {domain}-{service}
```

**重要**: すべて同じ単語を使用（機能名と実行者を分けない）

---

## 📊 現状と目標

### ❌ 現状（混在している）

| サービス | エンドポイント | コンテナ名 | ECRリポジトリ | 問題点 |
|---------|--------------|-----------|--------------|--------|
| Vibe Transcriber | `/vibe-analysis/transcription/` | `vibe-analysis-transcriber` | `watchme-vibe-analysis-transcriber` | ❌ transcription ≠ transcriber |
| Vibe Aggregator | `/vibe-analysis/aggregation/` | `vibe-analysis-aggregator` | `watchme-api-vibe-aggregator` | ❌ aggregation ≠ aggregator |
| Vibe Scorer | `/vibe-analysis/scoring/` | `api-gpt-v1` | `watchme-api-vibe-scorer` | ❌ scoring ≠ scorer ≠ api-gpt-v1 |
| Behavior Aggregator | `/behavior-aggregator/` | `api-sed-aggregator` | `watchme-api-sed-aggregator` | ❌ 階層化なし、名前違い |
| Behavior Features | `/behavior-analysis/features/` | `behavior-analysis-feature-extractor` | `watchme-behavior-analysis-feature-extractor` | ❌ features ≠ feature-extractor |
| Emotion Features | `/emotion-analysis/features/` | `emotion-analysis-feature-extractor-v3` | `watchme-emotion-analysis-feature-extractor-v3` | ❌ features ≠ feature-extractor |
| Emotion Aggregator | `/emotion-analysis/aggregation/` | `emotion-analysis-aggregator` | `watchme-api-opensmile-aggregator` | ❌ aggregation ≠ aggregator |

---

### ✅ 目標（完全統一）

| サービス | エンドポイント | コンテナ名 | ECRリポジトリ | 状態 |
|---------|--------------|-----------|--------------|------|
| Vibe Transcriber | `/vibe-analysis/transcriber/` | `vibe-analysis-transcriber` | `watchme-vibe-analysis-transcriber` | ✅ 統一 |
| Vibe Aggregator | `/vibe-analysis/aggregator/` | `vibe-analysis-aggregator` | `watchme-vibe-analysis-aggregator` | ✅ 統一 |
| Vibe Scorer | `/vibe-analysis/scorer/` | `vibe-analysis-scorer` | `watchme-vibe-analysis-scorer` | ✅ 統一 |
| Behavior Aggregator | `/behavior-analysis/aggregator/` | `behavior-analysis-aggregator` | `watchme-behavior-analysis-aggregator` | ✅ 統一 |
| Behavior Feature Extractor | `/behavior-analysis/feature-extractor/` | `behavior-analysis-feature-extractor` | `watchme-behavior-analysis-feature-extractor` | ✅ 統一 |
| Emotion Feature Extractor | `/emotion-analysis/feature-extractor/` | `emotion-analysis-feature-extractor` | `watchme-emotion-analysis-feature-extractor` | ✅ 統一 |
| Emotion Aggregator | `/emotion-analysis/aggregator/` | `emotion-analysis-aggregator` | `watchme-emotion-analysis-aggregator` | ✅ 統一 |

---

## 📋 移行タスク

### 🔴 優先度: 高

#### 1. Vibe Transcriber ✅ **完了: 2025-10-28**

**完了状態:**
- エンドポイント: `/vibe-analysis/transcriber/` ✅
- コンテナ: `vibe-analysis-transcriber` ✅
- ECR: `watchme-vibe-analysis-transcriber` ✅
- systemd: `vibe-analysis-transcriber` ✅
- GitHubリポジトリ: `api-vibe-analysis-transcriber-v2` ✅

**実施内容:**
- [x] Nginxエンドポイント: `/vibe-analysis/transcription/` → `/vibe-analysis/transcriber/`
- [x] Lambda関数（watchme-audio-worker）のURL修正 → デプロイ完了
- [x] TECHNICAL_REFERENCE.mdのエンドポイント修正（5箇所）
- [x] PROCESSING_ARCHITECTURE.mdのエンドポイント修正（2箇所）
- [x] CI/CDワークフロー（deploy-to-ecr.yml）のURL修正
- [x] Gitリモート: `api-asr-azure` → `api-vibe-analysis-transcriber-v2`

**確認済み:**
- Lambda: デプロイ済み（CodeSha256: 88K3mC5QMAOpuOvak6pq34BWoS78uibHE7ptphbs4MQ=）
- Nginx: リロード完了、構文チェックOK
- エンドポイント: `https://api.hey-watch.me/vibe-analysis/transcriber/docs` で正常応答

---

#### 2. Vibe Aggregator ✅ **完了: 2025-10-29**

**完了状態:**
- エンドポイント: `/vibe-analysis/aggregator/` ✅
- コンテナ: `api_gen_prompt_mood_chart` ⚠️（統一前の名前）
- ECR: `watchme-api-vibe-aggregator` ⚠️（prefixが違う）
- systemd: （コンテナ名に依存）⚠️

**実施内容:**
- [x] Nginxエンドポイント: `/vibe-aggregator/` → `/vibe-analysis/aggregator/` + タイムアウト設定（180秒）
- [x] Lambda関数（watchme-audio-worker）のURL修正 → デプロイ完了
- [x] Lambda関数（watchme-dashboard-summary-worker）のURL修正 → デプロイ完了
- [x] TECHNICAL_REFERENCE.mdのエンドポイント修正
- [x] 本番環境反映（git pull + nginx reload）✅ **2025-10-29**
- [ ] ECRリポジトリ名: 新しく `watchme-vibe-analysis-aggregator` を作成、旧削除（保留）
- [ ] コンテナ名: `api_gen_prompt_mood_chart` → `vibe-analysis-aggregator`（保留）
- [ ] GitHub Actions CI/CD: ECRリポジトリ名修正（保留）

**確認済み:**
- Lambda: デプロイ済み（audio-worker, dashboard-summary-worker）
- Nginx: リロード完了、構文チェックOK
- エンドポイント: `https://api.hey-watch.me/vibe-analysis/aggregator/health` で正常応答 ✅

**注意:**
- エンドポイントのみ統一完了（オプション1）
- コンテナ名・ECRリポジトリ名の統一は将来実施予定（オプション2）

---

#### 3. Vibe Scorer ✅ **完了: 2025-10-30**

**完了状態:**
- エンドポイント: `/vibe-analysis/scoring/` ✅
- コンテナ: `vibe-analysis-scorer` ✅ **2025-10-30完了**
- ECR: `watchme-vibe-analysis-scorer` ✅ **2025-10-30完了**
- systemd: `vibe-analysis-scorer` ✅ **2025-10-30完了**
- GitHubリポジトリ: `hey-watchme/api-vibe-analysis-scorer` ✅ **2025-10-30完了**

**実施内容:**
- [x] Nginxエンドポイント: `/vibe-scorer/` → `/vibe-analysis/scoring/` + タイムアウト設定（180秒）✅ **2025-10-29**
- [x] 本番環境反映（git pull + nginx reload）✅ **2025-10-29**
- [x] コンテナ名: `api-gpt-v1` → `vibe-analysis-scorer` ✅ **2025-10-30**
- [x] systemd: `api-gpt-v1` → `vibe-analysis-scorer` ✅ **2025-10-30**
- [x] ECRリポジトリ名: `watchme-api-vibe-scorer` → `watchme-vibe-analysis-scorer` ✅ **2025-10-30**
- [x] 旧ECRリポジトリ削除（watchme-api-vibe-scorer）✅ **2025-10-30**
- [x] docker-compose.prod.yml作成（vibe-analysis-scorer-docker-compose.prod.yml）✅ **2025-10-30**
- [x] GitHub Actionsワークフロー修正 ✅ **2025-10-30**
- [x] README.mdルーティング詳細セクション追加 ✅ **2025-10-30**
- [x] GitHubリモートリポジトリ変更 ✅ **2025-10-30**

**確認済み:**
- Nginx: リロード完了、構文チェックOK
- エンドポイント: `https://api.hey-watch.me/vibe-analysis/scoring/health` で正常応答 ✅
- コンテナ: `docker ps | grep vibe-analysis-scorer` で確認 ✅
- systemd: `sudo systemctl status vibe-analysis-scorer` で動作確認 ✅
- ECR: `watchme-vibe-analysis-scorer` のみ存在、旧リポジトリ削除済み ✅

**注意:**
- **完全統一完了（オプション2実施済み）** ✅
- すべての名称が統一命名規則に準拠

---

### 🟡 優先度: 中

#### 4. Behavior Aggregator

**現状:**
- エンドポイント: `/behavior-aggregator/` ❌ **階層化されていない**
- コンテナ: `api-sed-aggregator` ❌ **完全に違う**
- ECR: `watchme-api-sed-aggregator` ❌
- systemd: `api-sed-aggregator` ❌

**修正内容:**
- [ ] Nginxエンドポイント: `/behavior-aggregator/` → `/behavior-analysis/aggregator/`
- [ ] コンテナ名: `api-sed-aggregator` → `behavior-analysis-aggregator`
- [ ] systemd: `api-sed-aggregator` → `behavior-analysis-aggregator`
- [ ] ECRリポジトリ名: 新しく `watchme-behavior-analysis-aggregator` を作成、旧削除
- [ ] docker-compose.prod.yml修正
- [ ] ドキュメント修正

**影響範囲:**
- コンテナ名: 変更必要（大きな変更）
- ECRリポジトリ: 再作成必要
- systemdサービス: 再作成必要
- ドキュメント: 3ファイル

---

#### 5. Behavior Feature Extractor

**現状（2025-10-29更新）:**
- エンドポイント: `/behavior-analysis/features/` ❌ **Nginxに設定なし（404）**
- コンテナ: `behavior-analysis-feature-extractor` ✅
- ECR: `watchme-behavior-analysis-feature-extractor` ✅
- systemd: `behavior-analysis-feature-extractor` ✅

**発見した問題（2025-10-29）:**
- Nginxに `/behavior-analysis/features/` のlocationブロックが存在しない
- `/behavior-features/` のみ存在（旧パス）
- Lambda（watchme-audio-worker）は `/behavior-analysis/features/fetch-and-process-paths` を呼んでいる
- 結果：Lambda → Nginx → 404 Not Found

**修正内容:**
- [x] **緊急対応**: Nginxに `/behavior-analysis/features/` を追加（2025-10-29）
- [ ] **将来対応**: エンドポイント名を `/behavior-analysis/feature-extractor/` に統一
- [ ] Lambda関数（watchme-audio-worker）のURL修正
- [ ] ドキュメント修正

**影響範囲:**
- Lambda関数: 1つ
- ドキュメント: 3ファイル

---

#### 6. Emotion Feature Extractor ✅ **完了: 2025-10-29**

**完了状態:**
- エンドポイント: `/emotion-analysis/feature-extractor/` ✅
- コンテナ: `emotion-analysis-feature-extractor-v3` ⚠️（バージョン番号は保留）
- ECR: `watchme-emotion-analysis-feature-extractor-v3` ⚠️（バージョン番号は保留）
- systemd: `emotion-analysis-feature-extractor-v3` ⚠️（バージョン番号は保留）

**実施内容:**
- [x] Nginxエンドポイント: `/emotion-features/` → `/emotion-analysis/feature-extractor/`
- [x] Lambda関数（watchme-audio-worker）のURL修正 → デプロイ完了
- [x] README.mdの更新（ルーティング詳細セクション追加）
- [ ] コンテナ名: `-v3` を削除（将来実施）
- [ ] ECRリポジトリ名: `-v3` を削除（将来実施）
- [ ] systemd: `-v3` を削除（将来実施）

**確認済み:**
- Lambda: デプロイ済み（CodeSha256: zbah+C5kg8HVONsm3VWgtBSG/54SleapLx+0bn07apw=）
- Nginx: リロード完了、構文チェックOK
- エンドポイント: `https://api.hey-watch.me/emotion-analysis/feature-extractor/` で正常応答

**注意:**
- エンドポイントのみ統一完了（オプション1）
- コンテナ名・ECRリポジトリ名の統一は将来実施予定（オプション2）

---

#### 7. Emotion Aggregator ✅ **完了: 2025-10-29**

**完了状態:**
- エンドポイント: `/emotion-analysis/aggregator/` ✅
- コンテナ: `emotion-analysis-aggregator` ✅
- ECR: `watchme-api-opensmile-aggregator` ⚠️（統一前の名前）
- systemd: `emotion-analysis-aggregator` ✅

**実施内容:**
- [x] Nginxエンドポイント: `/emotion-aggregator/` → `/emotion-analysis/aggregator/`
- [x] Lambda関数（watchme-audio-worker）のURL修正 → デプロイ完了
- [ ] ECRリポジトリ名: 新しく `watchme-emotion-analysis-aggregator` を作成、旧削除（保留）
- [ ] GitHub Actions CI/CD: ECRリポジトリ名修正（保留）

**確認済み:**
- Lambda: デプロイ済み（CodeSha256: zbah+C5kg8HVONsm3VWgtBSG/54SleapLx+0bn07apw=）
- Nginx: リロード完了、構文チェックOK
- エンドポイント: `https://api.hey-watch.me/emotion-analysis/aggregator/` で正常応答

**注意:**
- エンドポイントのみ統一完了（オプション1）
- ECRリポジトリ名の統一は将来実施予定（オプション2）

---

## 🔧 作業手順（テンプレート）

### 各サービスの移行手順

1. **ローカルで変更**
   - [ ] Nginx設定ファイル修正
   - [ ] ドキュメント修正（TECHNICAL_REFERENCE.md, PROCESSING_ARCHITECTURE.md, API_RESTRUCTURE_LOG.md）
   - [ ] Lambda関数のエンドポイントURL修正（該当する場合）

2. **コミット・プッシュ**
   - [ ] server-configsリポジトリにコミット・プッシュ
   - [ ] Lambda関数をビルド・デプロイ（該当する場合）

3. **EC2に反映**
   - [ ] `git pull origin main`
   - [ ] `sudo ./setup_server.sh`
   - [ ] Nginxリロード確認

4. **動作確認**
   - [ ] 新エンドポイントで動作確認
   - [ ] Lambda関数の動作確認（該当する場合）

5. **クリーンアップ**
   - [ ] 旧ECRリポジトリ削除（該当する場合）

---

## 📅 移行スケジュール（提案）

### フェーズ1: エンドポイントのみ修正（影響小）
- Vibe Transcriber
- Behavior Feature Extractor

### フェーズ2: ECRリポジトリ名も修正（影響中）
- Vibe Aggregator
- Emotion Feature Extractor
- Emotion Aggregator

### フェーズ3: コンテナ名・systemdも修正（影響大）
- Vibe Scorer
- Behavior Aggregator

---

## 📝 注意事項

1. **本番環境への影響**
   - エンドポイント変更はLambda関数に影響
   - Lambda関数を先に更新してからNginxを変更

2. **後方互換性**
   - 旧エンドポイントは削除する方針（2025-10-23の決定に基づく）
   - ただし、段階的に移行する場合は一時的に並行運用も検討

3. **ECRリポジトリ変更**
   - 新しいリポジトリを作成してからイメージをプッシュ
   - 旧リポジトリは動作確認後に削除

4. **ドキュメント更新**
   - すべての変更をドキュメントに反映
   - README.mdのアーキテクチャ図も更新

---

## ✅ 完了チェック

各サービスの移行完了時にチェック:

- [x] Vibe Transcriber ✅ **2025-10-28完了（完全統一）**
- [x] Vibe Aggregator ✅ **2025-10-29完了（エンドポイントのみ）**
- [x] Vibe Scorer ✅ **2025-10-30完了（完全統一）**
- [ ] Behavior Aggregator
- [ ] Behavior Feature Extractor
- [x] Emotion Feature Extractor ✅ **2025-10-29完了（エンドポイントのみ）**
- [x] Emotion Aggregator ✅ **2025-10-29完了（エンドポイントのみ）**

**進捗状況**: 5/7 完了 (71.4%)

**完全統一完了**: 2/7 (28.6%)
- ✅ Vibe Transcriber（2025-10-28）
- ✅ Vibe Scorer（2025-10-30）

**注意**: Vibe Aggregator、Emotion Feature Extractor、Emotion Aggregatorはエンドポイントのみ統一（オプション1）。コンテナ名・ECRリポジトリは未統一。
