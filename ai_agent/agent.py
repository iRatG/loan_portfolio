"""
Основной модуль AI-агента для работы с данными кредитной симуляции.
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain.agents import AgentType
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from sqlalchemy import create_engine, text

from config import AgentConfig
from logging_utils import log_agent_interaction, log_sql_event


class CreditSimulationAgent:
    """
    AI-агент для анализа данных кредитной симуляции.
    
    Использует LangChain SQL Agent для ответов на вопросы о кредитном портфеле.
    
    Attributes:
        config: Конфигурация агента
        logger: Логгер
        db: SQLDatabase объект LangChain
        llm: Языковая модель (OpenAI или Anthropic)
        agent: SQL-агент LangChain
    """
    
    # Детальное описание структуры БД и бизнес-контекста
    DB_CONTEXT = """
    # Структура базы данных NCL Credit Simulation
    
    ## Таблицы:
    
    ### 1. loan_issue - Выдачи кредитов (Модуль 1)
    Основная таблица с информацией о выданных кредитах.
    
    Поля:
    - loan_id: Уникальный ID кредита (PRIMARY KEY)
    - issue_date: Дата выдачи (формат: YYYY-MM-DD)
    - cohort_month: Месяц когорты для vintage-анализа (YYYY-MM-01)
    - loan_amount: Сумма кредита в рублях
    - interest_rate: Годовая процентная ставка (%)
    - term_months: Срок кредита в месяцах
    - product_type: Тип продукта (consumer_loan, auto_loan, mortgage и т.д.)
    
    Макроэкономические параметры на момент выдачи:
    - macro_rate_cbr: Ключевая ставка ЦБ РФ (%)
    - macro_employment_rate: Уровень занятости (%)
    - macro_unemployment_rate: Уровень безработицы (%)
    - macro_index: Макроэкономический индекс
    
    Сезонные параметры:
    - season_k_issue: Сезонный коэффициент для интенсивности выдач
    - season_k_amount: Сезонный коэффициент для суммы выдач
    - season_period_name: Название сезонного периода
    
    Технические поля:
    - created_at: Timestamp создания записи
    - batch_id: ID батча генерации данных
    
    ### 2. credit_fact_history - Операционный факт (Модуль 2)
    История платежей и состояния кредитов по месяцам.
    
    Поля:
    - loan_id: ID кредита (FK -> loan_issue)
    - period_month: Отчетный месяц (YYYY-MM-01)
    - MOB: Months On Book - месяцев на балансе с момента выдачи
    
    Балансы:
    - balance_principal: Остаток основного долга
    - overdue_principal: Просроченный основной долг
    - interest_scheduled: Запланированные проценты
    - overdue_interest: Просроченные проценты
    
    Платежи:
    - scheduled_payment: Плановый платеж (аннуитет)
    - actual_payment: Фактически оплаченная сумма
    
    Просрочка (DPD - Days Past Due):
    - DPD_bucket: Корзина просрочки ('0', '1-30', '31-60', '61-90', '90+')
    - overdue_days: Точное количество дней просрочки
    
    Статусы:
    - status: Текущий статус (Active, Closed, Default)
    - migration_scenario: Сценарий миграции между бакетами (cure/default)
    
    Технические:
    - created_at: Timestamp
    - batch_id: ID батча
    
    ### 3. macro_params_log - Лог макроэкономических параметров
    История макропоказателей по месяцам.
    
    Поля:
    - year_month: Месяц (YYYY-MM-01)
    - rate_cbr: Ключевая ставка ЦБ РФ
    - employment_rate: Уровень занятости
    - unemployment_rate: Уровень безработицы
    - macro_index: Макроэкономический индекс
    - k_macro_calculated: Расчетный макро-коэффициент
    - source: Источник данных
    
    ## Бизнес-метрики и концепции:
    
    ### DPD Buckets (Корзины просрочки):
    - '0': Нет просрочки (current)
    - '1-30': Техническая просрочка (1-30 дней)
    - '31-60': Средняя просрочка (31-60 дней)
    - '61-90': Серьезная просрочка (61-90 дней)
    - '90+': Критическая просрочка (более 90 дней)
    
    ### PAR (Portfolio At Risk) - Портфель под риском:
    - PAR30: Доля портфеля (по балансу) с DPD >= 30 дней
    - PAR60: Доля портфеля с DPD >= 60 дней
    - PAR90: Доля портфеля с DPD >= 90 дней
    
    Формула PAR30:
    ```sql
    SUM(CASE WHEN DPD_bucket IN ('31-60', '61-90', '90+') THEN balance_principal ELSE 0 END) / 
    SUM(balance_principal)
    ```
    
    ### IFRS9 Stage Mix (упрощенная прокси-модель):
    - Stage 1: Performing (DPD = '0')
    - Stage 2: Underperforming (DPD IN ('1-30', '31-60'))
    - Stage 3: Non-performing (DPD IN ('61-90', '90+'))
    
    ### Cure Rate (Коэффициент оздоровления):
    Процент кредитов, которые улучшили свой DPD bucket (например, с '1-30' на '0')
    
    ### Default Rate (Коэффициент дефолта):
    Процент кредитов, которые перешли в статус 'Default'
    
    ### Roll Rate (Коэффициент перетока):
    Процент кредитов, которые переходят из одного DPD bucket в следующий (хуже)
    
    ### Vintage Analysis (Когортный анализ):
    Анализ поведения кредитов, выданных в определенный месяц (cohort_month)
    Позволяет сравнить качество разных когорт.
    
    ### MOB (Months On Book):
    Количество месяцев с момента выдачи кредита.
    MOB = 0 - месяц выдачи
    MOB = 1 - первый месяц после выдачи
    и т.д.
    
    ## Период данных:
    2010-01-01 до 2015-12-31 (включая кризис 2014-2015)
    
    ## Важные SQL-паттерны:
    
    ### Группировка по месяцам:
    ```sql
    -- Вариант 1: substr
    SELECT substr(issue_date, 1, 7) as month, COUNT(*) 
    FROM loan_issue 
    GROUP BY month;
    
    -- Вариант 2: strftime
    SELECT strftime('%Y-%m', issue_date) as month, COUNT(*) 
    FROM loan_issue 
    GROUP BY month;
    ```
    
    ### JOIN таблиц:
    ```sql
    SELECT 
        li.loan_id,
        li.issue_date,
        cfh.period_month,
        cfh.DPD_bucket
    FROM loan_issue li
    JOIN credit_fact_history cfh ON li.loan_id = cfh.loan_id
    WHERE li.issue_date >= '2010-01-01';
    ```
    
    ### Расчет PAR30:
    ```sql
    SELECT 
        period_month,
        ROUND(100.0 * 
            SUM(CASE WHEN DPD_bucket IN ('31-60', '61-90', '90+') 
                THEN balance_principal ELSE 0 END) / 
            NULLIF(SUM(balance_principal), 0), 2
        ) as PAR30_pct
    FROM credit_fact_history
    WHERE status = 'Active'
    GROUP BY period_month
    ORDER BY period_month;
    ```
    
    ## Рекомендации по запросам:
    1. Всегда проверяй схему таблицы перед запросом
    2. Используй ROUND(..., 2) для процентов и денежных сумм
    3. Для дат используй формат ISO: YYYY-MM-DD
    4. Помни про NULL значения - используй NULLIF и COALESCE
    5. Для топ-N используй ORDER BY + LIMIT
    6. Фильтруй только Active кредиты для актуальных метрик
    """
    
    def __init__(self, config: AgentConfig):
        """
        Инициализация агента.
        
        Args:
            config: Объект конфигурации AgentConfig
        """
        self.config = config
        self.logger = config.setup_logging()
        
        self.logger.info(f"Инициализация AI-агента (provider={config.llm_provider})")
        
        # Проверка существования БД
        if not Path(config.db_path).exists():
            raise FileNotFoundError(f"База данных не найдена: {config.db_path}")
        
        # Создание подключения к БД
        db_uri = f"sqlite:///{config.db_path}"
        self.engine = create_engine(db_uri, echo=config.verbose)
        self.db = SQLDatabase(self.engine)
        
        self.logger.info(f"Подключение к БД: {config.db_path}")
        
        # Инициализация LLM
        self._init_llm()
        
        # Создание SQL-агента
        self._create_agent()
        
        self.logger.info("AI-агент успешно инициализирован")
    
    def _init_llm(self):
        """Инициализировать языковую модель."""
        if self.config.llm_provider == "openai":
            self.logger.info(f"Инициализация OpenAI (model={self.config.openai_model})")
            self.llm = ChatOpenAI(
                model=self.config.openai_model,
                temperature=self.config.openai_temperature,
                max_tokens=self.config.openai_max_tokens,
                api_key=self.config.get_api_key()
            )
        elif self.config.llm_provider == "anthropic":
            self.logger.info(f"Инициализация Anthropic (model={self.config.anthropic_model})")
            self.llm = ChatAnthropic(
                model=self.config.anthropic_model,
                temperature=self.config.openai_temperature,  # Используем ту же температуру
                api_key=self.config.get_api_key()
            )
        else:
            raise ValueError(f"Неизвестный провайдер: {self.config.llm_provider}")
    
    def _create_agent(self):
        """Создать SQL-агента."""
        # Создание toolkit
        self.toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        
        # Промпт с контекстом
        prefix = f"""
        Ты - эксперт по анализу данных кредитного портфеля банка NCL.
        У тебя есть доступ к базе данных с информацией о кредитах, выданных с 2010 по 2015 год.
        
        {self.DB_CONTEXT}
        
        Твоя задача:
        1. Понять вопрос пользователя о кредитном портфеле
        2. Составить корректный SQL-запрос к SQLite базе данных
        3. Проанализировать результаты
        4. Дать понятный ответ с бизнес-интерпретацией
        
        Важные правила:
        - ВСЕГДА проверяй схему таблиц перед запросом (используй инструмент sql_db_schema)
        - Используй правильные имена колонок (они указаны выше)
        - Для дат используй формат YYYY-MM-DD
        - Округляй числа до 2 знаков после запятой
        - Для процентов умножай на 100
        - Отвечай ТОЛЬКО на русском языке
        - Если не уверен в структуре - сначала проверь схему таблицы
        - Проверяй результаты на пустоту и NULL
        
        Примеры хороших ответов:
        - "В базе данных 50,432 кредита. Период: 2010-01-01 до 2015-12-31."
        - "PAR30 на декабрь 2015 составил 8.3%, что на 2.1% выше, чем год назад."
        - "Топ-3 месяца по выдачам: май 2013 (2.5 млрд руб), июнь 2013 (2.4 млрд), апрель 2013 (2.3 млрд)"
        
        Если запрос вернул пустой результат - сообщи об этом явно и предложи альтернативу.
        """
        
        suffix = """
        Начинаем! Помни порядок: 
        1. Проверь схему таблиц
        2. Составь SQL
        3. Выполни запрос
        4. Проанализируй результат
        5. Дай понятный ответ на русском языке
        
        Вопрос пользователя: {input}
        
        Ход рассуждений: {agent_scratchpad}
        """
        
        # Создание агента
        self.agent = create_sql_agent(
            llm=self.llm,
            toolkit=self.toolkit,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=self.config.verbose,
            prefix=prefix,
            suffix=suffix,
            max_iterations=15,
            max_execution_time=120,
            early_stopping_method="generate",
            handle_parsing_errors=True
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Задать вопрос агенту.
        
        Args:
            question: Вопрос на естественном языке
            
        Returns:
            Словарь с результатами:
            - success: bool - успешность выполнения
            - question: str - исходный вопрос
            - answer: str - ответ агента
            - error: Optional[str] - текст ошибки если была
        """
        self.logger.info(f"Получен вопрос: {question}")
        import time
        t0 = time.perf_counter()
        try:
            response = self.agent.invoke({"input": question})
            answer = response.get("output", "")
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.info(f"Ответ получен успешно (длина: {len(answer)} символов, {dt:.0f} ms)")
            # JSONL лог
            log_agent_interaction(
                self.config.history_file,
                question=question,
                success=True,
                answer=answer,
                latency_ms=dt,
            )
            return {
                "success": True,
                "question": question,
                "answer": answer,
                "error": None
            }
        except Exception as e:
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.error(f"Ошибка при обработке вопроса: {e}", exc_info=True)
            log_agent_interaction(
                self.config.history_file,
                question=question,
                success=False,
                error=str(e),
                latency_ms=dt,
            )
            return {
                "success": False,
                "question": question,
                "answer": None,
                "error": str(e)
            }
    
    def get_table_info(self, table_name: Optional[str] = None) -> str:
        """
        Получить информацию о таблицах базы данных.
        
        Args:
            table_name: Название конкретной таблицы (если None - все таблицы)
            
        Returns:
            Строка с описанием структуры таблиц
        """
        if table_name:
            return self.db.get_table_info_no_throw([table_name])
        return self.db.get_table_info()
    
    def run_raw_sql(self, sql: str) -> Any:
        """
        Выполнить сырой SQL-запрос (для отладки и прямых запросов).
        
        Args:
            sql: SQL-запрос
            
        Returns:
            Результат выполнения запроса
        """
        self.logger.debug(f"Выполнение raw SQL: {sql}")
        import time
        t0 = time.perf_counter()
        try:
            result = self.db.run(sql)
            rows = len(result) if result else 0
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.debug(f"SQL выполнен успешно, строк: {rows}, {dt:.0f} ms")
            log_sql_event(
                self.config.history_file,
                name="raw_sql",
                sql=sql,
                success=True,
                rowcount=rows,
                duration_ms=dt,
            )
            return result
        except Exception as e:
            dt = (time.perf_counter() - t0) * 1000.0
            self.logger.error(f"Ошибка выполнения SQL: {e}")
            log_sql_event(
                self.config.history_file,
                name="raw_sql",
                sql=sql,
                success=False,
                rowcount=0,
                duration_ms=dt,
                error=str(e),
            )
            raise
    
    def get_example_questions(self) -> List[str]:
        """
        Получить список примеров вопросов для агента.
        
        Returns:
            Список строк с примерами вопросов
        """
        return [
            # Общая статистика
            "Сколько всего кредитов в базе данных?",
            "Какой период данных в базе?",
            "Какой общий объем выдач в рублях?",
            "Какой средний размер кредита?",
            "Какая средняя процентная ставка?",
            
            # Анализ выдач
            "Покажи топ-5 месяцев по объему выдач",
            "Как менялся объем выдач по годам?",
            "Какая сезонность в выдачах по месяцам года?",
            "Какая динамика среднего чека по месяцам?",
            "Какая динамика процентных ставок по месяцам?",
            
            # Риск-метрики
            "Какая доля портфеля находится в просрочке 30+ дней?",
            "Покажи распределение кредитов по DPD бакетам",
            "Какая динамика PAR30 по месяцам?",
            "Какой PAR60 и PAR90 на последнюю дату?",
            "Сколько кредитов в дефолте?",
            
            # IFRS9
            "Покажи IFRS9 stage mix на последнюю дату",
            "Как менялся stage mix по месяцам в 2014-2015?",
            
            # Макроэкономика
            "Как менялась ставка ЦБ по годам?",
            "Какая корреляция между ставкой ЦБ и объемом выдач?",
            "Как влияла безработица на просрочку?",
            "Покажи макропоказатели в период кризиса 2014-2015",
            
            # Платежи
            "Какое соотношение фактических и плановых платежей?",
            "Сколько кредитов было закрыто досрочно?",
            "Какой средний фактический платеж по месяцам?",
            
            # Vintage analysis
            "Покажи vintage analysis для когорт 2010 года",
            "Какие когорты показали худшую просрочку?",
            "Какой средний MOB для дефолтных кредитов?",
            "Сравни качество когорт 2010 и 2014 годов",
            
            # Продукты
            "Какое распределение выдач по типам продуктов?",
            "Какой продукт показывает лучшее качество?",
            
            # Cure и Default rates
            "Какой cure rate за последний год?",
            "Какой default rate по когортам?",
            "Сколько кредитов вернулось из просрочки в current?"
        ]


if __name__ == "__main__":
    # Простой тест агента
    from config import load_config
    
    print("🔧 Тест AI-агента\n")
    
    try:
        # Загрузка конфигурации
        config = load_config()
        print(f"✅ Конфигурация загружена ({config.llm_provider})")
        
        # Создание агента
        agent = CreditSimulationAgent(config)
        print(f"✅ Агент создан\n")
        
        # Тестовый вопрос
        test_question = "Сколько всего кредитов в базе данных?"
        print(f"❓ Вопрос: {test_question}\n")
        
        result = agent.query(test_question)
        
        if result["success"]:
            print(f"💡 Ответ:\n{result['answer']}\n")
            print("✅ Тест пройден!")
        else:
            print(f"❌ Ошибка: {result['error']}")
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")

