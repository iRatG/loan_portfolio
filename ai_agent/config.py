"""
Конфигурация AI-агента.

Загружает настройки из .env файла с валидацией через Pydantic.
"""

import os
from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator


class AgentConfig(BaseModel):
    """Конфигурация AI-агента."""
    
    # OpenAI настройки
    openai_api_key: Optional[str] = Field(
        default=None,
        description="API ключ OpenAI"
    )
    openai_model: str = Field(
        default="gpt-3.5-turbo",
        description="Модель OpenAI"
    )
    openai_max_tokens: int = Field(
        default=1000,
        ge=100,
        le=4000,
        description="Максимальное количество токенов в ответе"
    )
    openai_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Температура генерации"
    )
    openai_max_requests_per_minute: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Лимит запросов в минуту"
    )
    
    # Anthropic настройки (альтернатива)
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="API ключ Anthropic"
    )
    anthropic_model: str = Field(
        default="claude-3-sonnet-20240229",
        description="Модель Anthropic Claude"
    )
    
    # Провайдер LLM
    llm_provider: Literal["openai", "anthropic"] = Field(
        default="openai",
        description="Провайдер LLM"
    )
    
    # База данных
    db_path: str = Field(
        default="../credit_sim.db",
        description="Путь к базе данных SQLite"
    )
    
    # Логирование
    log_level: str = Field(
        default="INFO",
        description="Уровень логирования"
    )
    log_file: str = Field(
        default="logs/agent.log",
        description="Файл логов"
    )
    
    # История
    history_file: str = Field(
        default="logs/agent_history.jsonl",
        description="Файл истории диалогов"
    )
    
    # Режим отладки
    verbose: bool = Field(
        default=False,
        description="Режим отладки"
    )
    
    class Config:
        """Настройки Pydantic."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("llm_provider")
    def validate_provider_has_key(cls, v, values):
        """Проверить, что для выбранного провайдера есть API ключ."""
        if v == "openai" and not values.get("openai_api_key"):
            # Проверим переменную окружения
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("Для провайдера 'openai' требуется OPENAI_API_KEY")
        elif v == "anthropic" and not values.get("anthropic_api_key"):
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise ValueError("Для провайдера 'anthropic' требуется ANTHROPIC_API_KEY")
        return v
    
    @validator("db_path")
    def validate_db_exists(cls, v):
        """Проверить существование базы данных."""
        # Разрешить относительные пути
        if not v.startswith("/") and not v.startswith("\\") and ":" not in v:
            # Относительный путь - ищем от директории ai_agent
            base_path = Path(__file__).parent
            full_path = (base_path / v).resolve()
        else:
            full_path = Path(v)
        
        if not full_path.exists():
            raise ValueError(f"База данных не найдена: {full_path}")
        
        return str(full_path)
    
    def get_api_key(self) -> str:
        """Получить API ключ для текущего провайдера."""
        if self.llm_provider == "openai":
            return self.openai_api_key or os.getenv("OPENAI_API_KEY")
        else:
            return self.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    
    def get_model_name(self) -> str:
        """Получить название модели для текущего провайдера."""
        if self.llm_provider == "openai":
            return self.openai_model
        else:
            return self.anthropic_model
    
    def setup_logging(self):
        """Настроить логирование."""
        import logging
        
        # Создать директорию для логов
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Настроить логгер
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.log_file, encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
        
        return logging.getLogger("ai_agent")


def load_config(env_file: Optional[str] = None) -> AgentConfig:
    """
    Загрузить конфигурацию из .env файла.
    
    Args:
        env_file: Путь к .env файлу (если не указан, ищет в директории ai_agent)
        
    Returns:
        Объект конфигурации
    """
    if env_file:
        env_path = Path(env_file)
    else:
        # Ищем .env в директории ai_agent
        base_path = Path(__file__).parent
        env_path = base_path / ".env"
    
    # Загрузить переменные из .env если файл существует
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
    
    # Создать конфигурацию
    return AgentConfig()


if __name__ == "__main__":
    # Тест конфигурации
    try:
        config = load_config()
        print("✅ Конфигурация загружена успешно:")
        print(f"  Provider: {config.llm_provider}")
        print(f"  Model: {config.get_model_name()}")
        print(f"  Database: {config.db_path}")
        print(f"  Log file: {config.log_file}")
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")

