"""
Модуль для пакетной обработки вопросов к AI-агенту.

Позволяет:
- Запускать заранее подготовленные вопросы из файла
- Генерировать отчеты в формате JSON, CSV, HTML
- Использовать для автоматической периодической аналитики
"""

import json
import csv
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from config import load_config
from agent import CreditSimulationAgent


class BatchProcessor:
    """Обработчик пакетных запросов."""
    
    def __init__(self, agent: CreditSimulationAgent):
        self.agent = agent
        self.results: List[Dict[str, Any]] = []
    
    def process_questions(self, questions: List[str], verbose: bool = True) -> List[Dict[str, Any]]:
        """
        Обработать список вопросов.
        
        Args:
            questions: Список вопросов
            verbose: Выводить прогресс
            
        Returns:
            Список результатов
        """
        total = len(questions)
        
        if verbose:
            print(f"\n📦 Обработка {total} вопросов...\n")
        
        for i, question in enumerate(questions, 1):
            if verbose:
                print(f"[{i}/{total}] {question}")
            
            result = self.agent.query(question)
            result["index"] = i
            result["timestamp"] = datetime.now().isoformat()
            
            self.results.append(result)
            
            if verbose:
                if result["success"]:
                    print(f"         ✅ Успешно")
                else:
                    error_preview = result['error'][:100] if result['error'] else "Unknown"
                    print(f"         ❌ Ошибка: {error_preview}")
                print()
        
        if verbose:
            successful = sum(1 for r in self.results if r["success"])
            print(f"{'='*80}")
            print(f"✅ Обработано: {successful}/{total} успешно ({successful/total*100:.1f}%)")
        
        return self.results
    
    def save_json(self, output_file: str):
        """Сохранить результаты в JSON."""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_questions": len(self.results),
                    "successful": sum(1 for r in self.results if r["success"]),
                    "failed": sum(1 for r in self.results if not r["success"])
                },
                "results": self.results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"💾 JSON сохранен: {output_file}")
    
    def save_csv(self, output_file: str):
        """Сохранить результаты в CSV."""
        if not self.results:
            return
        
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            fieldnames = ["index", "question", "answer", "success", "error", "timestamp"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                writer.writerow({
                    "index": result["index"],
                    "question": result["question"],
                    "answer": result.get("answer", ""),
                    "success": result["success"],
                    "error": result.get("error", ""),
                    "timestamp": result["timestamp"]
                })
        
        print(f"💾 CSV сохранен: {output_file}")
    
    def save_html(self, output_file: str):
        """Сохранить результаты в красивый HTML отчет."""
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Статистика
        total = len(self.results)
        successful = sum(1 for r in self.results if r["success"])
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0
        
        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Agent Batch Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #2d3748;
            margin-bottom: 10px;
            font-size: 32px;
        }}
        .timestamp {{
            color: #718096;
            margin-bottom: 30px;
            font-size: 14px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .summary-label {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .summary-value {{
            font-size: 36px;
            font-weight: bold;
        }}
        .qa-item {{
            background: #f7fafc;
            padding: 25px;
            margin: 20px 0;
            border-radius: 10px;
            border-left: 5px solid #667eea;
            transition: all 0.3s ease;
        }}
        .qa-item:hover {{
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }}
        .qa-item.error {{
            border-left-color: #f56565;
            background: #fff5f5;
        }}
        .question-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .question {{
            font-weight: 600;
            color: #2d3748;
            font-size: 18px;
            flex: 1;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .status-success {{
            background: #c6f6d5;
            color: #22543d;
        }}
        .status-error {{
            background: #fed7d7;
            color: #742a2a;
        }}
        .answer {{
            color: #4a5568;
            line-height: 1.7;
            white-space: pre-wrap;
            padding: 15px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }}
        .error-text {{
            color: #e53e3e;
            font-style: italic;
            padding: 15px;
            background: white;
            border-radius: 8px;
            border: 1px solid #fc8181;
        }}
        .meta {{
            color: #a0aec0;
            font-size: 12px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e2e8f0;
        }}
        .progress-bar {{
            height: 30px;
            background: #e2e8f0;
            border-radius: 15px;
            overflow: hidden;
            margin-bottom: 40px;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #48bb78, #38a169);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 600;
            font-size: 14px;
        }}
        @media print {{
            body {{ background: white; }}
            .container {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 AI Agent Batch Report</h1>
        <div class="timestamp">Сгенерировано: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</div>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: {success_rate}%;">
                {success_rate:.1f}% успешно
            </div>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <div class="summary-label">Всего вопросов</div>
                <div class="summary-value">{total}</div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #48bb78, #38a169);">
                <div class="summary-label">Успешно</div>
                <div class="summary-value">{successful}</div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #f56565, #e53e3e);">
                <div class="summary-label">С ошибками</div>
                <div class="summary-value">{failed}</div>
            </div>
            <div class="summary-card" style="background: linear-gradient(135deg, #4299e1, #3182ce);">
                <div class="summary-label">Успешность</div>
                <div class="summary-value">{success_rate:.0f}%</div>
            </div>
        </div>
"""
        
        # Вопросы и ответы
        for result in self.results:
            error_class = "" if result["success"] else " error"
            status_class = "status-success" if result["success"] else "status-error"
            status_text = "✓ Успешно" if result["success"] else "✗ Ошибка"
            
            html += f"""
        <div class="qa-item{error_class}">
            <div class="question-header">
                <div class="question">{result['index']}. {result['question']}</div>
                <span class="status-badge {status_class}">{status_text}</span>
            </div>
"""
            
            if result["success"]:
                answer = result.get('answer', 'Нет ответа')
                html += f"""            <div class="answer">{answer}</div>"""
            else:
                error = result.get('error', 'Неизвестная ошибка')
                html += f"""            <div class="error-text">❌ {error}</div>"""
            
            html += f"""
            <div class="meta">⏱ {result['timestamp']}</div>
        </div>
"""
        
        html += """
    </div>
</body>
</html>
"""
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"💾 HTML сохранен: {output_file}")


def load_questions_from_file(file_path: str) -> List[str]:
    """
    Загрузить вопросы из файла.
    
    Поддерживаемые форматы:
    - .txt: один вопрос на строку (строки с # игнорируются)
    - .json: массив строк или объектов с полем "question"
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    if path.suffix == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            questions = [
                line.strip() for line in f 
                if line.strip() and not line.strip().startswith("#")
            ]
    
    elif path.suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                if all(isinstance(q, str) for q in data):
                    questions = data
                elif all(isinstance(q, dict) and "question" in q for q in data):
                    questions = [q["question"] for q in data]
                else:
                    raise ValueError("Некорректный формат JSON")
            else:
                raise ValueError("JSON должен содержать массив")
    
    else:
        raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}. Используйте .txt или .json")
    
    return questions


def create_default_questions_file(output_file: str = "questions_template.txt"):
    """Создать шаблон файла с вопросами."""
    questions = """# Шаблон вопросов для AI-агента NCL Credit Simulation
# Строки, начинающиеся с #, игнорируются
# Один вопрос на строку

# ========== Общая статистика ==========
Сколько всего кредитов в базе данных?
Какой период данных в базе?
Какой общий объем выдач в рублях?
Какой средний размер кредита?

# ========== Анализ выдач ==========
Покажи топ-5 месяцев по объему выдач
Как менялся средний размер кредита по годам?
Какая динамика процентных ставок по месяцам?
Какая корреляция между ставкой ЦБ и объемом выдач?
Какая сезонность в выдачах по месяцам года?

# ========== Риск-метрики ==========
Какая доля портфеля находится в просрочке 30+ дней?
Покажи распределение кредитов по DPD бакетам
Какая динамика PAR30 по месяцам с 2010 по 2015?
Какой cure rate и default rate?
Сколько кредитов в дефолте?

# ========== Макроэкономика ==========
Как влияла ставка ЦБ на объем выдач?
Какая была занятость и безработица в период кризиса 2014-2015?
Как менялся макро-индекс по годам?

# ========== Vintage analysis ==========
Покажи vintage analysis для когорт 2010 года
Какие когорты показали худшую просрочку?
Какой средний MOB для дефолтных кредитов?

# ========== IFRS9 ==========
Покажи IFRS9 stage mix на последнюю дату
Как менялся stage mix по месяцам в 2014-2015?

# ========== Платежи ==========
Какое соотношение фактических и плановых платежей?
Сколько кредитов закрылось досрочно?
"""
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(questions)
    
    print(f"✅ Шаблон создан: {output_file}")
    print(f"   Отредактируйте файл и запустите:")
    print(f"   python batch.py --input {output_file}")


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Пакетная обработка вопросов к AI-агенту",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Создать шаблон файла с вопросами
  python batch.py --create-template
  
  # Обработать вопросы из файла
  python batch.py --input questions.txt
  
  # Указать директорию для результатов
  python batch.py --input questions.txt --output-dir reports
  
  # Сохранить только в HTML
  python batch.py --input questions.txt --format html
        """
    )
    
    parser.add_argument(
        "--input",
        "-i",
        help="Файл с вопросами (.txt или .json)"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="reports",
        help="Директория для выходных файлов (по умолчанию: reports)"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "csv", "html", "all"],
        default="all",
        help="Формат вывода (по умолчанию: all)"
    )
    parser.add_argument(
        "--create-template",
        action="store_true",
        help="Создать шаблон файла с вопросами"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Режим отладки"
    )
    parser.add_argument(
        "--env",
        help="Путь к .env файлу"
    )
    
    args = parser.parse_args()
    
    # Создание шаблона
    if args.create_template:
        create_default_questions_file()
        return
    
    # Проверка входного файла
    if not args.input:
        parser.error("Требуется --input или --create-template")
    
    try:
        # Загрузка вопросов
        print(f"📂 Загрузка вопросов из {args.input}...")
        questions = load_questions_from_file(args.input)
        print(f"✅ Загружено {len(questions)} вопросов")
        
        # Загрузка конфигурации
        print(f"\n⚙️  Загрузка конфигурации...")
        config = load_config(args.env)
        if args.verbose:
            config.verbose = True
        print(f"✅ Конфигурация загружена")
        
        # Создание агента
        print(f"\n🤖 Инициализация агента ({config.llm_provider})...")
        agent = CreditSimulationAgent(config)
        print(f"✅ Агент готов")
        
        # Обработка вопросов
        processor = BatchProcessor(agent)
        processor.process_questions(questions, verbose=True)
        
        # Создание имени файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_base = output_dir / f"batch_report_{timestamp}"
        
        # Сохранение результатов
        print(f"\n💾 Сохранение результатов в {output_dir}/...")
        
        if args.format in ["json", "all"]:
            processor.save_json(f"{output_base}.json")
        
        if args.format in ["csv", "all"]:
            processor.save_csv(f"{output_base}.csv")
        
        if args.format in ["html", "all"]:
            processor.save_html(f"{output_base}.html")
        
        print(f"\n✅ Готово! Результаты сохранены в {output_dir}/")
        
    except FileNotFoundError as e:
        print(f"\n❌ ОШИБКА: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

