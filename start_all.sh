#!/bin/bash
# Запуск всей платформы NCL Analytics

echo "========================================"
echo "  NCL Analytics Platform"
echo "========================================"
echo
echo "Запускаем все компоненты..."
echo

# Проверка БД
if [ ! -f "credit_sim.db" ]; then
    echo "Ошибка: База данных не найдена!"
    echo "Сначала сгенерируйте данные."
    exit 1
fi

# Запуск в фоне
cd landing
python3 server.py &
LANDING_PID=$!
cd ..

sleep 2

python3 -m credit_simulation.src.dashboard_app --conn "sqlite:///credit_sim.db" --port 8050 &
DASH_PID=$!

sleep 3

cd ai_agent
streamlit run app_streamlit_advanced.py &
STREAMLIT_PID=$!
cd ..

sleep 3

echo
echo "========================================"
echo "  Все компоненты запущены!"
echo "========================================"
echo
echo "Откройте в браузере:"
echo "  🏠 Главная:    http://localhost:8000"
echo "  📊 Дашборд:    http://localhost:8050"
echo "  🤖 AI-агент:   http://localhost:8501"
echo
echo "Для остановки нажмите Ctrl+C"

# Функция остановки
cleanup() {
    echo
    echo "Останавливаем компоненты..."
    kill $LANDING_PID $DASH_PID $STREAMLIT_PID 2>/dev/null
    exit 0
}

trap cleanup INT

# Ждем
wait

