# Multi-stage build для минимизации размера образа
FROM python:3.12-slim AS builder

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создание виртуального окружения
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ================================
# Production stage
# ================================
FROM python:3.12-slim

# Метаданные
LABEL maintainer="StudentBuddy Team"
LABEL description="Telegram bot для расписания колледжа"
LABEL version="1.0.0"

# Создание пользователя для безопасности (не root!)
RUN useradd -m -u 1000 -s /bin/bash botuser

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Копирование виртуального окружения из builder
COPY --from=builder /opt/venv /opt/venv

# Настройка переменных окружения
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Moscow

# Рабочая директория
WORKDIR /app

# Копирование кода приложения
COPY --chown=botuser:botuser . .

# Создание директорий для данных
RUN mkdir -p /app/data /app/logs && \
    chown -R botuser:botuser /app

# Переключение на непривилегированного пользователя
USER botuser

# Volume для данных (БД, persistence, логи)
VOLUME ["/app/data", "/app/logs"]

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 health_check.py || exit 1

# Запуск бота
CMD ["python3", "bot.py"]
