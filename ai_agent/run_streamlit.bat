@echo off
REM Запуск Streamlit приложения AI-агента

echo ========================================
echo   Streamlit AI-агент NCL
echo ========================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Ошибка: Python не найден!
    pause
    exit /b 1
)

REM Проверка БД
if not exist "..\credit_sim.db" (
    echo Ошибка: База данных не найдена!
    pause
    exit /b 1
)

REM Создание директорий
if not exist "logs" mkdir logs
if not exist "outputs" mkdir outputs

echo Выберите версию приложения:
echo   1. Базовая (чат)
echo   2. Расширенная (чат + аналитика + SQL)
echo.
set /p choice="Ваш выбор (1/2): "

if "%choice%"=="1" (
    echo.
    echo Запуск базовой версии...
    streamlit run app_streamlit.py
) else if "%choice%"=="2" (
    echo.
    echo Запуск расширенной версии...
    streamlit run app_streamlit_advanced.py
) else (
    echo Неверный выбор!
    pause
    exit /b 1
)

