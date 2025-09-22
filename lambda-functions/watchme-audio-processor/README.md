# WatchMe Audio Processor Lambda

## 1. 概要 (Concept)

このLambda関数は、WatchMeプラットフォームの音声分析処理をイベント駆動で実行するための中核的な役割を担います。

従来は1時間ごとのスケジュール実行（cron）だったため、ユーザーが結果を確認するまでに大きな遅延が発生していました。この関数は、S3バケットへの音声ファイルアップロードをトリガーとして即座に実行されることで、ニア・リアルタイムな分析体験を実現します。

## 2. 処理フロー (Workflow)

1.  iOSアプリから録音された音声ファイル（`.wav`）が `s3://watchme-vault/files/` 以下にアップロードされます。
    - iPhoneデバイスの場合、S3パスは `files/iphone_{device_id}/YYYY-MM-DD/HH-MM/audio.wav` となります
2.  S3が `ObjectCreated` イベントを検知し、このLambda関数を自動的にトリガーします。
3.  Lambda関数は、イベント情報からアップロードされたファイルのバケット名とキー（パス）を取得します。
4.  デバイスIDを判定し、処理対象かどうかを確認します：
    - `iphone_`プレフィックス付きのデバイスID → iPhoneデバイスとして処理
    - `TEST_DEVICES`環境変数に含まれるデバイスID → テストデバイスとして処理
    - その他 → スキップ（オブザーバーデバイスは従来通りcron処理）
5.  取得したファイルパスを元に、以下の各種分析APIを順次呼び出します：
    - **Azure Speech API** (vibe-transcriber-v2) - 音声文字起こし
    - **AST API** (behavior-features) - 音響イベント検出
    - **SUPERB API** (emotion-features) - 感情認識
6.  各APIの処理結果はそれぞれのAPIで直接Supabaseデータベースに保存されます。

## 3. 依存関係 (Dependencies)

- **Python 3.11**
- 必要なライブラリは `requirements.txt` に記載されています。

## 4. 環境変数 (Environment Variables)

この関数は、動作のために以下の環境変数を必要とします。AWS Lambdaの管理コンソールから設定してください。

| キー | 値の例 | 説明 |
| --- | --- | --- |
| `API_BASE_URL` | `https://api.hey-watch.me` | 各種分析APIのベースURL。 |
| `IPHONE_PREFIX` | `iphone_` | iPhoneデバイスを識別するためのプレフィックス。 |
| `ENABLE_ALL_DEVICES` | `false` | `true`にすると、すべてのデバイスを処理対象とする。コスト管理のため通常は`false`。 |
| `TEST_DEVICES` | `test_device_001,demo_device` | `ENABLE_ALL_DEVICES`が`false`の時に、処理を許可するデバイスIDのリスト（カンマ区切り）。 |

### 変更履歴 (2025-09-22)
- **デバッグ用ログ追加**: Azure Speech APIのレスポンス詳細をログ出力するように修正
- **エラーハンドリング改善**: APIレスポンスのパースエラー時に詳細情報を記録
- **Vibe Scorer API削除**: 使用されていないコードを削除

### 変更履歴 (2025-09-21)
- **プレフィックスベースの判定を採用**: iPhoneデバイスは`iphone_`プレフィックスで識別
- **Supabase依存の一時回避**: pydantic_coreエラーのため、device_typeベースの判定は保留

## 5. デプロイ手順 (Deployment)

Lambda関数のコードを更新する際は、以下の手順でデプロイパッケージを作成し、アップロードします。

1.  **ローカルでコードを修正**
    - このディレクトリにある `lambda_function.py` を編集します。

2.  **パッケージの作成**
    - 以下のコマンドを実行して、コードと依存ライブラリを `function.zip` にまとめます。
    ```bash
    # このディレクトリ (watchme-audio-processor) に移動
    cd /path/to/watchme-audio-processor

    # ビルド用の一時ディレクトリを作成
    mkdir -p build

    # 依存ライブラリをインストール
    pip install -r requirements.txt -t ./build/

    # コード本体をコピー
    cp lambda_function.py ./build/

    # zipファイルを作成
    cd build
    zip -r ../function.zip .
    cd ..
    ```

3.  **AWSコンソールからアップロード**
    - AWS Lambdaの `watchme-audio-processor` 関数のページを開きます。
    - 「コードソース」セクションの「アップロード元」から「.zipファイル」を選択します。
    - 作成した `function.zip` をアップロードし、「保存」または「デプロイ」をクリックします。
