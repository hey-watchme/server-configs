# WatchMe Audio Processor Lambda

## 1. 概要 (Concept)

このLambda関数は、WatchMeプラットフォームの音声分析処理をイベント駆動で実行するための中核的な役割を担います。

従来は1時間ごとのスケジュール実行（cron）だったため、ユーザーが結果を確認するまでに大きな遅延が発生していました。この関数は、S3バケットへの音声ファイルアップロードをトリガーとして即座に実行されることで、ニア・リアルタイムな分析体験を実現します。

## 2. 処理フロー (Workflow)

1.  各デバイスから録音された音声ファイル（`.wav`）が `s3://watchme-vault/files/` 以下にアップロードされます。
    - S3パスは `files/{device_id}/YYYY-MM-DD/HH-MM/audio.wav` となります
2.  S3が `ObjectCreated` イベントを検知し、このLambda関数を自動的にトリガーします。
3.  Lambda関数は、イベント情報からアップロードされたファイルのバケット名とキー（パス）を取得します。
4.  **すべてのデバイスを一律処理対象とします**（iPhone、オブザーバー、その他すべて）
5.  取得したファイルパスを元に、以下の各種分析APIを呼び出します：
    - **Azure Speech API** (vibe-transcriber-v2) - 音声文字起こし
    - **AST API** (behavior-features) - 音響イベント検出
    - **SUPERB API** (emotion-features) - 感情認識
6.  **イベント駆動型の処理連鎖**:
    - AST APIの処理が完了すると、自動的に**SED Aggregator API**を起動
    - SED Aggregatorは非同期でバックグラウンド実行（Lambda関数は完了を待たない）
7.  各APIの処理結果はそれぞれのAPIで直接Supabaseデータベースに保存されます。

## 3. 依存関係 (Dependencies)

- **Python 3.11**
- 必要なライブラリは `requirements.txt` に記載されています。

## 4. 環境変数 (Environment Variables)

この関数は、動作のために以下の環境変数を必要とします。AWS Lambdaの管理コンソールから設定してください。

| キー | 値の例 | 説明 |
| --- | --- | --- |
| `API_BASE_URL` | `https://api.hey-watch.me` | 各種分析APIのベースURL。 |

### 変更履歴 (2025-09-22 v3)
- **イベント駆動型処理の実装**: AST API処理完了後、自動的にSED Aggregatorを起動
- **処理の連鎖**: AST (音響イベント検出) → SED Aggregator (行動パターン集計) の自動連携
- **非同期タスク管理**: SED Aggregatorのタスクは非同期で実行、task_idのみ取得

### 変更履歴 (2025-09-22 v2)
- **すべてのデバイスを一律処理**: iPhoneプレフィックス判定を削除し、S3にアップロードされたすべてのオーディオファイルを処理対象に変更
- **環境変数の削除**: `IPHONE_PREFIX`, `ENABLE_ALL_DEVICES`, `TEST_DEVICES` を削除
- **iOSアプリ連携修正**: プレフィックスなしの純粋なdevice_idを使用するよう変更

### 変更履歴 (2025-09-22)
- **デバッグ用ログ追加**: Azure Speech APIのレスポンス詳細をログ出力するように修正
- **エラーハンドリング改善**: APIレスポンスのパースエラー時に詳細情報を記録
- **Vibe Scorer API削除**: 使用されていないコードを削除

### 変更履歴 (2025-09-21)
- **プレフィックスベースの判定を採用**: iPhoneデバイスは`iphone_`プレフィックスで識別
- **Supabase依存の一時回避**: pydantic_coreエラーのため、device_typeベースの判定は保留

## 5. デプロイ手順 (Deployment)

Lambda関数のコードを更新する際は、以下の手順でデプロイパッケージを作成し、アップロードします。

### ⚠️ 超重要：ビルド時の注意事項

**絶対にDockerを使用したビルドスクリプトを使わないでください！**
Dockerコンテナ内でビルドすると、ローカルの変更が反映されない問題が発生します。

### 正しいビルド手順

1.  **ローカルでコードを修正**
    - このディレクトリにある `lambda_function.py` を編集します。

2.  **build.shスクリプトを使用**（推奨）
    ```bash
    # このディレクトリに移動
    cd /path/to/watchme-audio-processor
    
    # ビルドスクリプトを実行
    ./build.sh
    ```
    
    このスクリプトは以下を実行します：
    - 古いビルドファイルを削除
    - **ローカルの** `lambda_function.py` をコピー
    - 依存関係をインストール
    - ZIPファイルを作成

3.  **手動ビルド**（build.shが動作しない場合）
    ```bash
    # クリーンアップ
    rm -rf build function.zip
    
    # ビルドディレクトリ作成
    mkdir build
    
    # 重要：ローカルのファイルをコピー
    cp lambda_function.py build/
    
    # 依存関係インストール
    pip3 install --target ./build requests --quiet
    
    # ZIP作成
    cd build
    zip -r ../function.zip .
    cd ..
    ```

4.  **変更が反映されているか必ず確認**
    ```bash
    # ZIPファイル内のコードを確認
    unzip -p function.zip lambda_function.py | grep "追加したコード"
    ```

5.  **AWSコンソールからアップロード**
    - AWS Lambdaの `watchme-audio-processor` 関数のページを開きます。
    - 「コードソース」セクションの「アップロード元」から「.zipファイル」を選択します。
    - 作成した `function.zip` をアップロードし、「保存」をクリックします。

### 🚨 トラブルシューティング

**「no change」と表示される場合：**
- ブラウザキャッシュをクリア（Ctrl+F5）
- Lambda関数のコードエディタで直接変更を確認
- 環境変数を一時的に変更して強制再デプロイ

**変更が反映されない場合：**
1. CloudWatchログで実行されているコードを確認
2. ZIPファイル内のコードが最新か確認
3. Lambda関数のバージョンが更新されているか確認
