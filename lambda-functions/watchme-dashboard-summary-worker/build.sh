#!/bin/bash

# Build script for watchme-dashboard-summary-worker Lambda function

echo "Building watchme-dashboard-summary-worker Lambda function..."

# ディレクトリのパス
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BUILD_DIR="${SCRIPT_DIR}/build"

# ビルドディレクトリをクリーンアップ
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# 依存関係をインストール
echo "Installing dependencies..."
pip3 install -r requirements.txt -t "${BUILD_DIR}/" --no-cache-dir

# Lambda関数のコードをコピー
echo "Copying Lambda function code..."
cp lambda_function.py "${BUILD_DIR}/"

# ZIPファイルを作成
echo "Creating deployment package..."
cd "${BUILD_DIR}"
zip -r ../function.zip . -x "*.pyc" -x "__pycache__/*"

cd "${SCRIPT_DIR}"
echo "Build completed. Deployment package: function.zip"
echo "Size: $(du -h function.zip | cut -f1)"