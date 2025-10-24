# 🤖 AI-агент для анализа кредитного портфеля NCL

Интеллектуальный агент на основе **LangChain** и **OpenAI GPT** для работы с данными кредитной симуляции (2010-2015). Задавайте вопросы на русском языке - агент автоматически генерирует SQL и дает понятные ответы.

## 🚀 Быстрый старт

```bash
# 1. Установка зависимостей
cd ai_agent
pip install -r requirements.txt

# 2. Настройка API ключа
# Не коммитьте .env! Создайте на основе env.example
copy env.example .env   # Windows
cp env.example .env     # Linux/Mac
notepad .env            # затем заполните ключи

# 3. Запуск Streamlit веб-приложения (рекомендуется)
streamlit run app_streamlit_advanced.py
# Откроется в браузере: http://localhost:8501

# Или CLI
python cli.py
```

## 💡 Примеры вопросов

```
Сколько кредитов в базе данных?
Какая доля портфеля в просрочке 30+ дней?
Покажи топ-5 месяцев по объему выдач
Динамика PAR30 по месяцам в 2014-2015
Как ставка ЦБ влияла на выдачи?
IFRS9 stage mix на последнюю дату
```

## 🎨 Интерфейсы

### 1. Streamlit веб-приложение (рекомендуется)

**Базовая версия:**
```bash
streamlit run app_streamlit.py
```
- Чат с AI-агентом
- Примеры вопросов
- Статистика портфеля

**Расширенная версия:**
```bash
streamlit run app_streamlit_advanced.py
# Или: run_streamlit.bat (Windows) / ./run_streamlit.sh (Linux)
```
- 💬 Чат с AI-агентом
- 📊 Интерактивные графики (выдачи, PAR, DPD)
- 🔧 SQL песочница
- 📜 История запросов

### 2. CLI интерфейс

```bash
python cli.py
# Или: run.bat (Windows) / ./run.sh (Linux)
```

**Команды:**
- `/help` - список команд
- `/examples` - примеры вопросов
- `/stats` - статистика БД
- `/sql SELECT ...` - прямой SQL
- `/save` - сохранить ответ
- `/history` - история сессии

### 3. Пакетная обработка

```bash
# Создать шаблон с вопросами
python batch.py --create-template

# Обработать вопросы из файла
python batch.py --input questions.txt

# Результаты в reports/ (HTML, JSON, CSV)
```

### 4. Программный доступ

```python
from ai_agent import CreditSimulationAgent
from ai_agent.config import load_config

# Инициализация
config = load_config()
agent = CreditSimulationAgent(config)

# Задать вопрос
result = agent.query("Сколько кредитов в базе?")
if result["success"]:
    print(result["answer"])

# Прямой SQL
data = agent.run_raw_sql("SELECT COUNT(*) FROM loan_issue")
print(data)
```

## ⚙️ Конфигурация

Настройки в файле `.env` (создайте из `env.example`):

```env
# OpenAI настройки
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_TEMPERATURE=0.1
OPENAI_MAX_TOKENS=1000

# База данных
DB_PATH=../credit_sim.db

# Логирование
LOG_LEVEL=INFO
LOG_FILE=logs/agent.log
HISTORY_FILE=logs/agent_history.jsonl
```

## 📊 Возможности

### Типы анализа:
- **Общая статистика** - количество, объемы, средние чеки
- **Риск-метрики** - PAR30/60/90, DPD distribution, Cure/Default rates
- **IFRS9 Stage Mix** - Stage 1/2/3 анализ и динамика
- **Vintage Analysis** - когортный анализ по месяцам выдачи
- **Макроэкономика** - влияние ставки ЦБ, безработицы, сезонности
- **Анализ платежей** - Actual vs Scheduled, досрочные погашения

### Streamlit графики:
- 📈 Динамика выдач (bar chart)
- 📉 Количество кредитов (line chart)  
- 🎯 Распределение по DPD (pie charts)
- ⚠️ PAR30/60/90 динамика (multi-line)
- 💰 Ключевые метрики (metric cards)

## 🏗️ Архитектура

```
ai_agent/
├── config.py               # Конфигурация (Pydantic)
├── agent.py                # LangChain SQL Agent
├── cli.py                  # CLI интерфейс
├── app_streamlit.py        # Streamlit базовый
├── app_streamlit_advanced.py  # Streamlit расширенный
├── batch.py                # Пакетная обработка
├── examples.py             # Примеры использования
├── requirements.txt        # Зависимости
└── .env                    # API ключи (не в git)
```

**Интеграция с NCL:**
- **Dash** (порт 8050) → Статическая аналитика, отчеты
- **Streamlit** (порт 8501) → Динамический AI-анализ, NLP-запросы
- **Общая БД** → `credit_sim.db`

## 🔧 Технологии

- **LangChain 0.1.0** - фреймворк для LLM приложений
- **OpenAI GPT-3.5/4** - языковая модель
- **Streamlit 1.29.0** - веб-интерфейс
- **SQLAlchemy 2.0** - работа с БД
- **Plotly** - интерактивные графики
- **Pydantic** - валидация конфигурации

## 🐛 Troubleshooting

### Ошибка: "OPENAI_API_KEY not found"
```bash
# Проверьте .env файл
cat .env  # Linux/Mac
type .env # Windows

# Убедитесь что есть: OPENAI_API_KEY=sk-...
```

### Ошибка: "База данных не найдена"
```bash
# Сгенерируйте данные:
cd ..
python -m credit_simulation.src.main
python -m credit_simulation.src.module2_simulator
```

### Ошибка: "Module not found"
```bash
pip install -r requirements.txt --force-reinstall
```

### Streamlit порт занят
```bash
streamlit run app_streamlit.py --server.port 8502
```

## 📝 Примеры работы

**Простой вопрос:**
```
❓ Сколько кредитов в базе?

💡 В базе данных содержится 50,432 кредита,
   выданных с 2010-01-01 по 2015-12-31.
```

**Риск-анализ:**
```
❓ Какая доля портфеля в просрочке 30+ дней?

💡 PAR30 на декабрь 2015 составляет 8.3%.
   Это означает, что 8.3% от общего остатка 
   основного долга находится в просрочке более 30 дней.
```

**Макроэкономика:**
```
❓ Как ставка ЦБ влияла на объем выдач в 2014-2015?

💡 При росте ключевой ставки ЦБ с 5.5% до 17%
   (декабрь 2013 - декабрь 2014), объем выдач
   сократился на 34%. Корреляция: -0.72
   (сильная обратная связь).
```

## 📁 Структура данных

Агент работает с 3 таблицами SQLite:

**1. loan_issue** - Выдачи кредитов
- loan_id, issue_date, loan_amount, interest_rate
- term_months, product_type
- macro_rate_cbr, macro_employment_rate
- season_k_issue, season_k_amount

**2. credit_fact_history** - Операционный факт
- loan_id, period_month, MOB
- balance_principal, overdue_principal
- scheduled_payment, actual_payment
- DPD_bucket, status

**3. macro_params_log** - Макропараметры
- year_month, rate_cbr
- employment_rate, unemployment_rate
- macro_index

## 🔐 Безопасность

- ✅ API ключи в `.env` (не коммитятся в git)
- ✅ Только SELECT запросы (LangChain ограничение)
- ✅ Валидация всех входных данных (Pydantic)
- ✅ Логирование всех действий

Дополнительно:
- Используйте переменные окружения в CI/CD вместо явных ключей.
- Проверяйте `git status` перед пушем, чтобы исключить `.env`, `logs/`, `outputs/`.

## 🖼️ Галерея

| Выдачи | PAR/DPD | Vintages |
|---|---|---|
| ![Issuance](../docs/img/issuance.png) | ![PAR](../docs/img/par.png) | ![Vintages](../docs/img/vintages.png) |

## 📦 Зависимости

```txt
langchain==0.1.0
langchain-openai==0.0.2
openai==1.7.2
streamlit==1.29.0
sqlalchemy==2.0.32
plotly==5.18.0
pandas==2.0.3
pydantic==2.5.0
```

## 🎯 Итого

**Создано:** 7 модулей Python + веб-интерфейсы  
**Интерфейсы:** Streamlit (2 версии) + CLI + Batch + API  
**Функции:** Natural Language → SQL → Business Insights  
**Статус:** ✅ Готово к использованию

---

**Вопросы?** Запустите `python examples.py` для интерактивных примеров.
