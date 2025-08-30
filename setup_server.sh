#!/bin/bash
# ==============================================================================
# WatchMe Server Configuration Setup Script
# ==============================================================================
#
# このスクリプトは、watchme-server-configsリポジトリ内の設定ファイルを
# EC2サーバーの適切な場所に配置し、サービスを有効化するためのものです。
# 新しいサーバーをセットアップした際や、構成をリセットしたい場合に実行します。
#
# 実行方法:
# 1. このリポジトリをサーバーの /home/ubuntu/watchme-server-configs にクローン
# 2. cd /home/ubuntu/watchme-server-configs
# 3. chmod +x setup_server.sh
# 4. ./setup_server.sh
#
# ==============================================================================

set -e # いずれかのコマンドが失敗したら、ただちにスクリプトを終了する

echo "=== WatchMe Server Configuration Setup ==="
echo "This script will link systemd and Nginx configurations."
echo "Sudo privileges will be required."

# このスクリプトが存在するディレクトリの絶対パスを取得
# これにより、どこから実行しても正しく動作する
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

# --- Systemd Setup ---
echo ""
echo "--> Setting up systemd services..."
SYSTEMD_DIR="$SCRIPT_DIR/systemd"

if [ -d "$SYSTEMD_DIR" ]; then
  # systemdディレクトリ内の全ての.serviceファイルをループ処理
  for service_file in "$SYSTEMD_DIR"/*.service; do
    if [ -f "$service_file" ]; then
      service_name=$(basename "$service_file")
      target_path="/etc/systemd/system/$service_name"
      echo "Linking $service_name to $target_path..."
      # シンボリックリンクを作成（-fオプションで既存のリンクを上書き）
      sudo ln -sf "$service_file" "$target_path"
    fi
  done
else
  echo "WARNING: 'systemd' directory not found. Skipping systemd setup."
fi

echo "Reloading systemd daemon to recognize new services..."
sudo systemctl daemon-reload
echo "Systemd setup complete."
echo ""

# --- Nginx Setup ---
echo "--> Setting up Nginx sites..."
NGINX_DIR="$SCRIPT_DIR/sites-available"

if [ -d "$NGINX_DIR" ]; then
  for nginx_conf in "$NGINX_DIR"/*; do
    if [ -f "$nginx_conf" ]; then
      conf_name=$(basename "$nginx_conf")
      target_path="/etc/nginx/sites-available/$conf_name"
      enabled_path="/etc/nginx/sites-enabled/$conf_name"
      
      echo "Linking $conf_name to $target_path..."
      sudo ln -sf "$nginx_conf" "$target_path"
      
      # sites-enabledにもリンクを作成してサイトを有効化
      if [ ! -L "$enabled_path" ]; then
        echo "Enabling site: $conf_name"
        sudo ln -s "$target_path" "$enabled_path"
      fi
    fi
  done
else
  echo "WARNING: 'sites-available' directory not found. Skipping Nginx setup."
fi

echo "Testing Nginx configuration syntax..."
sudo nginx -t

echo "Reloading Nginx to apply new configuration..."
sudo systemctl reload nginx
echo "Nginx setup complete."
echo ""

# --- Infrastructure Service ---
echo "--> Enabling and starting the base infrastructure service..."
# watchme-infrastructure.serviceが存在すれば、有効化して起動する
if systemctl list-unit-files | grep -q 'watchme-infrastructure.service'; then
    echo "Enabling and starting watchme-infrastructure.service..."
    sudo systemctl enable --now watchme-infrastructure.service
    echo "Waiting a moment for the infrastructure to settle..."
    sleep 3
    sudo systemctl status watchme-infrastructure.service --no-pager
else
    echo "WARNING: watchme-infrastructure.service not found. Please ensure it exists."
fi

echo ""
echo "=== Setup Finished Successfully! ==="
echo "NOTE: This script enables the base infrastructure."
echo "You may need to enable other specific services individually using 'sudo systemctl enable --now <service-name>'"
