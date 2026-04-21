#!/bin/bash
# ================================================================
# StudentBuddy — удаление проекта с сервера
# ================================================================
# Останавливает PM2-процесс, удаляет каталог проекта и бэкапы.
# Используй те же переменные, что и для deploy.sh.
# ================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${YELLOW}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

SERVER="${DEPLOY_SERVER:?Укажите DEPLOY_SERVER, например: export DEPLOY_SERVER=root@203.0.113.10}"
REMOTE_PATH="${DEPLOY_PATH:-/opt/studentbuddy}"
PM2_APP_NAME="${PM2_APP_NAME:-student-buddy}"

echo ""
echo "=========================================="
echo "🗑  Удаление StudentBuddy с сервера"
echo "=========================================="
echo ""
info "Сервер: $SERVER"
info "Путь:   $REMOTE_PATH"
info "PM2:    $PM2_APP_NAME"
echo ""

if [ "${1:-}" != "--yes" ]; then
    echo "Будет выполнено:"
    echo "  - pm2 stop $PM2_APP_NAME && pm2 delete $PM2_APP_NAME && pm2 save"
    echo "  - rm -rf $REMOTE_PATH"
    echo "  - rm -rf ~/studentbuddy_backups"
    echo ""
    read -p "Продолжить? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Отменено."
        exit 0
    fi
fi

info "Остановка и удаление PM2-процесса..."
ssh $SERVER "pm2 stop $PM2_APP_NAME 2>/dev/null || true; pm2 delete $PM2_APP_NAME 2>/dev/null || true; pm2 save" || warning "PM2: процесс не найден или уже удалён"

info "Удаление каталога проекта..."
ssh $SERVER "rm -rf $REMOTE_PATH" || error "Не удалось удалить $REMOTE_PATH"

info "Удаление резервных копий..."
ssh $SERVER "rm -rf ~/studentbuddy_backups" || true

success "Проект удалён с сервера."
echo ""
