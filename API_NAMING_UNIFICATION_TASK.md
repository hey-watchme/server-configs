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
| Behavior Feature Extractor | `/behavior-analysis/feature-extractor/` | `behavior-analysis-feature-extractor` | `watchme-behavior-analysis-feature-extractor` | ✅ 統一 |
| Emotion Feature Extractor | `/emotion-analysis/feature-extractor/` | `emotion-analysis-feature-extractor` | `watchme-emotion-analysis-feature-extractor` | ✅ 統一 |
| Emotion Aggregator | `/emotion-analysis/aggregator/` | `emotion-analysis-aggregator` | `watchme-emotion-analysis-aggregator` | ✅ 統一 |

---

## 📋 移行タスク

### 🔴 優先度: 高

#### 1. Vibe Transcriber

**現状:**
- エンドポイント: `/vibe-analysis/transcription/` ❌
- コンテナ: `vibe-analysis-transcriber` ✅
- ECR: `watchme-vibe-analysis-transcriber` ✅
- systemd: `vibe-analysis-transcriber` ✅

**修正内容:**
- [ ] Nginxエンドポイント: `/vibe-analysis/transcription/` → `/vibe-analysis/transcriber/`
- [ ] Lambda関数（watchme-audio-worker）のURL修正
- [ ] TECHNICAL_REFERENCE.mdのエンドポイント修正
- [ ] PROCESSING_ARCHITECTURE.mdのエンドポイント修正
- [ ] API_RESTRUCTURE_LOG.mdのエンドポイント修正

**影響範囲:**
- Lambda関数: watchme-audio-worker
- ドキュメント: 3ファイル

---

#### 2. Vibe Aggregator

**現状:**
- エンドポイント: `/vibe-analysis/aggregation/` ❌
- コンテナ: `vibe-analysis-aggregator` ✅
- ECR: `watchme-api-vibe-aggregator` ⚠️（prefixが違う）
- systemd: `vibe-analysis-aggregator` ✅

**修正内容:**
- [ ] Nginxエンドポイント: `/vibe-analysis/aggregation/` → `/vibe-analysis/aggregator/`
- [ ] Lambda関数（watchme-audio-worker, watchme-dashboard-summary-worker）のURL修正
- [ ] ECRリポジトリ名: 新しく `watchme-vibe-analysis-aggregator` を作成、旧削除
- [ ] GitHub Actions CI/CD: ECRリポジトリ名修正
- [ ] ドキュメント修正

**影響範囲:**
- Lambda関数: 2つ
- ECRリポジトリ: 再作成必要
- ドキュメント: 3ファイル

---

#### 3. Vibe Scorer

**現状:**
- エンドポイント: `/vibe-analysis/scoring/` ❌
- コンテナ: `api-gpt-v1` ❌ **完全に違う**
- ECR: `watchme-api-vibe-scorer` ⚠️
- systemd: `api-gpt-v1` ❌

**修正内容:**
- [ ] Nginxエンドポイント: `/vibe-analysis/scoring/` → `/vibe-analysis/scorer/`
- [ ] コンテナ名: `api-gpt-v1` → `vibe-analysis-scorer`
- [ ] systemd: `api-gpt-v1` → `vibe-analysis-scorer`
- [ ] ECRリポジトリ名: `watchme-api-vibe-scorer` → `watchme-vibe-analysis-scorer`
- [ ] Lambda関数（watchme-audio-worker, watchme-dashboard-analysis-worker）のURL修正
- [ ] docker-compose.prod.yml修正
- [ ] ドキュメント修正

**影響範囲:**
- Lambda関数: 2つ
- コンテナ名: 変更必要（大きな変更）
- ECRリポジトリ: 再作成必要
- systemdサービス: 再作成必要
- ドキュメント: 3ファイル

---

### 🟡 優先度: 中

#### 4. Behavior Feature Extractor

**現状:**
- エンドポイント: `/behavior-analysis/features/` ❌
- コンテナ: `behavior-analysis-feature-extractor` ✅
- ECR: `watchme-behavior-analysis-feature-extractor` ✅
- systemd: `behavior-analysis-feature-extractor` ✅

**修正内容:**
- [ ] Nginxエンドポイント: `/behavior-analysis/features/` → `/behavior-analysis/feature-extractor/`
- [ ] Lambda関数（watchme-audio-worker）のURL修正
- [ ] ドキュメント修正

**影響範囲:**
- Lambda関数: 1つ
- ドキュメント: 3ファイル

---

#### 5. Emotion Feature Extractor

**現状:**
- エンドポイント: `/emotion-analysis/features/` ❌
- コンテナ: `emotion-analysis-feature-extractor-v3` ⚠️（バージョン番号）
- ECR: `watchme-emotion-analysis-feature-extractor-v3` ⚠️
- systemd: `emotion-analysis-feature-extractor-v3` ⚠️

**修正内容:**
- [ ] Nginxエンドポイント: `/emotion-analysis/features/` → `/emotion-analysis/feature-extractor/`
- [ ] コンテナ名: `-v3` を削除検討（バージョン管理はECRタグで）
- [ ] ECRリポジトリ名: `-v3` を削除検討
- [ ] systemd: `-v3` を削除検討
- [ ] Lambda関数（watchme-audio-worker）のURL修正
- [ ] ドキュメント修正

**影響範囲:**
- Lambda関数: 1つ
- バージョン番号削除: 要検討
- ドキュメント: 3ファイル

---

#### 6. Emotion Aggregator

**現状:**
- エンドポイント: `/emotion-analysis/aggregation/` ❌
- コンテナ: `emotion-analysis-aggregator` ✅
- ECR: `watchme-api-opensmile-aggregator` ❌ **完全に違う**
- systemd: `emotion-analysis-aggregator` ✅

**修正内容:**
- [ ] Nginxエンドポイント: `/emotion-analysis/aggregation/` → `/emotion-analysis/aggregator/`
- [ ] ECRリポジトリ名: 新しく `watchme-emotion-analysis-aggregator` を作成、旧削除
- [ ] GitHub Actions CI/CD: ECRリポジトリ名修正
- [ ] Lambda関数（watchme-audio-worker）のURL修正（Emotion Features成功時に自動起動）
- [ ] ドキュメント修正

**影響範囲:**
- Lambda関数: 1つ
- ECRリポジトリ: 再作成必要
- ドキュメント: 3ファイル

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

- [ ] Vibe Transcriber
- [ ] Vibe Aggregator
- [ ] Vibe Scorer
- [ ] Behavior Feature Extractor
- [ ] Emotion Feature Extractor
- [ ] Emotion Aggregator

**すべて完了**: ❌ 未着手
