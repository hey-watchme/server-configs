#!/bin/bash
# ==============================================================================
# WatchMe Server Configuration Setup Script
# ==============================================================================
#
# Configures Nginx reverse proxy and Docker network on the EC2 server.
# All API containers are managed by Docker (restart policy + CI/CD),
# NOT by systemd.
#
# Usage:
# 1. Clone this repo to /home/ubuntu/watchme-server-configs
# 2. cd /home/ubuntu/watchme-server-configs/production
# 3. chmod +x setup_server.sh
# 4. ./setup_server.sh
#
# ==============================================================================

set -e

echo "=== WatchMe Server Configuration Setup ==="
echo "This script will configure Nginx and Docker network."
echo "Sudo privileges will be required."

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

# --- Docker Network ---
echo ""
echo "--> Ensuring Docker network exists..."
if docker network inspect watchme-network > /dev/null 2>&1; then
    echo "watchme-network already exists."
else
    echo "Creating watchme-network..."
    docker network create watchme-network
    echo "watchme-network created."
fi

# --- Nginx Setup ---
echo ""
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
echo "=== Setup Finished Successfully! ==="
echo ""
echo "Note: API containers are managed by Docker with restart policies."
echo "  - Deployment: GitHub Actions CI/CD -> ECR -> run-prod.sh"
echo "  - Persistence: Docker restart policy (always / unless-stopped)"
echo "  - To check running containers: docker ps"
