# NCL Analytics Platform - PowerShell Launcher
# Запускает все компоненты платформы

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NCL Analytics Platform" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Запускаем все компоненты..." -ForegroundColor Yellow
Write-Host ""

# Проверка БД
if (-not (Test-Path "credit_sim.db")) {
    Write-Host "Ошибка: База данных не найдена!" -ForegroundColor Red
    Write-Host "Сначала сгенерируйте данные." -ForegroundColor Yellow
    pause
    exit 1
}

# Запуск лендинга (порт 8000)
Write-Host "[1/3] Запуск лендинга (порт 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\landing'; python server.py"
Start-Sleep -Seconds 2

# Запуск Dash (порт 8050)
Write-Host "[2/3] Запуск Dash дашборда (порт 8050)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; python -m credit_simulation.src.dashboard_app --conn 'sqlite:///credit_sim.db' --port 8050"
Start-Sleep -Seconds 3

# Запуск Streamlit (порт 8501)
Write-Host "[3/3] Запуск Streamlit AI-агента (порт 8501)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\ai_agent'; streamlit run app_streamlit_advanced.py"
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Все компоненты запущены!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Откройте в браузере:" -ForegroundColor Yellow
Write-Host "  🏠 Главная:    http://localhost:8000" -ForegroundColor White
Write-Host "  📊 Дашборд:    http://localhost:8050" -ForegroundColor White
Write-Host "  🤖 AI-агент:   http://localhost:8501" -ForegroundColor White
Write-Host ""
Write-Host "Для остановки закройте окна PowerShell" -ForegroundColor Gray
Write-Host ""

# Автоматически открыть главную страницу
Start-Sleep -Seconds 2
Start-Process "http://localhost:8000"

Write-Host "Нажмите любую клавишу для закрытия..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

