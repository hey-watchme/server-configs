#!/bin/bash
set -e

echo "Building watchme-audio-worker Lambda function..."

# クリーンアップ
rm -rf build function.zip

# ビルドディレクトリ作成
mkdir build

# Lambdaファイルをコピー
cp lambda_function.py build/

# 依存関係をインストール
pip3 install --target ./build requests --quiet

# ZIP作成
cd build
zip -r ../function.zip .
cd ..

echo "✅ Build complete: function.zip"
ls -lh function.zip