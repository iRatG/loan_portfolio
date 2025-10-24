# NCL Risk Simulation & Analytics (2010–2015)

Бизнес‑ориентированный прототип симуляции кредитного портфеля и риск‑аналитики с дашбордом. Период данных: 2010–2015.

## Запуск

1) Установка зависимостей
```
pip install -r credit_simulation/requirements.txt
```

2) Генерация выдач (Модуль 1)
```
python -m credit_simulation.src.main
```

3) Эмуляция операционного факта (Модуль 2)
```
python -m credit_simulation.src.module2_simulator
```

4) Риск‑аналитика (CSV/PNG/HTML)
```
python -m credit_simulation.src.analysis_risk_module2 --conn "sqlite:///credit_sim.db" --outdir logs --plots --plotly --start 2010-01 --end 2015-12
```

5) Дашборд (read‑only)
```
python -m credit_simulation.src.dashboard_app --conn "sqlite:///credit_sim.db" --host 127.0.0.1 --port 8050
```

## Архитектура
- `credit_simulation/src/generators` – выдачи, макро/сезонность
- `credit_simulation/src/module2_simulator.py` – операционный факт (аннуитет, DPD‑эйджинг, cure/default)
- `credit_simulation/src/analysis_*.py` – аналитика (DPD, PAR, IFRS9, Cure/Default, Vintages)
- `credit_simulation/src/dashboard_app.py` – дашборд (Dash/Plotly)
- `credit_simulation/sql` – DDL SQL (таблицы)
- `credit_simulation/config/config.toml` – конфигурация + `[descriptions]` (пояснения к параметрам)

Слои (цель рефакторинга):
- Domain: Engines (Schedule/Delinquency/Cure), Models (Loan/Fact)
- Infrastructure: Repositories (loan_issue, credit_fact_history), Migrations
- Application: Simulator Orchestrator, Analytics, Dashboard

## Конфигурация
- `[simulation]` – период, базовая интенсивность выдач
- `[loan_parameters]` – суммы/сроки
- `[sensitivity]` – чувствительности к макро
- `[database]` – строка подключения
- `[collections]` – DPD‑правила, cure и политика оплаты по бакетам
- `[descriptions]` – описания параметров (читаются в дашборде)

## Метрики (для бизнеса)
- DPD: доли 0/1–30/31–60/61–90/90+
- PAR30/60/90 (по балансу)
- IFRS9 Stage mix (proxy)
- Cure rate / Default rate
- Payments: Actual/Scheduled
- Vintages: PD 12m
- Issuance: объёмы/количество/средний чек/ставка

## Качество кода и настройки
- Настройки валидируются Pydantic‑моделью (`credit_simulation/src/utils/settings.py`).
- DDL вынесен в SQL (`sql/create_tables.sql`, `sql/create_fact_tables.sql`).
- Докстринги — Google style.

## Тесты (план)
- Аннуитет/аллокация
- DPD‑эйджинг и cure
- Roll‑rate, PAR, Stage mix
