# ディープリサーチ: 音声バイオマーカー / DI 実装調査（2026-07）

最終更新: 2026-07-06
Status: Reference
Source of truth: ダイバージェンスインデックス（DI）と音声分析パイプラインの技術選定の根拠

> このファイルは、外部ディープリサーチ（2026-07-06 実施、一次文献・公式資料ベース）の結果を保存したものです。
> プロダクトの北極星（ビジョン）は [VISION.md](./VISION.md)、フェーズ計画は [MASTER_PLAN.md](./MASTER_PLAN.md) を参照。
> 数値・出典は調査時点のもの。モデル・価格・規制は変化が速いため、引用時は発表時期を確認すること。

---

## 0. 調査の位置づけ

「声を生体信号として読み、"何を話したか"ではなく"どう話したか"（韻律・音響・タイミング等の非言語特徴）から、
認知・感情・性格・健康サインを推定し、"診断ではなく自己理解/セルフケアのきっかけ"を返す」プロダクトの実装判断メモ。

**中心的結論**: DI は「病名推定器」ではなく「**個人内の変化検知＋多軸ナラティブ生成器**」として設計するのが最も妥当。

---

## 1. エグゼクティブサマリー（10点）

1. **最強構成は単一モデルではなくアンサンブル**。①ASR/話者分離は商用API複数＋pyannote系の話者層、②音声LLMは Gemini系・OpenAI Realtime・Qwen3-Omni の併用、③DIは LLM出力ではなく固定バージョンの専用スコアリングモデルで供給。
2. **声から読めるものはあるが、病名の特異的診断には弱い**。うつは臨床サンプルで AUC 0.93 の報告がある一方、モバイル一般成人では PHQ-9/GAD-7 分類 AUC はおおむね 0.68〜0.78。
3. **日本語で最も実用性が見えている健康領域は MCI/認知機能低下**。日本の地域在住高齢者約1,500名で、1分程度の自由会話＋年齢・性別・教育歴で認知機能障害を AUC 0.89 まで改善（音声のみでも 0.81）。
4. **「感度は高いが特異性は低い」は 2026 年時点でも妥当**。声はうつ・睡眠不足・風邪・疲労・飲酒・部屋音響・マイク距離で変わる。DIは「うつです」ではなく「いつものあなたから、声のエネルギー・テンポ・表出性・応答遅延がどの方向にずれたか」を返すべき。
5. **マルチモーダル音声LLMは"解釈層"には強いが"縦断スコア層"には不向き**。出力は確率的で、音声に根拠のない感情・状況を幻覚しうる（EmotionHallucer / HalluAudio でベンチマーク化）。
6. **DIの中核は personal baseline / idiographic modeling**。個人レベル・マルチモーダルモデルが集団モデルを上回る傾向（AUC 0.70〜0.88 で1〜4週先の悪化予測の例）。ただし研究の75%が高バイアスリスク。
7. **ベースライン確立の目安**: モック=3〜5録音、実運用=最低14日 or 20〜30録音、研究品質=28日以上。日内変動・録音環境・体調の統制が重要。
8. **日本語ASRの最大ボトルネックは逐語精度より話者分離**。応答潜時・割り込み・沈黙・フィラー・言い直しは話者ラベルと時刻が崩れると全指標が壊れる。評価優先順位は ①DER/JER/SA-WER ②雑音耐性 ③WER/CER。
9. **音声は個人情報・生体情報・場合により機微情報**。日本APPIで、特定個人を識別できる音声録音は個人情報、声の特徴は個人識別符号になりうる。健康・精神状態推定は要配慮個人情報に近い実務運用が必要。
10. **プロダクト表現は"診断・予測・リスク判定"ではなく"変化の気づき・自己理解・相談のきっかけ"に固定**。FDA General Wellness / 日本 PMD Act の医療機器境界を越えないため。

---

## 2. テーマ別詳細

### A. 音声バイオマーカー（何が声から読めるか）

声は精神状態・認知負荷・神経運動・睡眠/疲労・呼吸状態・急性摂動を反映する。ただし多くは横断・小規模・実験条件依存・言語/デバイス交絡を抱え、診断より「変化検知」に強い。

| 領域 | 代表エビデンス | 成熟度 | DIへの示唆 |
|------|----------------|--------|-----------|
| うつ・不安・疲労 | モバイル音声865名で PHQ-9 AUC 0.76 / BDI 0.78 / GAD-7 0.77 / 不眠 0.73 / 疲労 0.68。臨床MDDでは音響10特徴SVMで AUC 0.93 | 中 | 「低エネルギー」「単調化」「遅延」「表出低下」は有用。うつ断定は不可 |
| 自殺リスク | Web録音ケースコントロールで AUC 0.74、12か月以内死亡サブセットで 0.85 | 研究段階 | 消費者アプリでリスクスコア表示は避ける。危機表現検出時は安全導線へ |
| 双極性・再発 | デジタルフェノタイピング再発予測レビュー: 52研究・4,814名、AUC 0.70〜0.88（多くは音声単独でない） | 研究段階 | 睡眠・活動・音声テンポの多モーダル変化検知が妥当 |
| 認知機能低下/MCI/認知症 | XAIレビュー13研究で AUC 0.76〜0.94（ポーズ・話速・語彙多様性・代名詞が重要）。**日本で1,461名、音声＋年齢・性別・教育歴 AUC 0.89** | 中〜高 | 日本語で最も事業化しやすいが、医療機器境界に注意 |
| パーキンソン病 | 音声・言語障害が運動症状に先行しうる（2025レビュー、予備的） | 中 | motor/voice quality 軸として震え・発声安定性・構音テンポ |
| 呼吸器・感染症 | Colive Voice 1,908名で呼吸QOL推定、臨床＋音声で AUROC 0.77 | 中 | 咳・息切れ・嗄声は"体調負荷"軸に留める。感染症判定は不可 |
| 睡眠不足・疲労 | 睡眠制限研究で個人レベル検出可能、韻律と声質の2系統、個人差大 | 中 | 個人ベースライン型DIと相性が良い |
| 飲酒・薬物 | 636録音、BAC 0.15条件で Gradient Boosting F1 0.78 | 研究段階 | 安全用途以外は扱いに注意。薬物推定は避ける |
| 疼痛 | TAME Pain データセット。高/低疼痛分類 accuracy 0.71 / F1 0.73 の例 | 研究段階 | "声に負荷が出ている可能性"程度に留める |
| 性格 Big Five | 2,045名自由発話で自己申告と相関 r=0.26〜0.39（補正後 0.39〜0.60、音響＋言語）。非言語のみでは弱い | 低〜中 | 性格断定でなく「話し方傾向」「表現スタイル」に限定 |

**A の実装判断**: DI は疾患名ラベルでなく機能軸に変換する。
- affective expression（声の明るさ・抑揚・エネルギー・感情表出）
- cognitive tempo（話速・ポーズ・応答潜時・言い淀み）
- motor/voice quality（発声安定性・jitter/shimmer・HNR・構音）
- physiological load（咳・息切れ・嗄声・疲労様声質）
- social interaction（相づち・割り込み・ターンテイキング）

### B. 韻律・音響特徴と音声表現学習（DIの数値供給層）

数値供給層は「手工特徴＋SSL埋め込み＋タスク特化SER/イベントモデル」の三層が最も堅い。縦断安定性は必ず自社検証が必要。

| 層 | 推奨 | 強み | 弱み |
|----|------|------|------|
| 手工特徴 | openSMILE eGeMAPS v02（88特徴）/ ComParE 2016（6,373特徴）/ Praat / DisVoice | 解釈しやすい | 録音環境・マイク・話者差に弱い |
| SSL音声表現 | WavLM / wav2vec2 / HuBERT / Whisper encoder | パラ言語・認知・健康分類に強い | 埋め込み解釈が難しい、デバイス交絡を拾う |
| 感情基盤 | emotion2vec / emotion2vec+（ACL 2024、10言語、+large は約300M/42,526時間） | valence/arousal/表出性 | ライセンス商用確認が必要 |
| 多言語ASR/SER/イベント | SenseVoice Small/Large（40万時間超、50+言語、日中英韓） | 咳・笑い・泣き等イベント | SERベンチは中英中心、ライセンス確認要 |
| 音楽/環境音 | BEATs / MERT（MERT は Apache-2.0、音楽寄り） | 背景音・環境理解 | 音声状態推定の主軸ではない |

**B の実装判断（DIスコアの固定パイプライン）**:
1. QC特徴: SNR、clipping、RMS/LUFS、残響proxy、背景音、端末ID、マイク距離proxy
2. 韻律/音響: eGeMAPS v02 88特徴、F0、energy、speech rate、pause ratio、response latency、jitter/shimmer/HNR
3. SSL埋め込み: emotion2vec+、WavLM/wav2vec2/Whisper encoder を**固定バージョン**で抽出
4. 低次元因子化: PCA/PLS/autoencoder で affect・tempo・motor・load 軸へ写像
5. 個人内標準化: 文脈補正後、robust z-score、Mahalanobis距離、Wasserstein/JS距離

### C. マルチモーダル音声LLM（②解釈層）

「この発話がどんな声・感情・環境・会話状況に聞こえるか」を構造化説明する層として有用。出力の揺れ・幻覚・プロンプト依存があり、**DIの数値スコア源にしてはいけない**。

| モデル/系統 | 2026時点の位置づけ | 強み | 注意点 |
|-------------|--------------------|------|--------|
| Gemini（Native Audio 系） | 公式docsで話者分離・emotion detection・timestamp segment・JSON構造化例を提示 | 構造化出力、低遅延 | Previewは変動、DIスコアには不向き |
| OpenAI GPT-Realtime-2 / Realtime-Whisper | 2026 公表。聞く・推論・翻訳・転写を統合 | 推論・対話品質、ニュアンス保持 | 音声入力コスト高（gpt-realtime-2 音声入力 $32/1M tok、出力 $64/1M tok） |
| Qwen3-Omni | 30B-A3B 等、低幻覚 captioner、234ms first-packet、Apache-2.0 | OSS/自ホスト、研究再現性 | GPU負荷、日本語実音声は検証要 |
| Qwen2.5-Omni | 音声・画像・動画・テキスト＋音声生成 | OSS対抗、音声理解ベンチ豊富 | 7B級でも推論資源が必要 |
| Phi-4-multimodal | 5.6B、128K context、日本語含む | 軽量、自ホスト候補 | Gemini/GPT級の音声QAには差 |

**自由記述 vs 固定タクソノミー**: 二択でなく**両層**。固定タクソノミーは縦断比較・検証・閾値に、自由記述は人に伝わる言語化に使う。

**LLMスコアがDIに不向きな理由**: LLM出力は確率的（temperature=0でも完全決定的でない）で、感情・音響根拠のない幻覚が起きる。縦断の一貫スケールを供給できない。

### D. ASR＋話者分離＋単語タイムスタンプ（①計測の骨格）

日本語の認知・会話テンポ指標では逐語WERより話者分離と時刻精度が重要。単一ASRに賭けず、商用2〜3社＋pyannote＋OSS でベンチを作る。

| 候補 | 日本語 | 話者分離/時刻 | 価格（調査時点） | 推奨用途 |
|------|--------|---------------|------------------|----------|
| ElevenLabs Scribe v2 | 90+言語、日中対応 | entity timestamps、keyterm prompting | $0.22/hr（Realtime $0.39/hr） | 第1候補・基準 |
| Deepgram Nova-3 Multilingual | 45+言語、日中含む | wordごと speaker、全言語/streaming diarization | $0.0058/min streaming、$0.0092/min pre-recorded | 雑音・crosstalk・far-field対抗 |
| Speechmatics Ursa 2 | 50+言語 | channel_and_speaker diarization、latency <1s | SaaS/on-prem、無料枠あり | 企業/規制・オンプレ候補 |
| AssemblyAI Universal | Universal-2 で99言語、3.5 Pro は18言語 | diarization add-on | 3.5 Pro $0.21/hr、Universal-2 $0.15/hr、diarization $0.02/hr | 対抗（日本語が3.5 Pro対象か要確認） |
| Gladia | 多言語 | word-level、mono/stereo/multi-channel diarization | PAYG/サブスク | 開発速度重視 |
| NVIDIA Parakeet TDT-CTC 0.6B JA | 日本語専用（ReazonSpeech v2.0 35k時間、JSUT CER 6.4） | 文字列出力中心 | OSS/自ホスト | 日本語ASRバックアップ |
| WhisperX | 日本語可 | VAD＋forced alignment＋diarization、word-level | BSD-2 | OSS基準線 |
| pyannoteAI Precision-2 / Community-1 | 言語非依存 | Precision-2 は Community-1 比28%高精度、voiceprint/confidence あり | Precision-2 €0.096〜0.112/hr、Community-1 €0.035/hr、自ホスト可 | **話者分離最優先なら必ず評価** |

**D の評価プロトコル**: 日本語30〜50時間の自社評価セット（静音室/家庭/カフェ/路上/車内/イヤホン/スピーカーフォン/2名会話/被り発話）。指標は DER/JER、overlap DER、speaker-attributed WER、cpWER、timestamp MAE、pause boundary F1。

### E. 逸脱/変化検出（DI本体）

集団平均との差でなく、**文脈補正された個人内平均との差**で計算する。

| 手法 | 用途 | 推奨 |
|------|------|------|
| robust z-score（median/MAD） | 各特徴の単純な逸脱 | 初期DIの主軸 |
| shrinkage Mahalanobis距離 | 相関した複数特徴の同時逸脱 | 軸ごと。少数サンプルは Ledoit-Wolf 縮小共分散 |
| Wasserstein / JS距離 | 直近ウィンドウ vs baseline分布 | SSL埋め込み・F0分布 |
| Bayesian Online Change Point Detection | 急な状態変化 | 連続利用で有効 |
| EWMA / CUSUM / Page-Hinkley | 小さなドリフト | 実運用で安定、日次/週次 |
| 階層Bayes / mixed effects | コールドスタート | 年齢・性別・端末・録音条件で部分プーリング |

**ベースライン設計**:
- モック: 3〜5録音で仮baseline（「暫定」と明示）
- 初期実用: 14日 or 20〜30録音（曜日・時間帯・場所のばらつきを含む）
- 研究品質: 28日以上
- 常時録音拡張: 発話イベントを1日単位で集約、日内サイクルを明示モデル化

**DI計算例**:
```text
1. raw audio → QC / VAD / diarization / ASR / feature extraction
2. 文脈補正: r_i,t = f_i,t - E[f_i | device, noise, time_of_day, prompt, speaker_role]
3. 個人baseline: z_i,t = (r_i,t - median_i,baseline) / (1.4826 * MAD_i,baseline)
4. 軸別DI: DI_axis,t = sign(mean(z_axis,t)) * sqrt(z_axis,t^T Σ_axis^-1 z_axis,t)
5. 変化検出: EWMA + BOCPD + recent-window vs baseline distance
6. 生成: 「いつもより声の抑揚が低く、応答までの間が長い。録音環境の影響は小さい。」
```

### F. チャネル間不一致（voice–text mismatch、署名指標）

独自性のある署名指標として有望。臨床的意味づけは探索段階。単発でなく**同方向のズレの個人内反復**を見る。

| 不一致タイプ | 例 | 定量化 |
|--------------|-----|--------|
| positive text × flattened voice | 「元気です」だが F0変動・energy・表出性が低い | text valence − voice valence |
| neutral text × high arousal voice | 内容は事務的だが声が速く高緊張 | arousal mismatch、speech rate z |
| negative text × calm voice | ネガティブ内容だが声は平坦 | masking / emotional blunting候補 |
| self-report × voice mismatch | 本人申告の気分と声が乖離 | EMA気分 − voice affect embedding |

参考: CH-SIMS / CH-SIMS v2.0（中国語マルチモーダル感情、単一モダリティ別ラベル）が mismatch 設計に有用。

### G. 交絡の統制（妥当性の最大の脅威）

マイク・部屋・距離・コーデック・雑音が心理状態以上の変動を作る。2025 vocal biomarker master protocol は V3 framework（verification / analytical validation / clinical validation）を推奨。

| 交絡 | 対策 |
|------|------|
| 端末/マイク | 初回に端末ID・マイク経路を固定。端末変更時は baseline 再校正 |
| コーデック | 可能なら PCM/WAV 保存。圧縮差が重要特徴に影響（17,298サンプルの報告） |
| 距離/向き | 録音前に音量・SNR・clipping・距離proxyを測り、低品質なら再録音 |
| 部屋音響/残響 | reverb proxy、noise class を共変量化 |
| 背景音 | VAD、noise suppression は ASR用と特徴抽出用でパスを分ける。DI用音響特徴に過剰denoiseをかけない |
| 時間帯/活動 | 朝/夜、歩行中、運動後、飲酒後、風邪、睡眠時間を共変量化 |
| 話題/プロンプト | 毎回同じ30秒課題＋自由会話を併用。課題別baseline |

### H. 妥当性・信頼性・評価設計

パイプライン評価とDI妥当性評価を分ける（V3 framework）。

| 評価対象 | 指標 | 合格基準の考え方 |
|----------|------|------------------|
| ASR | WER/CER、専門語WER、フィラー保持率 | DIではフィラー削除モデルを避ける |
| 話者分離 | DER、JER、overlap DER、SA-WER | 最重要。2名会話・被り発話で評価 |
| タイムスタンプ | word boundary MAE、pause boundary F1 | 応答潜時・ポーズ構造の根拠 |
| 特徴量信頼性 | test–retest ICC、Bland–Altman、端末差 | 同一条件で同一スコア |
| DI妥当性 | PHQ-9/GAD-7/KSS/睡眠ログ/体調ログとの収束的妥当性 | 診断でなく相関・変化方向 |
| 既知摂動 | 寝不足・風邪・急性ストレス・運動後 | 動くべき軸が動くか、無関係軸が動きすぎないか |
| 汎化 | unseen speaker/device/room | **発話単位splitは禁止。参加者・端末単位split** |

臨床試験化する場合は CONSORT-AI / SPIRIT-AI を参照。

### I. 倫理・規制・プライバシー

設計・表現次第でウェルネスにも SaMD にもなりうる。境界を越えやすい表現は避ける。

| 論点 | 要点 |
|------|------|
| 米国 | FDA General Wellness: 疾病診断・治療・予防に関係しない低リスク機能はウェルネス扱い |
| 日本 | PMDA: 疾病の診断・治療を意図し機能不全が生命/健康にリスクを与えるソフトは医療機器規制対象 |
| EU | EU AI Act: biometric data は special category、emotion recognition は高リスクになりうる |
| GDPR | biometric による一意識別・health data は原則処理禁止、明示的同意等の例外が必要 |
| 日本APPI | 特定個人を識別できる音声録音は個人情報、声質特徴は個人識別符号になりうる |
| 要配慮 | 病歴・心身の障害・健診結果・診療等は要配慮個人情報、取得・第三者提供は原則同意 |

**推奨プロダクト表現**: 「うつ傾向」「認知症リスク」「自殺リスク」「飲酒判定」でなく、
「いつもより声のテンポが遅く、間が長めです」「声のエネルギーが低めに出ています」「休息・睡眠・体調を振り返るきっかけに」。

**プライバシーアーキテクチャ**:
- raw audio は原則短期保存またはオンデバイス処理
- サーバー保存は非可逆特徴量・統計量・埋め込み中心
- bystander voice を検出し第三者発話は保存しない/マスク
- voiceprint は別同意・別保管・短期有効
- 研究/モデル改善利用は明示的 opt-in
- 医療/メンタル推定ログは要配慮相当で暗号化・アクセス制御

### J. 日本語・国内事情

| 資源 | 内容 | 用途 |
|------|------|------|
| JTES | 100話者、4感情、20,000発話、23.5時間 | 日本語SER初期検証（演技音声中心） |
| UUDB | 自発的日本語対話、7ペア、4,737発話、感情状態ラベル | 対話・相づち・感情表出（小規模） |
| 高齢者音声DB（KAKEN等） | 超高齢者中心の大規模対話DB | 日本語認知軸の参考（アクセス制限あり） |
| 日本MCI音声研究 | 地域在住高齢者1,461名、自由会話、Wav2Vec2 512次元、AUC 0.89 | 国内PoCで最重要の参考例 |

中国語文献: 中国人女性再発性うつ（ピッチ変化 AUC 0.90）、PDCH（うつ相談データ）、CH-SIMS/v2.0、M3ED、EmotionTalk。

---

## 3. 参照アーキテクチャへのマッピングと推奨

### ① ASR / 話者分離 / タイムスタンプ

**第1候補**: ElevenLabs Scribe v2 + pyannoteAI Precision-2（話者分離独立レイヤー）+ Deepgram Nova-3 Multilingual（雑音対抗）の比較/アンサンブル。

**対抗**: Speechmatics Ursa 2（オンプレ）/ AssemblyAI Universal（日本語3.5 Pro確認後）/ Gladia / OSS（Parakeet JA + WhisperX + pyannote Community-1）。

**実装注意（重要）**:
- **no-verbatim / filler removal / disfluency removal は OFF**。「えー」「あの」「言い直し」「沈黙」は認知軸の信号。
- 日本語は空白区切りがないため、word timestamp でなく **morpheme/mora/character timestamp** も評価対象に。
- pause/latency は ASR文字境界でなく **VAD＋speaker turn boundary** から抽出。

### ② 音声直接入力マルチモーダルLLM

**第1候補**: Gemini audio 系を主解釈器、OpenAI GPT-Realtime-2 をセカンドオピニオン、Qwen3-Omni を自ホスト対抗。出力は JSON schema 固定、自由記述は別フィールド。

**出力スキーマ例**:
```json
{
  "speaker_state_observation": {
    "energy": "lower_than_typical_or_low",
    "prosody": "flat_or_reduced_variability",
    "pace": "slow_or_variable",
    "pauses": "frequent_long_pauses",
    "voice_quality": ["breathy", "hoarse", "strained"],
    "environment": ["quiet", "background_speech", "traffic_noise"],
    "confidence": 0.0
  },
  "unsupported_claims_to_avoid": ["diagnosis", "disease_probability", "personality_label"]
}
```

②のLLM出力は DI のナラティブ補助・異常説明・言語化に使い、**スコア本体には使わない**。

### ③ 統合・プロファイリングLLM

テキスト専用の高性能推論LLMを、厳格な schema/RAG/ガードレール付きで使う。
入力は ASR逐語＋話者ラベル＋timestamps、DI軸別スコア＋信頼区間＋録音品質、②の構造化観察、ユーザー自己申告（睡眠/体調/活動）、過去平均との差分。
出力は病名・診断・リスク断定でなく「今日の声の変化」「いつもと違う軸」「録音環境による不確実性」「振り返り質問」「一般的提案」に限定。

### DI 実装推奨（数値供給）

| DI軸 | 主特徴 | 補助モデル |
|------|--------|-----------|
| 感情/表出 | F0 range、energy、spectral slope、emotion2vec+ embedding、SER posterior | emotion2vec+、SenseVoice、Gemini/GPT観察 |
| 認知テンポ | words/sec、mora/sec、pause ratio、mean/max pause、response latency、filled pause、repair | ASR+VAD+diarization |
| 行動/対話 | turn length、talk time ratio、interruptions、backchannel、latency | pyannote + ASR |
| 声質/運動 | jitter、shimmer、HNR、CPP、formant stability、articulation rate | openSMILE/Praat/DisVoice |
| 体調負荷 | cough、breathiness、hoarseness、nasal/strained voice、SNR-normalized energy | SenseVoice/event model、BEATs系 |
| 不一致 | voice valence/arousal vs text sentiment/self-report | text sentiment model + voice scorer |

**可視化**: レーダー（軸のかたち）、縦断線（日次DI・7日移動平均・変化点）、信頼度表示（baseline不足/録音品質/話者分離信頼度/モデル一致度）、署名指標（mismatch の方向と反復性）、ナラティブ（「いつもより」「この録音条件では」「確定ではなく」）。

### 未決事項への回答

**(i) SED/SER を完全にLLMへ置換すべきか → 置換すべきでない**。LLMは説明・要約・状況理解に、DI用には固定バージョンのSER/SED/音響スコアモデルを残す。理由: LLMの出力揺れ・幻覚・モデル更新による縦断不連続。

**(ii) 日本語で話者分離最優先のASR選定 → 初期評価ラインナップ**: ①Scribe v2 ②Deepgram Nova-3 ③Speechmatics Ursa 2 ④pyannoteAI Precision-2（独立レイヤー）⑤OSS（Parakeet JA + WhisperX + pyannote Community-1）。最終選定は日本語自社セットで DER/JER/SA-WER を測って決める（ベンダー公開WERでは決めない）。

**(iii) baseline確立に必要なデータ量と運用**: デモ 3〜5録音（暫定表示）/ 実用開始 14日 or 20〜30録音 / 安定運用 30日ローリング＋長期の二重管理 / 常時録音は1日・半日単位に集約 / 端末変更・風邪・旅行・飲酒・睡眠不足は baseline更新でなく文脈タグで補正。

---

## 4. リスク・不確実性・今後12か月で変わりそうな点

1. 音声LLMの性能は急変する。DIの縦断一貫性を守るためモデル更新を即時反映せず versioned scorer で固定運用。
2. ASR/diarizationの日本語実性能は公開ベンチでは判断不能。特に2名会話・被り発話・相づち・短い応答・生活雑音で崩れる。自社ベンチ必須。
3. 音声バイオマーカー研究は再現性課題が大きい（標準化不足・録音条件差・データリーク・発話内容依存・交絡）。master protocol と V3 validation を前提に。
4. 規制境界は UI文言と機能で変わる。病名・確率・治療推奨を避ければウェルネス側に留まれる。
5. voice–text mismatch は差別・監視用途に転用されやすい。採用・人事評価・保険・教育評価に使わない明確なポリシーが必要。
6. 日本語・中国語データは重要だが文化差（感情表出・沈黙・相づち・敬語・フィラー）。英語SERをそのまま日本語DIに移植しない。

---

## 5. 主要参考文献（抜粋、URLは調査ログ参照）

- BMC Psychiatry 2024（うつ音声、MDD AUC 0.93）
- JMIR 2024（モバイル音声、うつ/不安/不眠/疲労 AUC 0.68〜0.78）
- Scientific Reports 2025（自殺 AUC 0.74/0.85）
- npj Digital Medicine 2025（認知症/MCI XAI レビュー AUC 0.76〜0.94）
- The Lancet Regional Health – Western Pacific 2025 / 国立循環器病研究センター（日本語 MCI AUC 0.89）
- Molecular Psychiatry 2025（中国人女性うつ、ピッチ AUC 0.90）
- emotion2vec（ACL 2024）/ emotion2vec+ / SenseVoice / Qwen3-Omni / Qwen2.5-Omni / Phi-4-multimodal（各モデルカード）
- ElevenLabs Scribe v2 / Deepgram Nova-3 / Speechmatics Ursa 2 / NVIDIA Parakeet JA / WhisperX / pyannoteAI（各公式ドキュメント）
- Digital phenotyping relapse prediction systematic review 2026
- Speech-based digital biomarker V3 evaluation / vocal biomarker master protocols 2025 / CONSORT-AI・SPIRIT-AI
- FDA General Wellness / FDA AI/ML SaMD / PMDA SaMD / 個人情報保護委員会ガイドライン / EU AI Act / GDPR Art.9
