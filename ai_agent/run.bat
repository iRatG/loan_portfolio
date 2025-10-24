@echo off
REM Скрипт запуска AI-агента NCL

echo ========================================
echo   AI-агент для анализа кредитного портфеля NCL
echo ========================================
echo.

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Ошибка: Python не найден!
    echo Установите Python 3.8+ и добавьте в PATH
    pause
    exit /b 1
)

REM Проверка наличия БД
if not exist "..\credit_sim.db" (
    echo Ошибка: База данных не найдена!
    echo.
    echo Сначала сгенерируйте данные:
    echo   1. python -m credit_simulation.src.main
    echo   2. python -m credit_simulation.src.module2_simulator
    echo.
    pause
    exit /b 1
)

REM Проверка наличия .env
if not exist ".env" (
    echo Предупреждение: Файл .env не найден!
    echo Создайте .env файл с вашим OPENAI_API_KEY
    echo.
    pause
)

REM Создание директорий
if not exist "logs" mkdir logs
if not exist "outputs" mkdir outputs
if not exist "reports" mkdir reports

REM Запуск CLI
echo Запуск интерактивного режима...
echo.
python cli.py %*

pause

