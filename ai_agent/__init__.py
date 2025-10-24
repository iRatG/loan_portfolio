"""
AI-агент для работы с данными кредитной симуляции NCL.

Использует LangChain для создания SQL-агента, который может:
- Отвечать на вопросы о кредитном портфеле
- Генерировать SQL-запросы на основе естественного языка
- Анализировать риск-метрики
- Предоставлять аналитику по выдачам и просрочкам
"""

__version__ = "1.0.0"
__author__ = "NCL Team"

from .agent import CreditSimulationAgent
from .config import AgentConfig

__all__ = ["CreditSimulationAgent", "AgentConfig"]

