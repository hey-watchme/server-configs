#!/bin/bash

# ビルドディレクトリをクリーンアップ
echo "🧹 Cleaning build directory..."
rm -rf build function.zip

# ビルドディレクトリを作成
mkdir -p build

echo "📦 Building Lambda package..."

# 重要：ローカルのlambda_function.pyをビルドディレクトリにコピー
echo "📝 Copying lambda_function.py from local directory..."
cp lambda_function.py build/

# 依存関係をインストール（requestsのみ必要）
echo "📚 Installing dependencies..."
pip3 install --target ./build requests --quiet

# ZIPファイルを作成
echo "🗜️ Creating function.zip..."
cd build
zip -r ../function.zip . -q
cd ..

if [ -f function.zip ]; then
  echo "✅ function.zip created successfully"
  ls -lh function.zip
else
  echo "❌ Failed to create function.zip"
  exit 1
fi