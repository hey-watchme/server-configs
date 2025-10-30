#!/bin/bash
set -e

echo "Building watchme-audio-trigger Lambda function..."

# クリーンアップ
rm -rf build function.zip

# ビルドディレクトリ作成
mkdir build

# Lambdaファイルをコピー
cp lambda_function.py build/

# ZIP作成（boto3は不要なので依存関係なし）
cd build
zip -r ../function.zip .
cd ..

echo "✅ Build complete: function.zip"
ls -lh function.zip