#!/bin/bash

# Build script for watchme-demo-generator-v2 Lambda function

echo "Building watchme-demo-generator-v2 Lambda function..."

# Directory paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BUILD_DIR="${SCRIPT_DIR}/build"

# Clean build directory
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt -t "${BUILD_DIR}/" --no-cache-dir

# Copy Lambda function code
echo "Copying Lambda function code..."
cp lambda_function.py "${BUILD_DIR}/"

# Copy data directory with proper structure
echo "Copying data directory..."
mkdir -p "${BUILD_DIR}/data"
cp -r data/child_5yo_active "${BUILD_DIR}/data/"

# Create ZIP file
echo "Creating deployment package..."
cd "${BUILD_DIR}"
zip -r ../function.zip . -x "*.pyc" -x "__pycache__/*"

cd "${SCRIPT_DIR}"
echo "Build completed. Deployment package: function.zip"
echo "Size: $(du -h function.zip | cut -f1)"