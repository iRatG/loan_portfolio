#!/bin/bash
# Запуск Streamlit приложения AI-агента

echo "========================================"
echo "  Streamlit AI-агент NCL"
echo "========================================"
echo

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python не найден!"
    exit 1
fi

# Проверка БД
if [ ! -f "../credit_sim.db" ]; then
    echo "Ошибка: База данных не найдена!"
    exit 1
fi

# Создание директорий
mkdir -p logs outputs

echo "Выберите версию приложения:"
echo "  1. Базовая (чат)"
echo "  2. Расширенная (чат + аналитика + SQL)"
echo
read -p "Ваш выбор (1/2): " choice

if [ "$choice" = "1" ]; then
    echo
    echo "Запуск базовой версии..."
    streamlit run app_streamlit.py
elif [ "$choice" = "2" ]; then
    echo
    echo "Запуск расширенной версии..."
    streamlit run app_streamlit_advanced.py
else
    echo "Неверный выбор!"
    exit 1
fi

