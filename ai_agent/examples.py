"""
Примеры программного использования AI-агента.

Этот файл демонстрирует различные способы работы с агентом
без использования CLI.
"""

from config import load_config, AgentConfig
from agent import CreditSimulationAgent


def example_basic():
    """Базовый пример использования."""
    print("=" * 80)
    print("ПРИМЕР 1: Базовое использование")
    print("=" * 80 + "\n")
    
    # Загрузка конфигурации из .env
    config = load_config()
    
    # Создание агента
    agent = CreditSimulationAgent(config)
    
    # Задать вопрос
    result = agent.query("Сколько всего кредитов в базе данных?")
    
    if result["success"]:
        print(f"✅ Ответ:\n{result['answer']}\n")
    else:
        print(f"❌ Ошибка: {result['error']}\n")


def example_multiple_questions():
    """Пример с несколькими вопросами."""
    print("=" * 80)
    print("ПРИМЕР 2: Несколько вопросов подряд")
    print("=" * 80 + "\n")
    
    config = load_config()
    agent = CreditSimulationAgent(config)
    
    questions = [
        "Какой средний размер кредита?",
        "Какая доля портфеля в просрочке 30+ дней?",
        "Покажи топ-3 месяца по объему выдач"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] Вопрос: {question}")
        result = agent.query(question)
        
        if result["success"]:
            print(f"Ответ: {result['answer'][:200]}...")  # Первые 200 символов
        else:
            print(f"Ошибка: {result['error']}")


def example_raw_sql():
    """Пример прямых SQL запросов."""
    print("\n" + "=" * 80)
    print("ПРИМЕР 3: Прямые SQL запросы")
    print("=" * 80 + "\n")
    
    config = load_config()
    agent = CreditSimulationAgent(config)
    
    # Простой запрос
    sql1 = "SELECT COUNT(*) as total FROM loan_issue"
    result1 = agent.run_raw_sql(sql1)
    print(f"SQL: {sql1}")
    print(f"Результат: {result1}\n")
    
    # Агрегация
    sql2 = """
    SELECT 
        substr(issue_date, 1, 4) as year,
        COUNT(*) as loans_count,
        ROUND(SUM(loan_amount)/1000000.0, 2) as volume_millions
    FROM loan_issue
    GROUP BY year
    ORDER BY year
    LIMIT 3
    """
    result2 = agent.run_raw_sql(sql2)
    print(f"SQL: {sql2.strip()}")
    print("Результат:")
    for row in result2:
        print(f"  {row}")


def example_table_info():
    """Пример получения информации о таблицах."""
    print("\n" + "=" * 80)
    print("ПРИМЕР 4: Информация о структуре таблиц")
    print("=" * 80 + "\n")
    
    config = load_config()
    agent = CreditSimulationAgent(config)
    
    # Информация о конкретной таблице
    print("Структура таблицы loan_issue:")
    print(agent.get_table_info("loan_issue"))
    print()
    
    print("Структура таблицы credit_fact_history:")
    print(agent.get_table_info("credit_fact_history"))


def example_custom_config():
    """Пример с кастомной конфигурацией."""
    print("\n" + "=" * 80)
    print("ПРИМЕР 5: Кастомная конфигурация")
    print("=" * 80 + "\n")
    
    import os
    
    # Создание конфигурации вручную
    config = AgentConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model="gpt-3.5-turbo",  # Можно изменить на gpt-4
        openai_temperature=0.0,  # Максимально детерминированно
        db_path="../credit_sim.db",
        verbose=False
    )
    
    print(f"Конфигурация:")
    print(f"  Model: {config.openai_model}")
    print(f"  Temperature: {config.openai_temperature}")
    print(f"  Database: {config.db_path}")
    print()
    
    agent = CreditSimulationAgent(config)
    result = agent.query("Какой период данных в базе?")
    
    if result["success"]:
        print(f"Ответ: {result['answer']}")


def example_batch_processing():
    """Пример пакетной обработки без использования batch.py."""
    print("\n" + "=" * 80)
    print("ПРИМЕР 6: Пакетная обработка в коде")
    print("=" * 80 + "\n")
    
    config = load_config()
    agent = CreditSimulationAgent(config)
    
    questions = [
        "Сколько кредитов в базе?",
        "Какой средний чек?",
        "Какая средняя ставка?"
    ]
    
    results = []
    for question in questions:
        result = agent.query(question)
        results.append(result)
    
    # Статистика
    successful = sum(1 for r in results if r["success"])
    print(f"\nСтатистика:")
    print(f"  Всего вопросов: {len(results)}")
    print(f"  Успешных: {successful}")
    print(f"  С ошибками: {len(results) - successful}")
    
    # Сохранение в JSON
    import json
    from datetime import datetime
    
    output = {
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    
    filename = f"outputs/batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Результаты сохранены: {filename}")


def example_error_handling():
    """Пример обработки ошибок."""
    print("\n" + "=" * 80)
    print("ПРИМЕР 7: Обработка ошибок")
    print("=" * 80 + "\n")
    
    try:
        config = load_config()
        agent = CreditSimulationAgent(config)
        
        # Корректный вопрос
        result1 = agent.query("Сколько кредитов?")
        print(f"Корректный вопрос: {'✅ Успешно' if result1['success'] else '❌ Ошибка'}")
        
        # Сложный вопрос (может вызвать ошибку)
        result2 = agent.query("Посчитай квантовую энтропию кредитного портфеля")
        print(f"Сложный вопрос: {'✅ Успешно' if result2['success'] else '❌ Ошибка'}")
        
        if not result2['success']:
            print(f"  Причина: {result2['error'][:100]}")
        
    except FileNotFoundError as e:
        print(f"❌ База данных не найдена: {e}")
    except ValueError as e:
        print(f"❌ Ошибка конфигурации: {e}")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка: {e}")


def main():
    """Запуск всех примеров."""
    print("\n🚀 Примеры использования AI-агента NCL\n")
    
    examples = [
        ("Базовое использование", example_basic),
        ("Несколько вопросов", example_multiple_questions),
        ("Прямые SQL запросы", example_raw_sql),
        ("Информация о таблицах", example_table_info),
        ("Кастомная конфигурация", example_custom_config),
        ("Пакетная обработка", example_batch_processing),
        ("Обработка ошибок", example_error_handling)
    ]
    
    print("Доступные примеры:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    print("\nВыберите пример (1-7) или 0 для запуска всех: ", end="")
    
    try:
        choice = input().strip()
        
        if choice == "0":
            # Запустить все примеры
            for name, func in examples:
                try:
                    func()
                except KeyboardInterrupt:
                    print("\n\n⏸️  Прервано пользователем")
                    break
                except Exception as e:
                    print(f"\n❌ Ошибка в примере '{name}': {e}\n")
        else:
            # Запустить один пример
            idx = int(choice) - 1
            if 0 <= idx < len(examples):
                examples[idx][1]()
            else:
                print(f"❌ Неверный номер примера: {choice}")
    
    except ValueError:
        print("❌ Введите число от 0 до 7")
    except KeyboardInterrupt:
        print("\n\n👋 До свидания!")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nУбедитесь что:")
        print("  1. Установлены зависимости: pip install -r requirements.txt")
        print("  2. Настроен .env файл с OPENAI_API_KEY")
        print("  3. Существует база данных credit_sim.db")


if __name__ == "__main__":
    main()

