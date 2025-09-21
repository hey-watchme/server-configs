#!/bin/bash

# Dockerを使用してLambda用のパッケージを作成
echo "Building Lambda package with Docker..."

# Pythonの公式Lambdaイメージを使用してビルド
docker run --rm \
  -v "$PWD":/var/task \
  -w /var/task \
  public.ecr.aws/lambda/python:3.11 \
  bash -c "
    pip install --target ./build requests supabase &&
    cp lambda_function.py ./build/ &&
    cd build &&
    zip -r ../function.zip . -q
  "

if [ -f function.zip ]; then
  echo "✅ function.zip created successfully"
  ls -lh function.zip
else
  echo "❌ Failed to create function.zip"
  exit 1
fi