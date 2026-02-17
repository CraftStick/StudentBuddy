#!/bin/bash
# Скрипт деплоя StudentBuddy на сервер

echo "🚀 Начинаю деплой StudentBuddy..."

SERVER="root@144.31.212.99"
REMOTE_PATH="/root/StudentBuddy"

echo "📦 Копирую основные файлы..."
scp bot.py database.py i18n.py user_helpers.py keyboards.py formatters.py .gitignore config.py $SERVER:$REMOTE_PATH/

echo "📦 Копирую handlers..."
scp handlers/__init__.py handlers/start.py handlers/menu.py handlers/reminders.py handlers/settings.py handlers/schedule.py handlers/errors.py $SERVER:$REMOTE_PATH/handlers/

echo "📦 Копирую локализацию..."
scp -r locales $SERVER:$REMOTE_PATH/

echo "🧹 Очистка на сервере..."
ssh $SERVER << 'EOF'
cd /root/StudentBuddy
rm -rf groups/ studentbuddy_data.pickle migrate_to_db.py test_database.py
rm -rf __pycache__ handlers/__pycache__ buildings/__pycache__ timetable/__pycache__ replacements/__pycache__
find . -name "*.pyc" -delete
echo "✅ Очистка завершена"
EOF

echo "🔄 Перезапуск бота..."
ssh $SERVER << 'EOF'
cd /root/StudentBuddy
pm2 restart student-buddy
echo "✅ Бот перезапущен"
EOF

echo "📊 Проверка статуса..."
ssh $SERVER "pm2 list"

echo ""
echo "🎉 Деплой завершён!"
echo "📋 Проверь логи: ssh root@144.31.212.99 'pm2 logs student-buddy --lines 30'"
