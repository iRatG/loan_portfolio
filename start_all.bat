@echo off
REM Запуск всей платформы NCL Analytics

echo ========================================
echo   NCL Analytics Platform
echo ========================================
echo.
echo Запускаем все компоненты...
echo.

REM Проверка БД
if not exist "credit_sim.db" (
    echo Ошибка: База данных не найдена!
    echo Сначала сгенерируйте данные.
    pause
    exit /b 1
)

REM Запуск лендинга (порт 8000)
start "NCL Landing" cmd /k "cd landing && python server.py"
timeout /t 2 /nobreak >nul

REM Запуск Dash (порт 8050)
start "NCL Dash Dashboard" cmd /k "python -m credit_simulation.src.dashboard_app --conn sqlite:///credit_sim.db --port 8050"
timeout /t 3 /nobreak >nul

REM Запуск Streamlit (порт 8501)
start "NCL AI Agent" cmd /k "cd ai_agent && streamlit run app_streamlit_advanced.py"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Все компоненты запущены!
echo ========================================
echo.
echo Откройте в браузере:
echo   🏠 Главная:    http://localhost:8000
echo   📊 Дашборд:    http://localhost:8050
echo   🤖 AI-агент:   http://localhost:8501
echo.
echo Для остановки закройте все окна или нажмите Ctrl+C
pause

