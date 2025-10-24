#!/bin/bash
# Скрипт запуска AI-агента NCL

echo "========================================"
echo "  AI-агент для анализа кредитного портфеля NCL"
echo "========================================"
echo

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python не найден!"
    echo "Установите Python 3.8+"
    exit 1
fi

# Проверка наличия БД
if [ ! -f "../credit_sim.db" ]; then
    echo "Ошибка: База данных не найдена!"
    echo
    echo "Сначала сгенерируйте данные:"
    echo "  1. python -m credit_simulation.src.main"
    echo "  2. python -m credit_simulation.src.module2_simulator"
    echo
    exit 1
fi

# Проверка наличия .env
if [ ! -f ".env" ]; then
    echo "Предупреждение: Файл .env не найден!"
    echo "Создайте .env файл с вашим OPENAI_API_KEY"
    echo
fi

# Создание директорий
mkdir -p logs outputs reports

# Запуск CLI
echo "Запуск интерактивного режима..."
echo
python3 cli.py "$@"

