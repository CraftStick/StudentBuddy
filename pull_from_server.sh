#!/bin/bash
# ================================================================
# Выгрузка проекта с сервера (старая версия — парсер и всё остальное)
# ================================================================
# Запускай из корня StudentBuddy. По умолчанию копирует в ./from_server/
# Чтобы перезаписать текущую папку: ./pull_from_server.sh overwrite
# ================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

SERVER="${DEPLOY_SERVER:?Укажите DEPLOY_SERVER, например: export DEPLOY_SERVER=root@203.0.113.10}"
REMOTE_PATH="${DEPLOY_PATH:-/opt/studentbuddy}"
TARGET="${1:-from_server}"

echo ""
echo "=========================================="
echo "⬇️  Выгрузка StudentBuddy с сервера"
echo "=========================================="
echo ""
info "Сервер: $SERVER"
info "Путь на сервере: $REMOTE_PATH"
info "Куда сохранить локально: $TARGET"
echo ""

if [ "$TARGET" = "overwrite" ]; then
    warning "Режим overwrite: файлы будут скопированы В ТЕКУЩУЮ ПАПКУ (. и подпапки)."
    warning "Рекомендуется сначала сделать бэкап: cp -r . ../StudentBuddy_backup_\$(date +%Y%m%d)"
    read -p "Продолжить? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[yY]$ ]]; then
        echo "Отменено."
        exit 0
    fi
    DEST="."
else
    if [ -d "$TARGET" ]; then
        warning "Папка $TARGET уже есть. Будет перезаписана."
    fi
    mkdir -p "$TARGET"
    DEST="$TARGET"
fi

info "Копирование с сервера (rsync)..."
rsync -avz --progress \
    --exclude 'venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'node_modules' \
    --exclude '.git' \
    --exclude 'from_server' \
    "$SERVER:$REMOTE_PATH/" "$DEST/" || error "Ошибка rsync. Проверь SSH: ssh $SERVER"

# Проверка: все папки в корне
info "Проверка папок в корне..."
EXPECTED_DIRS="data database handlers keyboards locales middlewares parser replacements timetable utils"
MISSING=""
for dir in $EXPECTED_DIRS; do
    if [ ! -d "$DEST/$dir" ]; then
        MISSING="$MISSING $dir"
    fi
done
if [ -n "$MISSING" ]; then
    warning "На сервере нет или не скопировались папки:$MISSING"
else
    success "Все ожидаемые папки в корне на месте."
fi
echo ""
echo "Содержимое корня $DEST:"
ls -la "$DEST" | grep -E '^d|^-' || true
echo ""
success "Готово. Код с сервера в: $DEST"
echo "Парсер: $DEST/parser/mosgortrans-master/"
echo ""
