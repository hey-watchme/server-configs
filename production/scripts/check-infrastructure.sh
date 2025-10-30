#!/bin/bash

# =============================================================================
# WatchMe Infrastructure Health Check Script
# =============================================================================
# 用途: watchme-networkの状態確認と自動修復
# 実行: ./check-infrastructure.sh
# Cron: */5 * * * * /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh
# =============================================================================

set -e

# カラー出力の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ログファイル
LOG_FILE="/var/log/watchme-infrastructure.log"

# タイムスタンプ付きログ出力
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# エラー出力
error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# 成功出力
success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

# 警告出力
warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# =============================================================================
# メイン処理
# =============================================================================

log "Starting infrastructure health check..."

# 1. Docker動作確認
if ! docker version > /dev/null 2>&1; then
    error "Docker is not running or not accessible"
    exit 1
fi

# 2. watchme-network存在確認
if ! docker network ls | grep -q "watchme-network"; then
    warning "watchme-network not found! Creating..."
    
    # docker-compose.infra.ymlから作成を試みる
    INFRA_COMPOSE="/home/ubuntu/watchme-server-configs/docker-compose.infra.yml"
    
    if [ -f "$INFRA_COMPOSE" ]; then
        docker-compose -f "$INFRA_COMPOSE" up -d
        if [ $? -eq 0 ]; then
            success "watchme-network created successfully"
        else
            error "Failed to create watchme-network"
            exit 1
        fi
    else
        # 手動作成（フォールバック）
        docker network create --driver bridge --subnet=172.27.0.0/16 watchme-network
        if [ $? -eq 0 ]; then
            success "watchme-network created manually"
        else
            error "Failed to create watchme-network manually"
            exit 1
        fi
    fi
else
    success "watchme-network exists"
fi

# 3. ネットワーク詳細情報取得
NETWORK_INFO=$(docker network inspect watchme-network 2>/dev/null)
if [ $? -ne 0 ]; then
    error "Failed to inspect watchme-network"
    exit 1
fi

# 4. 接続されているコンテナ数を確認
CONTAINER_COUNT=$(echo "$NETWORK_INFO" | jq -r '.[0].Containers | length')
log "Connected containers: $CONTAINER_COUNT"

# 5. 必須コンテナのリスト
REQUIRED_CONTAINERS=(
    "watchme-scheduler-prod"
    "watchme-api-manager-prod"
    "api_gen_prompt_mood_chart"
    "api-transcriber"
    "api-gpt-v1"
    "opensmile-api"
    "opensmile-aggregator"
    "api-sed-aggregator"
    "watchme-vault-api"
    "watchme-web-prod"
)

# 6. 各必須コンテナの接続状態を確認
DISCONNECTED_CONTAINERS=()

for container in "${REQUIRED_CONTAINERS[@]}"; do
    # コンテナが存在するか確認
    if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        # コンテナが実行中か確認
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            # ネットワークに接続されているか確認
            if ! echo "$NETWORK_INFO" | jq -r '.[0].Containers[].Name' | grep -q "^${container}$"; then
                warning "Container $container is not connected to watchme-network"
                DISCONNECTED_CONTAINERS+=("$container")
                
                # 自動接続を試みる
                log "Attempting to connect $container to watchme-network..."
                if docker network connect watchme-network "$container" 2>/dev/null; then
                    success "Successfully connected $container to watchme-network"
                else
                    error "Failed to connect $container to watchme-network"
                fi
            else
                log "✓ $container is connected"
            fi
        else
            warning "Container $container is not running"
        fi
    else
        log "Container $container does not exist (may not be deployed yet)"
    fi
done

# 7. ネットワークのIP範囲確認
SUBNET=$(echo "$NETWORK_INFO" | jq -r '.[0].IPAM.Config[0].Subnet')
GATEWAY=$(echo "$NETWORK_INFO" | jq -r '.[0].IPAM.Config[0].Gateway')
log "Network subnet: $SUBNET"
log "Network gateway: $GATEWAY"

# 8. 結果サマリー
echo "============================================="
if [ ${#DISCONNECTED_CONTAINERS[@]} -eq 0 ]; then
    success "All required containers are properly connected"
    EXIT_CODE=0
else
    warning "Some containers needed reconnection:"
    for container in "${DISCONNECTED_CONTAINERS[@]}"; do
        echo "  - $container"
    done
    EXIT_CODE=1
fi

# 9. 統計情報の出力
echo "============================================="
echo "Infrastructure Statistics:"
echo "  Total containers connected: $CONTAINER_COUNT"
echo "  Network: $SUBNET"
echo "  Gateway: $GATEWAY"
echo "============================================="

log "Infrastructure health check completed"

exit $EXIT_CODE