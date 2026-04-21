#!/bin/bash
# ================================================================
# StudentBuddy Deployment Script
# ================================================================
# Скрипт для автоматического деплоя на VPS
# Версия: 2.0.0
# ================================================================

set -e  # Прерывать выполнение при ошибках

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; exit 1; }

# ================================
# Конфигурация
# ================================

# Сервер и путь задаются только через окружение (без значений по умолчанию с реальным хостом)
SERVER="${DEPLOY_SERVER:?Укажите DEPLOY_SERVER, например: export DEPLOY_SERVER=root@203.0.113.10}"
REMOTE_PATH="${DEPLOY_PATH:-/opt/studentbuddy}"
PM2_APP_NAME="${PM2_APP_NAME:-student-buddy}"

# Локальные проверки
LOCAL_CHECKS=true
CREATE_BACKUP=true
RUN_TESTS=false

# ================================
# Баннер
# ================================

echo ""
echo "=========================================="
echo "🚀 StudentBuddy Deployment Script v2.0.0"
echo "=========================================="
echo ""
info "Сервер: $SERVER"
info "Путь: $REMOTE_PATH"
info "PM2 процесс: $PM2_APP_NAME"
echo ""

# ================================
# Режим "quick" — только парсер и рестарт
# ================================
if [ "${1:-}" = "quick" ]; then
    info "Режим quick: копируем только парсер (parse_web и др.), рестарт PM2"
    ssh $SERVER "mkdir -p $REMOTE_PATH/parser"
    scp -r parser/mosgortrans-master $SERVER:$REMOTE_PATH/parser/ || error "Ошибка копирования parser"
    success "Парсер скопирован"
    info "Перезапуск бота..."
    ssh $SERVER "cd $REMOTE_PATH && pm2 restart $PM2_APP_NAME --update-env && pm2 save"
    success "Готово. Логи: ssh $SERVER 'pm2 logs $PM2_APP_NAME'"
    exit 0
fi

# ================================
# 0. Каталог на сервере (для нового сервера)
# ================================

info "Проверка каталога на сервере..."
ssh $SERVER "mkdir -p $REMOTE_PATH" || error "Не удалось создать каталог на сервере"
echo ""

# ================================
# 1. Предварительные проверки
# ================================

if [ "$LOCAL_CHECKS" = true ]; then
    info "Запуск локальных проверок..."
    
    # Проверка наличия .env
    if [ ! -f .env ]; then
        error ".env файл не найден! Скопируй .env.example и заполни данные."
    fi
    
    # Проверка синтаксиса Python
    info "Проверка синтаксиса Python..."
    python3 -m py_compile bot.py config.py i18n.py cache_manager.py health_check.py \
        database/__init__.py database/db.py \
        handlers/*.py utils/*.py keyboards/*.py middlewares/*.py \
        timetable/*.py replacements/*.py || error "Ошибки синтаксиса в Python файлах"
    
    # Запуск health check
    info "Запуск health check..."
    python3 health_check.py || warning "Health check не прошёл (продолжаем)"
    
    success "Локальные проверки пройдены"
    echo ""
fi

# ================================
# 2. Резервное копирование на сервере
# ================================

if [ "$CREATE_BACKUP" = true ]; then
    info "Создание резервной копии на сервере..."
    
    ssh $SERVER "REMOTE_PATH='$REMOTE_PATH'; set -e;
cd \"\$REMOTE_PATH\" || { echo 'Каталог не найден'; exit 1; };
BACKUP_DIR=\"\$HOME/studentbuddy_backups\";
TIMESTAMP=\$(date +%Y%m%d_%H%M%S);
BACKUP_PATH=\"\$BACKUP_DIR/backup_\$TIMESTAMP\";
mkdir -p \"\$BACKUP_DIR\" \"\$BACKUP_PATH\";
if [ -f studentbuddy.db ]; then cp studentbuddy.db \"\$BACKUP_PATH/\"; echo '✅ БД скопирована'; fi;
if [ -f data/studentbuddy_data.pickle ]; then cp data/studentbuddy_data.pickle \"\$BACKUP_PATH/\"; echo '✅ Persistence скопирован'; fi;
if [ -f .env ]; then cp .env \"\$BACKUP_PATH/\"; echo '✅ .env скопирован'; fi;
find \"\$BACKUP_DIR\" -type d -name 'backup_*' -mtime +7 -exec rm -rf {} + 2>/dev/null || true;
echo \"✅ Резервная копия создана: \$BACKUP_PATH\";"
    
    success "Резервное копирование завершено"
    echo ""
fi

# ================================
# 3. Остановка бота
# ================================

info "Остановка текущего бота (если запущен)..."
ssh $SERVER "pm2 stop $PM2_APP_NAME 2>/dev/null || true"
echo ""

# ================================
# 4. Копирование файлов
# ================================

info "Копирование файлов на сервер..."

# Основные модули (корень проекта)
info "→ Основные модули..."
scp bot.py config.py i18n.py cache_manager.py health_check.py db_admin.py \
    $SERVER:$REMOTE_PATH/ || error "Ошибка копирования основных модулей"

# Пакеты: database, utils, keyboards, middlewares
info "→ database, utils, keyboards, middlewares..."
scp -r database utils keyboards middlewares \
    $SERVER:$REMOTE_PATH/ || error "Ошибка копирования database/utils/keyboards/middlewares"

# Handlers
info "→ Handlers..."
scp handlers/__init__.py handlers/start.py handlers/menu.py handlers/reminders.py \
    handlers/settings.py handlers/schedule.py handlers/errors.py handlers/buses.py \
    $SERVER:$REMOTE_PATH/handlers/ || error "Ошибка копирования handlers"

# Парсер автобусов (меню «Автобусы»)
info "→ Парсер автобусов (mosgortrans)..."
ssh $SERVER "mkdir -p $REMOTE_PATH/parser"
scp -r parser/mosgortrans-master $SERVER:$REMOTE_PATH/parser/ || error "Ошибка копирования parser/mosgortrans-master"

# API модули
info "→ API модули..."
scp timetable/__init__.py timetable/api.py $SERVER:$REMOTE_PATH/timetable/ || error "Ошибка копирования timetable"
scp replacements/__init__.py replacements/api.py $SERVER:$REMOTE_PATH/replacements/ || error "Ошибка копирования replacements"

# Локализация
info "→ Файлы переводов..."
scp -r locales $SERVER:$REMOTE_PATH/ || error "Ошибка копирования locales"

# Конфигурационные файлы
info "→ Конфигурация..."
scp requirements.txt .gitignore .env.example $SERVER:$REMOTE_PATH/ || error "Ошибка копирования конфигурации"

# .env отдельно — чтобы точно подхватился актуальный (не перезаписанный из кэша)
if [ ! -f .env ]; then
    warning "Файл .env не найден локально — на сервере останется старый. Создай .env с BOT_TOKEN и SCHEDULE_API_TOKEN."
else
    info "→ Копирование .env на сервер..."
    scp .env $SERVER:$REMOTE_PATH/.env || error "Ошибка копирования .env"
    success ".env скопирован"
fi

success "Файлы скопированы"
echo ""

# ================================
# 5. Установка зависимостей
# ================================

info "Установка/обновление зависимостей..."
ssh $SERVER << ENDSSH
cd $REMOTE_PATH
source venv/bin/activate 2>/dev/null || python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip > /dev/null
pip install -r requirements.txt --upgrade > /dev/null
# Playwright: браузер для парсера автобусов (Яндекс.Карты)
if python3 -c "import playwright" 2>/dev/null; then
    playwright install chromium 2>/dev/null || true
    playwright install-deps chromium 2>/dev/null || true
fi
echo "✅ Зависимости установлены"
ENDSSH

success "Зависимости обновлены"
echo ""

# ================================
# 6. Очистка кэша
# ================================

info "Очистка кэша..."
ssh $SERVER << ENDSSH
cd $REMOTE_PATH
rm -rf __pycache__ database/__pycache__ handlers/__pycache__ utils/__pycache__ keyboards/__pycache__ middlewares/__pycache__ timetable/__pycache__ replacements/__pycache__
find . -name "*.pyc" -delete
echo "✅ Кэш очищен"
ENDSSH

success "Кэш очищен"
echo ""

# ================================
# 7. Health check перед запуском
# ================================

info "Запуск health check на сервере..."
ssh $SERVER << ENDSSH
cd $REMOTE_PATH
source venv/bin/activate
python3 health_check.py
if [ \$? -eq 0 ]; then
    echo "✅ Health check пройден"
else
    echo "⚠️ Health check показал предупреждения (продолжаем)"
fi
ENDSSH

echo ""

# ================================
# 8. Запуск бота
# ================================

info "Запуск бота..."
ssh $SERVER << ENDSSH
cd $REMOTE_PATH
source venv/bin/activate

# Проверяем, запущен ли уже процесс
if pm2 describe $PM2_APP_NAME > /dev/null 2>&1; then
    echo "🔄 Перезапуск существующего процесса..."
    pm2 restart $PM2_APP_NAME --update-env
else
    echo "🆕 Создание нового процесса PM2..."
    pm2 start bot.py --name $PM2_APP_NAME --interpreter venv/bin/python3 --time
fi

pm2 save
echo "✅ Бот запущен/перезапущен"
ENDSSH

success "Бот запущен!"
echo ""

# ================================
# 9. Проверка статуса
# ================================

info "Проверка статуса..."
ssh $SERVER "pm2 list"
echo ""

info "Последние логи:"
ssh $SERVER "pm2 logs $PM2_APP_NAME --lines 20 --nostream" || true
echo ""

# ================================
# Финал
# ================================

echo "=========================================="
success "🎉 Деплой успешно завершён!"
echo "=========================================="
echo ""
echo "📊 Полезные команды:"
echo "   Логи:    ssh $SERVER 'pm2 logs $PM2_APP_NAME'"
echo "   Статус:  ssh $SERVER 'pm2 status'"
echo "   Стоп:    ssh $SERVER 'pm2 stop $PM2_APP_NAME'"
echo "   Рестарт: ssh $SERVER 'pm2 restart $PM2_APP_NAME'"
echo "   Мониторинг: ssh $SERVER 'pm2 monit'"
echo ""
