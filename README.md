# NCL Risk Simulation & Analytics (2010–2015)

Бизнес‑ориентированный прототип симуляции кредитного портфеля и риск‑аналитики с дашбордом. Период данных: 2010–2015.

## 🚀 Запуск платформы

### Быстрый старт (запустить всё)

```bash
# Windows PowerShell (рекомендуется)
.\start_all.ps1

# Windows CMD
.\start_all.bat

# Linux/Mac
chmod +x start_all.sh
./start_all.sh
```

Откроется **NCL Analytics Platform**:
- 🏠 **Главная** (http://localhost:8000) - лендинг с навигацией
- 📊 **Дашборд** (http://localhost:8050) - аналитика и отчетность
- 🤖 **AI-агент** (http://localhost:8501) - чат с GPT

### Скриншоты

| Главная | Дашборд | AI‑агент |
|---|---|---|
| (скрин) | (скрин) | (скрин) |

### Пошаговый запуск

1) **Установка зависимостей (единый requirements)**
```bash
pip install -r requirements.txt
```

2) **Генерация данных** (если еще не сделано)
```bash
python -m credit_simulation.src.main
python -m credit_simulation.src.module2_simulator
```

3) **Запуск компонентов по отдельности**

```bash
# Лендинг (порт 8000)
cd landing && python server.py

# Дашборд (порт 8050)
python -m credit_simulation.src.dashboard_app --conn "sqlite:///credit_sim.db" --port 8050

# AI-агент (порт 8501)
cd ai_agent && streamlit run app_streamlit_advanced.py
```

## 🤖 AI-агент для анализа данных

**Интеллектуальный агент на LangChain + OpenAI GPT** для работы с данными симуляции.

**Возможности:**
- 💬 Вопросы на русском → SQL → Понятные ответы
- 📊 Streamlit веб-интерфейс с графиками (Plotly)
- 🔧 CLI + пакетная обработка + программный API
- 📈 Анализ риск-метрик (PAR, DPD, IFRS9, Vintages)

**Быстрый старт:**
```bash
cd ai_agent
pip install -r requirements.txt

# Streamlit веб-приложение (рекомендуется)
streamlit run app_streamlit_advanced.py
# → http://localhost:8501

# Или CLI
python cli.py
```

**Примеры вопросов:**
- "Сколько кредитов в базе?"
- "Какая доля портфеля в просрочке 30+?"
- "Топ-5 месяцев по объему выдач"
- "Динамика PAR30 в 2014-2015"

Подробнее об AI‑агенте см. разделы выше в этом файле (единая документация).

> Примечание: API‑ключи и приватные файлы не коммитятся. См. раздел «Безопасность» ниже.

## Архитектура
- `credit_simulation/src/generators` – выдачи, макро/сезонность
- `credit_simulation/src/module2_simulator.py` – операционный факт (аннуитет, DPD‑эйджинг, cure/default)
- `credit_simulation/src/analysis_*.py` – аналитика (DPD, PAR, IFRS9, Cure/Default, Vintages)
- `credit_simulation/src/dashboard_app.py` – дашборд (Dash/Plotly)
- `credit_simulation/sql` – DDL SQL (таблицы)
- `credit_simulation/config/config.toml` – конфигурация + `[descriptions]` (пояснения к параметрам)
- `ai_agent/` – 🤖 AI-агент на LangChain + OpenAI GPT для NLP-запросов к данным

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

## 🔐 Безопасность и подготовка к Git

- Не коммитьте секреты: используйте `ai_agent/env.example` и создайте локально `ai_agent/.env`.
- В `.gitignore` добавлены логи, артефакты, локальные файлы.
- Файл ключей `.env` исключен из git; проверьте перед пушем: `git status`.
- Для обмена скриншотами используйте каталог `docs/img` (без данных и логов).
