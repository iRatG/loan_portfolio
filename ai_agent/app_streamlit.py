"""
Streamlit веб-приложение для AI-агента NCL Credit Simulation.

Предоставляет интерактивный чат-интерфейс для работы с агентом,
визуализацию статистики и историю диалогов.

Запуск:
    streamlit run app_streamlit.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict, Any
import json
from pathlib import Path

from config import load_config
from agent import CreditSimulationAgent


# Конфигурация страницы
st.set_page_config(
    page_title="AI-агент NCL Credit",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Кастомные стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .assistant-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
    }
    .error-message {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
    }
    .stat-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
    }
    .example-question {
        background-color: #fff3cd;
        padding: 0.5rem;
        border-radius: 0.3rem;
        margin: 0.3rem 0;
        cursor: pointer;
        border: 1px solid #ffc107;
    }
    .example-question:hover {
        background-color: #ffe69c;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def init_agent():
    """Инициализировать агента (кешируется)."""
    try:
        config = load_config()
        agent = CreditSimulationAgent(config)
        return agent, None
    except Exception as e:
        return None, str(e)


def init_session_state():
    """Инициализировать состояние сессии."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "conversation_started" not in st.session_state:
        st.session_state.conversation_started = False
    
    if "session_id" not in st.session_state:
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if "stats_loaded" not in st.session_state:
        st.session_state.stats_loaded = False


def get_db_stats(agent: CreditSimulationAgent) -> Dict[str, Any]:
    """Получить статистику БД."""
    try:
        stats = {}
        
        # Основные метрики
        queries = {
            "total_loans": "SELECT COUNT(*) FROM loan_issue",
            "total_volume": "SELECT ROUND(SUM(loan_amount)/1000000000.0, 2) FROM loan_issue",
            "avg_loan": "SELECT ROUND(AVG(loan_amount)/1000.0, 2) FROM loan_issue",
            "avg_rate": "SELECT ROUND(AVG(interest_rate), 2) FROM loan_issue",
            "period_start": "SELECT MIN(issue_date) FROM loan_issue",
            "period_end": "SELECT MAX(issue_date) FROM loan_issue",
            "active_loans": "SELECT COUNT(DISTINCT loan_id) FROM credit_fact_history WHERE status='Active'",
        }
        
        for key, sql in queries.items():
            result = agent.run_raw_sql(sql)
            stats[key] = result[0][0] if result and result[0] else 0
        
        return stats
    except Exception as e:
        st.error(f"Ошибка загрузки статистики: {e}")
        return {}


def render_sidebar(agent: CreditSimulationAgent):
    """Отрисовать боковую панель."""
    with st.sidebar:
        # Навигация
        st.markdown("""
        <div style='padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 10px; margin-bottom: 20px;'>
            <h3 style='color: white; margin: 0 0 10px 0;'>📊 NCL Analytics</h3>
            <a href='http://localhost:8000' 
               style='display: block; padding: 8px; background: white; color: #667eea; 
                      border-radius: 6px; text-decoration: none; text-align: center; 
                      font-weight: 600; font-size: 13px; margin-bottom: 8px;'>
                🏠 Главная
            </a>
            <a href='http://localhost:8050' 
               style='display: block; padding: 8px; background: rgba(255,255,255,0.2); 
                      color: white; border-radius: 6px; text-decoration: none; 
                      text-align: center; font-weight: 600; font-size: 13px;'>
                📊 Дашборд
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🤖 AI-агент")
        st.markdown("---")
        
        # Статистика БД
        st.markdown("### 📊 Статистика портфеля")
        
        if st.button("🔄 Обновить статистику", use_container_width=True):
            st.session_state.stats_loaded = False
        
        if not st.session_state.stats_loaded:
            with st.spinner("Загрузка статистики..."):
                stats = get_db_stats(agent)
                st.session_state.db_stats = stats
                st.session_state.stats_loaded = True
        
        if st.session_state.stats_loaded:
            stats = st.session_state.db_stats
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Всего кредитов", f"{stats.get('total_loans', 0):,}")
                st.metric("Средний чек", f"{stats.get('avg_loan', 0)} тыс ₽")
            with col2:
                st.metric("Объем портфеля", f"{stats.get('total_volume', 0)} млрд ₽")
                st.metric("Средняя ставка", f"{stats.get('avg_rate', 0)}%")
            
            st.info(f"📅 Период: {stats.get('period_start')} - {stats.get('period_end')}")
        
        st.markdown("---")
        
        # Примеры вопросов
        st.markdown("### 💡 Примеры вопросов")
        
        examples_categories = {
            "🔍 Общее": [
                "Сколько кредитов в базе?",
                "Какой период данных?",
                "Какой средний размер кредита?"
            ],
            "📈 Выдачи": [
                "Топ-5 месяцев по выдачам",
                "Динамика выдач по годам",
                "Сезонность в выдачах"
            ],
            "⚠️ Риски": [
                "Какая доля портфеля в просрочке 30+?",
                "Распределение по DPD бакетам",
                "Динамика PAR30"
            ],
            "💰 Макро": [
                "Как ставка ЦБ влияла на выдачи?",
                "Макропоказатели в 2014-2015",
                "Корреляция безработицы и просрочки"
            ]
        }
        
        selected_category = st.selectbox(
            "Категория",
            list(examples_categories.keys())
        )
        
        for example in examples_categories[selected_category]:
            if st.button(f"📝 {example}", use_container_width=True, key=f"ex_{example}"):
                st.session_state.selected_example = example
                st.rerun()
        
        st.markdown("---")
        
        # Управление сессией
        st.markdown("### ⚙️ Управление")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Очистить чат", use_container_width=True):
                st.session_state.messages = []
                st.session_state.conversation_started = False
                st.rerun()
        
        with col2:
            if st.button("💾 Сохранить", use_container_width=True):
                save_conversation()
        
        # Информация о сессии
        st.markdown("---")
        st.caption(f"Сессия: {st.session_state.session_id}")
        st.caption(f"Вопросов: {len([m for m in st.session_state.messages if m['role'] == 'user'])}")


def save_conversation():
    """Сохранить историю диалогов."""
    if not st.session_state.messages:
        st.warning("Нет сообщений для сохранения")
        return
    
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    
    filename = output_dir / f"conversation_{st.session_state.session_id}.json"
    
    data = {
        "session_id": st.session_state.session_id,
        "timestamp": datetime.now().isoformat(),
        "messages": st.session_state.messages
    }
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    st.success(f"✅ Диалог сохранен: {filename}")


def render_chat_message(message: Dict[str, Any]):
    """Отрисовать сообщение в чате."""
    role = message["role"]
    content = message["content"]
    
    if role == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(content)
    
    elif role == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)
    
    elif role == "error":
        with st.chat_message("assistant", avatar="❌"):
            st.error(content)


def render_welcome():
    """Отрисовать приветственное сообщение."""
    st.markdown('<div class="main-header">🤖 AI-агент для анализа кредитного портфеля</div>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    ### Добро пожаловать!
    
    Я - интеллектуальный агент для работы с данными NCL Credit Simulation (2010-2015).
    
    **Что я умею:**
    - 💬 Отвечать на вопросы о кредитном портфеле на русском языке
    - 📊 Генерировать SQL-запросы и анализировать данные
    - 📈 Предоставлять бизнес-интерпретацию метрик
    - ⚡ Работать с риск-метриками, PAR, IFRS9, vintages
    
    **Как начать:**
    1. Посмотрите примеры вопросов в боковой панели →
    2. Или задайте свой вопрос в поле ввода ниже ↓
    """)
    
    # Быстрые действия
    st.markdown("### 🚀 Быстрый старт")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Общая статистика", use_container_width=True):
            st.session_state.selected_example = "Покажи общую статистику портфеля"
            st.rerun()
    
    with col2:
        if st.button("⚠️ Анализ рисков", use_container_width=True):
            st.session_state.selected_example = "Какая доля портфеля в просрочке 30+ дней?"
            st.rerun()
    
    with col3:
        if st.button("📈 Динамика выдач", use_container_width=True):
            st.session_state.selected_example = "Покажи топ-5 месяцев по объему выдач"
            st.rerun()


def process_query(agent: CreditSimulationAgent, question: str):
    """Обработать вопрос пользователя."""
    # Добавить вопрос в историю
    st.session_state.messages.append({
        "role": "user",
        "content": question,
        "timestamp": datetime.now().isoformat()
    })
    
    # Показать вопрос
    with st.chat_message("user", avatar="👤"):
        st.markdown(question)
    
    # Обработка агентом
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🔍 Анализирую..."):
            result = agent.query(question)
        
        if result["success"]:
            answer = result["answer"]
            st.markdown(answer)
            
            # Добавить ответ в историю
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "timestamp": datetime.now().isoformat()
            })
        else:
            error_msg = f"❌ **Ошибка:** {result['error']}"
            st.error(error_msg)
            
            # Добавить ошибку в историю
            st.session_state.messages.append({
                "role": "error",
                "content": error_msg,
                "timestamp": datetime.now().isoformat()
            })


def main():
    """Главная функция приложения."""
    init_session_state()
    
    # Инициализация агента
    agent, error = init_agent()
    
    if error:
        st.error(f"❌ Ошибка инициализации агента: {error}")
        st.info("""
        **Проверьте:**
        1. Файл `.env` существует и содержит `OPENAI_API_KEY`
        2. База данных `credit_sim.db` существует
        3. Установлены все зависимости: `pip install -r requirements.txt`
        """)
        return
    
    # Боковая панель
    render_sidebar(agent)
    
    # Основная область
    if not st.session_state.conversation_started:
        render_welcome()
        st.session_state.conversation_started = True
    
    # История сообщений
    for message in st.session_state.messages:
        render_chat_message(message)
    
    # Обработка примера из сайдбара
    if "selected_example" in st.session_state:
        example = st.session_state.selected_example
        del st.session_state.selected_example
        process_query(agent, example)
        st.rerun()
    
    # Поле ввода
    question = st.chat_input("Задайте вопрос о кредитном портфеле...")
    
    if question:
        process_query(agent, question)
        st.rerun()


if __name__ == "__main__":
    main()

