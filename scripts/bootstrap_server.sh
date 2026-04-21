#!/bin/bash
# ================================================================
# Установка зависимостей на новом сервере (один раз перед первым деплоем)
# ================================================================
# Запуск: из корня проекта, после export DEPLOY_SERVER="root@IP"
#   ./scripts/bootstrap_server.sh
# ================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
info() { echo -e "${YELLOW}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

SERVER="${DEPLOY_SERVER:?Задай DEPLOY_SERVER, например: export DEPLOY_SERVER=root@203.0.113.10}"

echo ""
info "Установка зависимостей на сервере: $SERVER"
echo ""

ssh -t $SERVER '
set -e
export DEBIAN_FRONTEND=noninteractive
echo "Обновление пакетов..."
apt-get update -qq
echo "Установка Python 3, venv, Node.js, npm..."
apt-get install -y python3 python3-pip nodejs npm > /dev/null
# На Ubuntu 24.04 нужен python3.12-venv; на старых системах — python3-venv
apt-get install -y python3.12-venv 2>/dev/null || apt-get install -y python3-venv
echo "Установка PM2 глобально..."
npm install -g pm2
echo ""
echo "Готово. Можно запускать деплой с локальной машины."
'
success "Сервер готов к деплою."
echo ""
