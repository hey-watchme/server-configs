# 音声AI技術 棚卸し（2026年7月時点）

最終更新: 2026-07-05
Status: Reference
Source of truth: 2026-07-05 時点の外部技術調査スナップショット

## この文書の目的

WatchMe 再始動（2026-07）にあたり、ASR / SER / SED / マルチモーダルLLM の選択肢を棚卸しした記録。
評価基準は **精度最優先・コスト度外視・日本語必須**（プレゼンテーション用モックアップという製品方針のため。方針は [MASTER_PLAN.md](./MASTER_PLAN.md) 参照）。

---

## 1. 結論サマリー

| 領域 | 現行 | 状態 | 推奨 |
|------|------|------|------|
| SER（感情認識） | Hume AI Expression Measurement | 🔴 **2026-06-14 サンセット済み・利用不可** | マルチモーダルLLM（Gemini 3.1 Pro）+ 必要なら emotion2vec+/SenseVoice で置換 |
| SED（音響イベント） | AST（2021年、mAP 0.485） | 🟡 動作するが5年前の世代 | Gemini/Qwen3-Omni の自由記述に置換 or SSLAM(0.502)へ更新 |
| ASR（文字起こし） | Speechmatics Batch | 🟡 動作するが最新比較未実施 | ElevenLabs Scribe v2 / AssemblyAI Universal-3 Pro / Speechmatics Melia-1 の実データA/B |
| LLM（心理分析） | OpenAI gpt-5.4 | 🟢 動作 | 最新フロンティアに随時更新 |

**最重要の変化**: フロンティア・マルチモーダルLLM（特に Gemini 3.1 Pro）が音声直接入力で「文字起こし+話者分離+感情+環境音記述」を一括実行できるようになった。ASR+SED+SER の3パイプライン並列という現行アーキテクチャの前提が崩れており、**「計測レベルは専用ASR、解釈レベルはマルチモーダルLLM」の2系統ハイブリッド**が2026年時点の最適解。

---

## 2. Hume AI の現状（SER 移行が必須の根拠）

- 会社自体は存続・成長中（Series B $50M）。ただし**バッチ分析からリアルタイム会話AI（EVI）へ完全ピボット**
- **Expression Measurement API（WatchMe が使用していた製品）は廃止**:
  - 2026-05-14: Playground 新規ジョブ最終日
  - 2026-06-14: API 利用・結果ダウンロード最終日 → **現在すでに利用不可**
- EVI の表情センシングはリアルタイム会話前提で、録音済み音声のバッチ分析には適合しない
- 出典: https://dev.hume.ai/docs/expression-measurement/faq （最終確認は要ブラウザ）

→ `emotion-analysis/feature-extractor-v3`（Hume 専用実装）は**そのままでは復旧不能**。SER 層の再設計が必須。

---

## 3. マルチモーダルLLM の音声理解（新しい選択肢）

### Gemini 3.1 Pro（現時点の最有力）

- 音声直接入力で、文字起こし・話者分離・感情検出・**非音声音（環境音）の理解**・タイムスタンプ参照・翻訳を単一プロンプトで実行可能
- 入力最大 9.5 時間 / プロンプト。音声は 32トークン/秒
- 弱点: 単語レベルタイムスタンプ不可、話者ラベルのハルシネーション、出力がプロンプト設計に依存
- 出典: https://ai.google.dev/gemini-api/docs/audio

### OpenAI

- GPT-Realtime-2（2026-05）等は**会話エージェント指向**。録音済み長時間音声の一括分析用途には不向き
- 文字起こし特化: gpt-4o-transcribe-diarize（$0.006/分・話者分離込み）、2025-12 版は雑音下ハルシネーション約90%削減を主張

### Anthropic Claude

- **API のネイティブ音声入力は非対応（2026-07 時点）**。分析層には使えない。レポート/ナラティブ生成層では有力

### OSS / Alibaba

- **Qwen3-Omni**（重み公開）+ **Qwen3-Omni-Captioner**: 低ハルシネーションの音声キャプション生成（環境音の自由記述）。自前ホスト可
- **Qwen3.5-Omni**（2026-04、API提供）: 10時間超入力、日本語 WER 3.479、一般音声理解で Gemini 3.1 Pro 超えを主張（自己申告）
- **SenseVoice**（FunAudioLLM）: ASR+SER+音響イベントを1パス同時出力、日本語ネイティブ、OSS

### 評価: 単一LLMで3パイプラインを置き換えられるか

| 要件 | 単一LLM | 専用モデル |
|------|---------|-----------|
| 逐語文字起こし（日本語）・単語TS・構造化話者分離 | △ 幻覚リスク | ◎ |
| 感情・トーンの文脈込み解釈 | ◎ 最強 | △ 固定カテゴリ |
| 環境音の記述 | ◎ 自由記述 | △ 固定527クラス |
| スコアの時系列一貫性（グラフ用途） | △ 出力安定性に課題 | ◎ 連続値 |
| プレゼン品質の物語化 | ◎ 唯一無二 | ✕ |

→ **「洞察」はLLM、「計測の骨格」は専用ASR** に分担するのが現実解。

---

## 4. 専用 ASR の2026年最新状況

| プロバイダ | 最新モデル | 特徴 | 価格目安 |
|-----------|-----------|------|---------|
| **ElevenLabs** | Scribe v2（2026-01） | **音声イベントタグ（笑い声・足音等）標準搭載**、48話者分離、単語TS。本用途との適合が最良 | プラン制 |
| **AssemblyAI** | Universal-3 Pro（2026） | 構造化話者分離の信頼性、99言語、コードスイッチング | ~$0.21-0.27/時 |
| **Speechmatics**（現行） | **Melia-1**（2026-06 preview） | 言語指定不要の多言語モデル。既存連携を活かすなら `model: melia-1` へ移行 | $0.129/時〜 |
| OpenAI | gpt-4o-transcribe-diarize | 雑音下ハルシネーション大幅削減を主張 | $0.36/時 |
| Deepgram | Nova-3（2025-02） | 低価格・低レイテンシ | ~$0.26-0.35/時 |
| OSS | Qwen3-ASR 1.7B（2026-01） | OSS SOTA 主張、日本語対応、TS対応（話者分離は別途） | 自前ホスト |

注: ベンチマーク数値はベンダー自己申告を含む。**日本語・生活雑音という条件では公開ベンチと乖離しうるため、選定は自社録音データでのA/Bテストで行うこと。**

---

## 5. SER / SED の専用モデル最新状況

### SER（Hume 代替の専用モデル路線）

- 商用API: audEERING devAIce（arousal/valence次元）、Empath（日本、1分0.2円。**2025-07 ナレッジワークに吸収合併、提供体制要確認**）、Behavioral Signals。**Hume の48感情のような細粒度を返す商用APIは他に存在しない** → 感情タクソノミーの再設計が前提
- OSS: **emotion2vec+ large**（9感情、多言語頑健、SERのデファクト）、**SenseVoice**（ASR+SER+AED同時、日本語ネイティブ）
- 研究動向: 音声LLMは語彙内容に引きずられ音響的手がかりを取りこぼす傾向（「言葉は前向きだが声は沈んでいる」の検出は専用SERが優位）。EmoNet-Voice で Gemini 2.5 Pro は r=0.416

### SED（AudioSet 527クラス路線の現在地）

- SOTA: **SSLAM（2025、mAP 0.502）** > EAT(0.486) ≒ BAT(0.485) ≒ **AST（現行、0.485、2021年）** > PANNs(0.431)
- 527クラス分類の枠内での改善は逓減局面（+1.7pt）。**劇的な向上はもう「固定クラス分類」では起きない**
- 新路線: GLAP（日本語テキストでゼロショット音分類）、Qwen3-Omni-Captioner / Audio Flamingo 3（自由記述）、Gemini 3 Pro（環境音の検出・記述）

---

## 6. 主要ソース

- Hume sunset: https://dev.hume.ai/docs/expression-measurement/faq
- Gemini audio: https://ai.google.dev/gemini-api/docs/audio / pricing: https://ai.google.dev/gemini-api/docs/pricing
- OpenAI audio models: https://developers.openai.com/blog/updates-audio-models
- Scribe v2: https://elevenlabs.io/blog/introducing-scribe-v2
- AssemblyAI: https://www.assemblyai.com/pricing
- Speechmatics Melia: https://www.speechmatics.com/company/articles-and-news/introducing-melia-multilingual-speech-to-text-model
- Qwen3-Omni: https://github.com/QwenLM/Qwen3-Omni / Qwen3.5-Omni: https://arxiv.org/html/2604.15804v1
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice / emotion2vec: https://huggingface.co/emotion2vec/emotion2vec_plus_large
- AudioSet SOTA: https://www.codesota.com/audio/classification
- AHELM（audio-LM 総合評価、Gemini 2.5 Pro 総合1位）: https://arxiv.org/pdf/2508.21376
