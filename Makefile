.PHONY: help install dev run test clean health backup docker-build docker-run docker-stop

# Цвета для вывода
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m

help: ## Показать эту справку
	@echo "$(BLUE)StudentBuddy - Доступные команды:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'
	@echo ""

install: ## Установить зависимости
	@echo "$(BLUE)📦 Установка зависимостей...$(NC)"
	python3 -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	@echo "$(GREEN)✅ Зависимости установлены$(NC)"

dev: ## Запустить в режиме разработки (DEBUG)
	@echo "$(BLUE)🔧 Запуск в режиме разработки...$(NC)"
	export LOG_LEVEL=DEBUG && . venv/bin/activate && python3 bot.py

run: ## Запустить бота
	@echo "$(BLUE)🚀 Запуск бота...$(NC)"
	. venv/bin/activate && python3 bot.py

test: ## Запустить тесты и проверки
	@echo "$(BLUE)🧪 Запуск проверок...$(NC)"
	. venv/bin/activate && python3 -m py_compile bot.py database.py handlers/*.py
	. venv/bin/activate && python3 health_check.py
	@echo "$(GREEN)✅ Проверки пройдены$(NC)"

health: ## Запустить health check
	@echo "$(BLUE)🏥 Health check...$(NC)"
	. venv/bin/activate && python3 health_check.py

backup: ## Создать резервную копию БД
	@echo "$(BLUE)💾 Создание бэкапа...$(NC)"
	. venv/bin/activate && python3 db_admin.py backup
	@echo "$(GREEN)✅ Бэкап создан$(NC)"

stats: ## Показать статистику БД
	@echo "$(BLUE)📊 Статистика базы данных:$(NC)"
	. venv/bin/activate && python3 db_admin.py stats

clean: ## Очистить временные файлы
	@echo "$(BLUE)🧹 Очистка...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete
	@echo "$(GREEN)✅ Очистка завершена$(NC)"

docker-build: ## Собрать Docker образ
	@echo "$(BLUE)🐳 Сборка Docker образа...$(NC)"
	docker build -t studentbuddy:latest .
	@echo "$(GREEN)✅ Образ собран$(NC)"

docker-run: ## Запустить через Docker Compose
	@echo "$(BLUE)🐳 Запуск через Docker...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✅ Контейнер запущен$(NC)"
	docker-compose ps

docker-stop: ## Остановить Docker контейнеры
	@echo "$(BLUE)🐳 Остановка контейнеров...$(NC)"
	docker-compose down
	@echo "$(GREEN)✅ Контейнеры остановлены$(NC)"

docker-logs: ## Показать логи Docker
	docker-compose logs -f

lint: ## Проверить код линтером (если установлен)
	@echo "$(BLUE)🔍 Проверка кода...$(NC)"
	-. venv/bin/activate && python3 -m pylint bot.py database.py --disable=C,R,W || true

format: ## Форматировать код (если установлен black)
	@echo "$(BLUE)✨ Форматирование кода...$(NC)"
	-. venv/bin/activate && python3 -m black bot.py database.py handlers/ || true

setup: install ## Полная настройка проекта
	@echo "$(BLUE)⚙️  Настройка проекта...$(NC)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(YELLOW)⚠️  Создан .env из .env.example. ЗАПОЛНИ ТОКЕНЫ!$(NC)"; \
	fi
	@echo "$(GREEN)✅ Проект настроен. Заполни .env и запусти: make run$(NC)"
