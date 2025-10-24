"""
Командный интерфейс (CLI) для AI-агента.

Предоставляет интерактивный режим работы с агентом,
историю диалогов и дополнительные команды.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False

from config import load_config, AgentConfig
from agent import CreditSimulationAgent


class ConversationManager:
    """Менеджер истории разговоров."""
    
    def __init__(self, history_file: str):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_session: List[Dict[str, Any]] = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def add_interaction(
        self,
        question: str,
        answer: str,
        success: bool,
        error: Optional[str] = None
    ):
        """Добавить взаимодействие в историю."""
        interaction = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer": answer,
            "success": success,
            "error": error
        }
        self.current_session.append(interaction)
        
        # Сохранить в файл (JSONL format)
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(interaction, ensure_ascii=False) + "\n")
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Получить сводку по текущей сессии."""
        return {
            "session_id": self.session_id,
            "total_questions": len(self.current_session),
            "successful": sum(1 for i in self.current_session if i["success"]),
            "failed": sum(1 for i in self.current_session if not i["success"]),
            "questions": [i["question"] for i in self.current_session]
        }


class AgentCLI:
    """Командный интерфейс для агента."""
    
    COMMANDS = {
        "help": "Показать список команд",
        "examples": "Показать примеры вопросов",
        "history": "Показать историю текущей сессии",
        "tables": "Показать информацию о таблицах БД",
        "stats": "Показать быструю статистику по БД",
        "sql": "Выполнить прямой SQL-запрос (формат: /sql SELECT...)",
        "save": "Сохранить последний ответ в файл",
        "clear": "Очистить экран",
        "config": "Показать текущую конфигурацию",
        "exit": "Выйти из программы (также: quit, выход)"
    }
    
    def __init__(
        self,
        agent: CreditSimulationAgent,
        conversation_manager: ConversationManager
    ):
        self.agent = agent
        self.conv_manager = conversation_manager
        self.last_answer = None
    
    def _colored(self, text: str, color: str) -> str:
        """Раскрасить текст если доступна colorama."""
        if not HAS_COLORAMA:
            return text
        
        colors = {
            "red": Fore.RED,
            "green": Fore.GREEN,
            "yellow": Fore.YELLOW,
            "blue": Fore.BLUE,
            "magenta": Fore.MAGENTA,
            "cyan": Fore.CYAN,
            "white": Fore.WHITE
        }
        
        return f"{colors.get(color, '')}{text}{Style.RESET_ALL}"
    
    def print_header(self):
        """Вывести заголовок."""
        print("\n" + "=" * 80)
        print(self._colored(
            " " * 15 + "AI-АГЕНТ ДЛЯ АНАЛИЗА КРЕДИТНОГО ПОРТФЕЛЯ NCL",
            "cyan"
        ))
        print("=" * 80)
        print(f"\n📊 База данных: {self.agent.config.db_path}")
        print(f"🤖 LLM: {self.agent.config.llm_provider} ({self.agent.config.get_model_name()})")
        print(f"🆔 Сессия: {self.conv_manager.session_id}")
        print(f"\nВведите {self._colored('/help', 'yellow')} для списка команд")
        print("-" * 80 + "\n")
    
    def print_help(self):
        """Вывести справку."""
        print(f"\n{self._colored('📖 Доступные команды:', 'cyan')}\n")
        for cmd, desc in self.COMMANDS.items():
            cmd_colored = self._colored(f"/{cmd:<12}", "yellow")
            print(f"  {cmd_colored} - {desc}")
        print(f"\n💡 {self._colored('Просто задавайте вопросы на естественном языке!', 'green')}")
        print()
    
    def handle_command(self, command: str) -> bool:
        """
        Обработать команду.
        
        Returns:
            True если нужно продолжить, False если выход
        """
        cmd_parts = command.strip().split(maxsplit=1)
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1] if len(cmd_parts) > 1 else ""
        
        if cmd in ["exit", "quit", "выход"]:
            return False
        
        elif cmd == "help":
            self.print_help()
        
        elif cmd == "examples":
            print(f"\n{self._colored('📋 Примеры вопросов:', 'cyan')}\n")
            examples = self.agent.get_example_questions()
            # Показываем по 10 примеров с группировкой
            groups = {
                "Общая статистика": examples[0:5],
                "Анализ выдач": examples[5:10],
                "Риск-метрики": examples[10:15],
                "IFRS9 и макроэкономика": examples[15:20],
            }
            for group_name, questions in groups.items():
                print(f"  {self._colored(group_name + ':', 'yellow')}")
                for q in questions:
                    print(f"    • {q}")
                print()
        
        elif cmd == "history":
            summary = self.conv_manager.get_session_summary()
            print(f"\n{self._colored('📜 История сессии', 'cyan')} {summary['session_id']}:\n")
            print(f"  Всего вопросов: {summary['total_questions']}")
            print(f"  Успешных: {self._colored(str(summary['successful']), 'green')}")
            print(f"  С ошибками: {self._colored(str(summary['failed']), 'red')}")
            if summary['questions']:
                print("\n  Вопросы:")
                for i, q in enumerate(summary['questions'], 1):
                    print(f"    {i}. {q}")
            print()
        
        elif cmd == "tables":
            print(f"\n{self._colored('📁 Информация о таблицах:', 'cyan')}\n")
            print(self.agent.get_table_info())
            print()
        
        elif cmd == "stats":
            self.show_db_stats()
        
        elif cmd == "sql":
            if not args:
                print(f"{self._colored('❌', 'red')} Использование: /sql SELECT ...")
            else:
                self.execute_raw_sql(args)
        
        elif cmd == "save":
            self.save_last_answer()
        
        elif cmd == "config":
            self.show_config()
        
        elif cmd == "clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            self.print_header()
        
        else:
            print(f"{self._colored('❌', 'red')} Неизвестная команда: /{cmd}")
            print(f"Введите {self._colored('/help', 'yellow')} для списка команд")
        
        return True
    
    def show_config(self):
        """Показать текущую конфигурацию."""
        cfg = self.agent.config
        print(f"\n{self._colored('⚙️  Конфигурация агента:', 'cyan')}\n")
        print(f"  LLM Provider: {cfg.llm_provider}")
        print(f"  Model: {cfg.get_model_name()}")
        print(f"  Temperature: {cfg.openai_temperature}")
        print(f"  Max Tokens: {cfg.openai_max_tokens}")
        print(f"  Database: {cfg.db_path}")
        print(f"  Log File: {cfg.log_file}")
        print(f"  History File: {cfg.history_file}")
        print(f"  Verbose: {cfg.verbose}")
        print()
    
    def show_db_stats(self):
        """Показать быструю статистику БД."""
        print(f"\n{self._colored('📊 Статистика базы данных:', 'cyan')}\n")
        
        stats_queries = [
            ("Всего кредитов", "SELECT COUNT(*) FROM loan_issue"),
            ("Период выдач", "SELECT MIN(issue_date) || ' - ' || MAX(issue_date) FROM loan_issue"),
            ("Общий объем выдач (млрд руб)", "SELECT ROUND(SUM(loan_amount)/1000000000.0, 2) FROM loan_issue"),
            ("Средний чек (тыс руб)", "SELECT ROUND(AVG(loan_amount)/1000.0, 2) FROM loan_issue"),
            ("Средняя ставка (%)", "SELECT ROUND(AVG(interest_rate), 2) FROM loan_issue"),
            ("Записей в credit_fact_history", "SELECT COUNT(*) FROM credit_fact_history"),
            ("Период операционного факта", "SELECT MIN(period_month) || ' - ' || MAX(period_month) FROM credit_fact_history")
        ]
        
        for label, sql in stats_queries:
            try:
                result = self.agent.run_raw_sql(sql)
                value = result[0][0] if result and result[0] else "N/A"
                print(f"  {label}: {self._colored(str(value), 'green')}")
            except Exception as e:
                print(f"  {label}: {self._colored(f'Ошибка - {e}', 'red')}")
        print()
    
    def execute_raw_sql(self, sql: str):
        """Выполнить прямой SQL."""
        print(f"\n{self._colored('🔧 Выполняю SQL:', 'cyan')}\n{sql}\n")
        try:
            result = self.agent.run_raw_sql(sql)
            if result:
                print(f"{self._colored('📋 Результат:', 'cyan')}\n")
                for i, row in enumerate(result[:50], 1):  # Показываем первые 50 строк
                    print(f"  {i}. {row}")
                if len(result) > 50:
                    print(f"\n  {self._colored(f'... и еще {len(result) - 50} строк', 'yellow')}")
                print(f"\nВсего строк: {self._colored(str(len(result)), 'green')}")
            else:
                print(f"{self._colored('✅', 'green')} Запрос выполнен успешно (нет результатов)")
        except Exception as e:
            print(f"{self._colored('❌ Ошибка выполнения SQL:', 'red')} {e}")
        print()
    
    def save_last_answer(self):
        """Сохранить последний ответ в файл."""
        if not self.last_answer:
            print(f"{self._colored('❌', 'red')} Нет ответа для сохранения")
            return
        
        # Создать директорию outputs
        output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)
        
        filename = output_dir / f"answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Вопрос: {self.last_answer['question']}\n")
            f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\n{'='*80}\n\n")
            f.write(f"Ответ:\n\n{self.last_answer['answer']}\n")
        
        print(f"{self._colored('✅', 'green')} Ответ сохранен: {filename}")
    
    def process_question(self, question: str):
        """Обработать вопрос пользователя."""
        print(f"\n{self._colored('🔍 Анализирую...', 'yellow')}\n")
        
        result = self.agent.query(question)
        
        if result["success"]:
            print(f"{self._colored('💡 Ответ:', 'cyan')}")
            print(result["answer"])
            self.last_answer = result
            self.conv_manager.add_interaction(
                question, result["answer"], True
            )
        else:
            print(f"{self._colored('❌ Ошибка:', 'red')}")
            print(result["error"])
            self.conv_manager.add_interaction(
                question, "", False, result["error"]
            )
        
        print("\n" + "-" * 80 + "\n")
    
    def run(self):
        """Запустить интерактивный режим."""
        self.print_header()
        
        while True:
            try:
                user_input = input(f"{self._colored('❓', 'cyan')} Вопрос или команда: ").strip()
                
                if not user_input:
                    continue
                
                # Команда начинается с /
                if user_input.startswith("/"):
                    if not self.handle_command(user_input[1:]):
                        break
                # Специальные слова для выхода
                elif user_input.lower() in ['exit', 'quit', 'выход']:
                    break
                # Обычный вопрос
                else:
                    self.process_question(user_input)
            
            except KeyboardInterrupt:
                print("\n")
                break
            except EOFError:
                print("\n")
                break
            except Exception as e:
                print(f"\n{self._colored('❌ Непредвиденная ошибка:', 'red')} {e}\n")
        
        # Показать сводку по сессии
        summary = self.conv_manager.get_session_summary()
        print(f"\n{self._colored('📊 Сводка по сессии:', 'cyan')}")
        print(f"  Вопросов задано: {summary['total_questions']}")
        print(f"  Успешных ответов: {self._colored(str(summary['successful']), 'green')}")
        print(f"  С ошибками: {self._colored(str(summary['failed']), 'red')}")
        print(f"\n{self._colored('👋 До свидания!', 'cyan')}\n")


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="AI-агент для анализа кредитного портфеля NCL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  
  # Запуск с настройками из .env файла
  python cli.py
  
  # Запуск с другой моделью
  python cli.py --model gpt-4
  
  # Verbose режим для отладки
  python cli.py --verbose
  
  # Использовать другую БД
  python cli.py --db ../other_database.db

Настройка:
  1. Скопируйте .env.example в .env
  2. Укажите ваш OPENAI_API_KEY
  3. При необходимости измените другие параметры
        """
    )
    
    parser.add_argument(
        "--env",
        help="Путь к .env файлу (по умолчанию: .env в директории ai_agent)"
    )
    parser.add_argument(
        "--db",
        help="Путь к базе данных (переопределяет .env)"
    )
    parser.add_argument(
        "--model",
        help="Модель LLM (переопределяет .env)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Режим отладки с детальным выводом"
    )
    
    args = parser.parse_args()
    
    try:
        # Загрузка конфигурации
        print("\n⚙️  Загрузка конфигурации...", end="", flush=True)
        config = load_config(args.env)
        print(" ✅")
        
        # Переопределение параметров из аргументов
        if args.db:
            config.db_path = args.db
        if args.model:
            if config.llm_provider == "openai":
                config.openai_model = args.model
            else:
                config.anthropic_model = args.model
        if args.verbose:
            config.verbose = True
        
        # Создание агента
        print(f"🤖 Инициализация агента ({config.llm_provider})...", end="", flush=True)
        agent = CreditSimulationAgent(config)
        print(" ✅")
        
        # Создание менеджера истории
        conv_manager = ConversationManager(config.history_file)
        
        # Запуск CLI
        cli = AgentCLI(agent, conv_manager)
        cli.run()
        
    except FileNotFoundError as e:
        print(f"\n❌ ОШИБКА: {e}")
        print("\nУбедитесь что:")
        print("  1. Сгенерированы данные (credit_sim.db существует)")
        print("  2. Путь к БД указан правильно в .env файле")
        sys.exit(1)
    
    except ValueError as e:
        print(f"\n❌ ОШИБКА конфигурации: {e}")
        print("\nПроверьте файл .env:")
        print("  1. Указан ли OPENAI_API_KEY?")
        print("  2. Корректны ли пути к файлам?")
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Ошибка инициализации: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

