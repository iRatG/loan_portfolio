"""
Расширенное Streamlit приложение для AI-агента с визуализацией и аналитикой.

Включает:
- Чат с AI-агентом
- Визуализацию основных метрик
- SQL-песочницу
- Историю запросов

Запуск:
    streamlit run app_streamlit_advanced.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict, Any
import json
from pathlib import Path
import time

from config import load_config
from agent import CreditSimulationAgent
from logging_utils import log_sql_event


st.set_page_config(
    page_title="AI-агент NCL Credit - Advanced",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def init_agent():
    """Инициализировать агента."""
    try:
        config = load_config()
        agent = CreditSimulationAgent(config)
        return agent, None
    except Exception as e:
        return None, str(e)


@st.cache_data
def load_portfolio_overview(_agent):
    """Загрузить обзор портфеля."""
    sql = """
    SELECT 
        substr(issue_date, 1, 7) as month,
        COUNT(*) as loans_count,
        ROUND(SUM(loan_amount)/1000000.0, 2) as volume_mln,
        ROUND(AVG(loan_amount)/1000.0, 2) as avg_ticket_k,
        ROUND(AVG(interest_rate), 2) as avg_rate
    FROM loan_issue
    GROUP BY month
    ORDER BY month
    """
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        with _agent.engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="overview", sql=sql, success=True, rowcount=len(df), duration_ms=dt)
        return df
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="overview", sql=sql, success=False, rowcount=0, duration_ms=dt, error=str(e))
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame(columns=['month', 'loans_count', 'volume_mln', 'avg_ticket_k', 'avg_rate'])


@st.cache_data
def load_dpd_distribution(_agent):
    """Загрузить распределение по DPD."""
    sql = """
    SELECT 
        period_month,
        DPD_bucket,
        COUNT(*) as loans_count,
        ROUND(SUM(balance_principal)/1000000.0, 2) as balance_mln
    FROM credit_fact_history
    WHERE lower(status) = 'active'
    GROUP BY period_month, DPD_bucket
    ORDER BY period_month, DPD_bucket
    """
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        with _agent.engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="dpd_distribution", sql=sql, success=True, rowcount=len(df), duration_ms=dt)
        return df
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="dpd_distribution", sql=sql, success=False, rowcount=0, duration_ms=dt, error=str(e))
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame(columns=['period_month', 'DPD_bucket', 'loans_count', 'balance_mln'])


@st.cache_data
def load_par_metrics(_agent):
    """Загрузить PAR метрики."""
    sql = """
    SELECT 
        period_month,
        ROUND(100.0 * SUM(CASE WHEN DPD_bucket IN ('31-60', '61-90', '90+') 
            THEN balance_principal ELSE 0 END) / 
            NULLIF(SUM(balance_principal), 0), 2) as PAR30,
        ROUND(100.0 * SUM(CASE WHEN DPD_bucket IN ('61-90', '90+') 
            THEN balance_principal ELSE 0 END) / 
            NULLIF(SUM(balance_principal), 0), 2) as PAR60,
        ROUND(100.0 * SUM(CASE WHEN DPD_bucket = '90+' 
            THEN balance_principal ELSE 0 END) / 
            NULLIF(SUM(balance_principal), 0), 2) as PAR90
    FROM credit_fact_history
    WHERE lower(status) = 'active'
    GROUP BY period_month
    ORDER BY period_month
    """
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        with _agent.engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="par_metrics", sql=sql, success=True, rowcount=len(df), duration_ms=dt)
        return df
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="par_metrics", sql=sql, success=False, rowcount=0, duration_ms=dt, error=str(e))
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame(columns=['period_month', 'PAR30', 'PAR60', 'PAR90'])


@st.cache_data
def load_stage_mix(_agent):
    """Загрузить IFRS9 Stage Mix."""
    sql = """
    SELECT 
        period_month,
        ROUND(100.0 * SUM(CASE WHEN DPD_bucket = '0' THEN balance_principal ELSE 0 END) / 
            NULLIF(SUM(balance_principal), 0), 2) as stage1,
        ROUND(100.0 * SUM(CASE WHEN DPD_bucket IN ('1-30', '31-60') THEN balance_principal ELSE 0 END) / 
            NULLIF(SUM(balance_principal), 0), 2) as stage2,
        ROUND(100.0 * SUM(CASE WHEN DPD_bucket IN ('61-90', '90+') THEN balance_principal ELSE 0 END) / 
            NULLIF(SUM(balance_principal), 0), 2) as stage3
    FROM credit_fact_history
    WHERE lower(status) = 'active'
    GROUP BY period_month
    ORDER BY period_month
    """
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        with _agent.engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="stage_mix", sql=sql, success=True, rowcount=len(df), duration_ms=dt)
        return df
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="stage_mix", sql=sql, success=False, rowcount=0, duration_ms=dt, error=str(e))
        st.error(f"Ошибка загрузки Stage Mix: {e}")
        return pd.DataFrame(columns=['period_month', 'stage1', 'stage2', 'stage3'])


@st.cache_data
def load_cure_default(_agent):
    """Загрузить Cure и Default rates."""
    sql = """
    WITH prev_status AS (
        SELECT 
            loan_id,
            period_month,
            DPD_bucket,
            LAG(DPD_bucket) OVER (PARTITION BY loan_id ORDER BY period_month) as prev_bucket
        FROM credit_fact_history
        WHERE lower(status) = 'active'
    )
    SELECT 
        period_month,
        ROUND(100.0 * SUM(CASE WHEN prev_bucket IN ('1-30', '31-60', '61-90', '90+') 
            AND DPD_bucket = '0' THEN 1 ELSE 0 END) / 
            NULLIF(SUM(CASE WHEN prev_bucket IN ('1-30', '31-60', '61-90', '90+') THEN 1 ELSE 0 END), 0), 2) as cure_rate,
        ROUND(100.0 * SUM(CASE WHEN lower(status) = 'default' THEN 1 ELSE 0 END) / 
            NULLIF(COUNT(*), 0), 2) as default_rate
    FROM credit_fact_history
    GROUP BY period_month
    ORDER BY period_month
    """
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        with _agent.engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="cure_default", sql=sql, success=True, rowcount=len(df), duration_ms=dt)
        return df
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="cure_default", sql=sql, success=False, rowcount=0, duration_ms=dt, error=str(e))
        # Упрощенная версия без LAG
        sql_simple = """
        SELECT 
            period_month,
            0 as cure_rate,
            ROUND(100.0 * SUM(CASE WHEN lower(status) = 'default' THEN 1 ELSE 0 END) / 
                NULLIF(COUNT(*), 0), 2) as default_rate
        FROM credit_fact_history
        GROUP BY period_month
        ORDER BY period_month
        """
        try:
            with _agent.engine.connect() as conn:
                result = conn.execute(text(sql_simple))
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
            dt2 = (time.perf_counter() - t0) * 1000.0
            log_sql_event(_agent.config.history_file, name="cure_default_simple", sql=sql_simple, success=True, rowcount=len(df), duration_ms=dt2)
            return df
        except Exception as e2:
            log_sql_event(_agent.config.history_file, name="cure_default_simple", sql=sql_simple, success=False, rowcount=0, duration_ms=0.0, error=str(e2))
            return pd.DataFrame(columns=['period_month', 'cure_rate', 'default_rate'])


@st.cache_data
def load_vintage_analysis(_agent):
    """Загрузить Vintage Analysis: кумулятивный PD до 12M по когортам."""
    sql = """
    WITH first_default AS (
        SELECT 
            loan_id,
            MIN(CASE WHEN lower(status) = 'default' THEN MOB END) AS first_def_mob
        FROM credit_fact_history
        GROUP BY loan_id
    ),
    cohort_size AS (
        SELECT cohort_month, COUNT(*) AS cohort_size
        FROM loan_issue
        GROUP BY cohort_month
    ),
    def_by_mob AS (
        SELECT 
            li.cohort_month,
            cfh.MOB,
            COUNT(DISTINCT CASE WHEN fd.first_def_mob IS NOT NULL AND fd.first_def_mob <= cfh.MOB THEN li.loan_id END) AS def_cum_cnt
        FROM loan_issue li
        JOIN credit_fact_history cfh ON li.loan_id = cfh.loan_id
        LEFT JOIN first_default fd ON fd.loan_id = li.loan_id
        WHERE cfh.MOB <= 12
        GROUP BY li.cohort_month, cfh.MOB
    )
    SELECT 
        d.cohort_month,
        d.MOB,
        cs.cohort_size,
        d.def_cum_cnt,
        ROUND(100.0 * 1.0 * d.def_cum_cnt / NULLIF(cs.cohort_size, 0), 2) AS pd_cum
    FROM def_by_mob d
    JOIN cohort_size cs USING (cohort_month)
    ORDER BY d.cohort_month, d.MOB
    """
    t0 = time.perf_counter()
    try:
        from sqlalchemy import text
        with _agent.engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="vintage_pd_cum", sql=sql, success=True, rowcount=len(df), duration_ms=dt)
        return df
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000.0
        log_sql_event(_agent.config.history_file, name="vintage_pd_cum", sql=sql, success=False, rowcount=0, duration_ms=dt, error=str(e))
        st.error(f"Ошибка загрузки Vintage: {e}")
        return pd.DataFrame(columns=['cohort_month', 'MOB', 'cohort_size', 'def_cum_cnt', 'pd_cum'])


@st.cache_data
def load_payments(_agent):
    """Загрузить платежную дисциплину и метрики Actual/Scheduled."""
    sql = """
    SELECT 
        period_month,
        SUM(scheduled_payment) AS scheduled_sum,
        SUM(actual_payment) AS actual_sum,
        CASE WHEN SUM(scheduled_payment)=0 THEN 0.0 
             ELSE ROUND(1.0 * SUM(actual_payment) / NULLIF(SUM(scheduled_payment),0), 4) END AS actual_vs_scheduled
    FROM credit_fact_history
    GROUP BY period_month
    ORDER BY period_month
    """
    try:
        from sqlalchemy import text
        with _agent.engine.connect() as conn:
            result = conn.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки Payments: {e}")
        return pd.DataFrame(columns=["period_month","scheduled_sum","actual_sum","actual_vs_scheduled"])


@st.cache_data
def load_config_table() -> pd.DataFrame:
    """Загрузить конфигурацию симуляции из TOML в табличном виде."""
    try:
        try:
            import toml  # type: ignore
        except Exception:
            toml = None
        cfg_path = (Path(__file__).resolve().parents[1] / "credit_simulation" / "config" / "config.toml")
        if not cfg_path.exists():
            # запасной путь, если запуск из корня
            alt = Path.cwd().parents[0] / "credit_simulation" / "config" / "config.toml"
            cfg_path = alt if alt.exists() else cfg_path
        if toml is None:
            # Если нет парсера, показать сырое содержимое
            text_data = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""
            return pd.DataFrame([
                {"section":"raw","parameter":"config.toml","value":text_data[:10000],"description":""}
            ])
        cfg = toml.load(str(cfg_path))
        desc = cfg.get("descriptions", {})
        rows = []
        for section_name, section in cfg.items():
            if section_name == "descriptions":
                continue
            if not isinstance(section, dict):
                rows.append({
                    "section": section_name,
                    "parameter": "value",
                    "value": str(section),
                    "description": ""
                })
                continue
            for key, value in section.items():
                d = desc.get(section_name, {}).get(key, "") if isinstance(desc.get(section_name, {}), dict) else ""
                rows.append({
                    "section": section_name,
                    "parameter": key,
                    "value": json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value),
                    "description": d,
                })
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Ошибка загрузки конфигурации: {e}")
        return pd.DataFrame(columns=["section","parameter","value","description"])


def tab_chat(agent):
    """Вкладка с чатом."""
    st.header("💬 Чат с AI-агентом")
    
    # Инициализация состояния
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Примеры вопросов
    with st.expander("💡 Примеры вопросов"):
        col1, col2, col3 = st.columns(3)
        
        examples = [
            "Сколько кредитов в базе?",
            "Какая доля портфеля в просрочке 30+?",
            "Топ-5 месяцев по выдачам",
            "Динамика PAR30 по месяцам",
            "IFRS9 stage mix на последнюю дату",
            "Как ставка ЦБ влияла на выдачи?"
        ]
        
        for i, example in enumerate(examples):
            col = [col1, col2, col3][i % 3]
            with col:
                if st.button(example, key=f"ex_{i}", use_container_width=True):
                    st.session_state.pending_question = example
    
    # История сообщений
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Обработка отложенного вопроса
    if "pending_question" in st.session_state:
        question = st.session_state.pending_question
        del st.session_state.pending_question
        
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        
        with st.chat_message("assistant"):
            with st.spinner("🔍 Анализирую..."):
                result = agent.query(question)
            
            if result["success"]:
                st.markdown(result["answer"])
                st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
            else:
                st.error(f"Ошибка: {result['error']}")
    
    # Поле ввода
    if prompt := st.chat_input("Задайте вопрос..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🔍 Анализирую..."):
                result = agent.query(prompt)
            
            if result["success"]:
                st.markdown(result["answer"])
                st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
            else:
                st.error(f"Ошибка: {result['error']}")
        
        st.rerun()
    
    # Управление
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🗑️ Очистить чат", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("💾 Сохранить диалог", use_container_width=True):
            if st.session_state.messages:
                output_dir = Path("outputs")
                output_dir.mkdir(exist_ok=True)
                filename = output_dir / f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
                st.success(f"✅ Сохранено: {filename}")


def tab_analytics(agent):
    """Вкладка с аналитикой."""
    st.header("📊 Визуальная аналитика")

    # Загрузка данных
    with st.spinner("Загрузка данных..."):
        df_overview = load_portfolio_overview(agent)
        df_dpd = load_dpd_distribution(agent)
        df_par = load_par_metrics(agent)
        df_stage = load_stage_mix(agent)
        df_cure = load_cure_default(agent)
        df_vintage = load_vintage_analysis(agent)
        df_pay = load_payments(agent)
        cfg_df = load_config_table()

    # Верхние метрики (общее)
    st.subheader("Ключевые метрики")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_volume = df_overview['volume_mln'].sum() if not df_overview.empty else 0
        st.metric("Общий объем выдач", f"{total_volume:,.0f} млн ₽")
    with col2:
        total_loans = df_overview['loans_count'].sum() if not df_overview.empty else 0
        st.metric("Всего кредитов", f"{total_loans:,}")
    with col3:
        avg_ticket = df_overview['avg_ticket_k'].mean() if not df_overview.empty else 0
        st.metric("Средний чек", f"{avg_ticket:.1f} тыс ₽")
    with col4:
        latest_par30 = (df_par['PAR30'].iloc[-1] if not df_par.empty else 0)
        st.metric("PAR30 (посл.)", f"{latest_par30:.2f}%")

    st.divider()

    # Под-вкладки как в Dash: Config, DPD, PAR, IFRS9, Payments, Vintages, Issuance, Quarterly
    tab_cfg, tab_dpd, tab_par, tab_ifrs9, tab_pay, tab_vint, tab_iss, tab_q = st.tabs([
        "Config", "DPD", "PAR", "IFRS9", "Payments", "Vintages", "Issuance", "Quarterly"
    ])

    # Config
    with tab_cfg:
        st.caption("Таблица параметров конфигурации симуляции с пояснениями.")
        if not cfg_df.empty:
            st.dataframe(cfg_df, use_container_width=True, height=420)
        else:
            st.info("Конфигурация недоступна.")

    # DPD
    with tab_dpd:
        st.caption("Распределение по бакетам просрочки и динамика долей.")
        if not df_dpd.empty:
            # посчитаем доли по количеству
            tmp = df_dpd.copy()
            totals = tmp.groupby('period_month')['loans_count'].sum().rename('total')
            tmp = tmp.merge(totals, left_on='period_month', right_index=True)
            tmp['share_cnt'] = tmp['loans_count'] / tmp['total'].replace(0, pd.NA)
            fig = px.area(tmp, x='period_month', y='share_cnt', color='DPD_bucket', title='Доли бакетов DPD (по счетам)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных DPD.")

    # PAR
    with tab_par:
        st.caption("Показатели PAR 30/60/90 по балансу (качество портфеля).")
        if not df_par.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_par['period_month'], y=df_par['PAR30'], name='PAR30', mode='lines+markers'))
            fig.add_trace(go.Scatter(x=df_par['period_month'], y=df_par['PAR60'], name='PAR60', mode='lines+markers'))
            fig.add_trace(go.Scatter(x=df_par['period_month'], y=df_par['PAR90'], name='PAR90', mode='lines+markers'))
            fig.update_layout(xaxis_title='Месяц', yaxis_title='PAR, %', hovermode='x unified', height=420)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных PAR.")

    # IFRS9
    with tab_ifrs9:
        st.caption("IFRS9 proxy: доли Stage 1/2/3 по балансу.")
        if not df_stage.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_stage['period_month'], y=df_stage['stage1'], name='Stage 1', fill='tonexty', mode='lines'))
            fig.add_trace(go.Scatter(x=df_stage['period_month'], y=df_stage['stage2'], name='Stage 2', fill='tonexty', mode='lines'))
            fig.add_trace(go.Scatter(x=df_stage['period_month'], y=df_stage['stage3'], name='Stage 3', fill='tonexty', mode='lines'))
            fig.update_layout(xaxis_title='Месяц', yaxis_title='Доля, %', height=420, hovermode='x unified', yaxis=dict(range=[0,100]))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных IFRS9.")

    # Payments
    with tab_pay:
        st.caption("Дисциплина платежей: отношение фактических к плановым платежам.")
        if not df_pay.empty:
            fig = px.line(df_pay, x='period_month', y='actual_vs_scheduled', title='Actual/Scheduled')
            fig.update_layout(yaxis_tickformat='.2f', height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Нет данных по платежам.")

    # Vintages
    with tab_vint:
        st.caption("Vintage PD (кумулятивный до 12M) по когортам выдачи.")
        if not df_vintage.empty:
            # Список лет и выбор
            years = sorted({str(c)[:4] for c in df_vintage['cohort_month'].unique()})
            left, right = st.columns(2)
            with left:
                year = st.selectbox("Год когорты", years, index=len(years)-1 if years else 0)
            with right:
                show_labels = st.checkbox("Показывать подписи на тепловой карте", value=True)

            df_year = df_vintage[df_vintage['cohort_month'].str.startswith(year)] if years else df_vintage

            # Heatmap PDcum по MOB
            if not df_year.empty:
                piv = df_year.pivot(index='cohort_month', columns='MOB', values='pd_cum').sort_index()
                fig = px.imshow(
                    piv,
                    labels=dict(x="MOB (месяц на балансе)", y="Когорта", color="PD cum, %"),
                    aspect="auto",
                    color_continuous_scale="Reds",
                    text_auto=True if show_labels else False,
                )
                fig.update_layout(height=520)
                # Формат подписей
                if show_labels:
                    fig.update_traces(texttemplate="%{text:.1f}")
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("—")

            # Кривые PDcum по выбранным когортам
            st.markdown("**Кривые PD cum по выбранным когортам:**")
            all_cohorts = sorted(df_year['cohort_month'].unique())
            default_sel = all_cohorts[-3:] if len(all_cohorts) >= 3 else all_cohorts
            selected = st.multiselect("Когорты для сравнения", all_cohorts, default=default_sel)
            if selected:
                curves = df_vintage[df_vintage['cohort_month'].isin(selected)].copy()
                figc = px.line(curves, x='MOB', y='pd_cum', color='cohort_month', markers=True,
                               labels={"pd_cum":"PD cum, %"}, title=None)
                figc.update_layout(height=420, yaxis_title="PD cum, %")
                st.plotly_chart(figc, use_container_width=True)

            st.markdown("—")

            # Сводная таблица PD@3/6/12 и размер когорты
            st.markdown("**Сводка по когортам: PD@3/6/12 и размер когорты**")
            try:
                base = df_vintage[df_vintage['MOB'].isin([3,6,12])].copy()
                pivot = base.pivot_table(index='cohort_month', columns='MOB', values='pd_cum', aggfunc='max')
                # Подтягиваем размер когорты
                size_map = df_vintage.groupby('cohort_month')['cohort_size'].max()
                pivot = pivot.merge(size_map, left_index=True, right_index=True)
                pivot = pivot.rename(columns={3:'PD@3', 6:'PD@6', 12:'PD@12', 'cohort_size':'Cohort size'})
                # Порядок колонок
                cols = [c for c in ['Cohort size','PD@3','PD@6','PD@12'] if c in pivot.columns]
                show = pivot[cols].reset_index().sort_values('cohort_month')
                st.dataframe(show, use_container_width=True, height=360)
            except Exception as e:
                st.info("Недостаточно данных для сводной таблицы PD@3/6/12.")
        else:
            st.info("Нет данных Vintage.")

    # Issuance
    with tab_iss:
        st.caption("Аналитика по выданному портфелю: объём, кол-во, средний чек и ставка.")
        if not df_overview.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Объем выдач (млн ₽)")
                st.plotly_chart(px.bar(df_overview, x='month', y='volume_mln'), use_container_width=True)
            with c2:
                st.subheader("Количество кредитов")
                st.plotly_chart(px.line(df_overview, x='month', y='loans_count', markers=True), use_container_width=True)
            c3, c4 = st.columns(2)
            with c3:
                st.subheader("Средний чек (тыс ₽)")
                st.plotly_chart(px.line(df_overview, x='month', y='avg_ticket_k', markers=True), use_container_width=True)
            with c4:
                st.subheader("Средняя ставка (%)")
                st.plotly_chart(px.line(df_overview, x='month', y='avg_rate', markers=True), use_container_width=True)
        else:
            st.info("Нет данных по выдачам.")

    # Quarterly
    with tab_q:
        st.caption("Квартальная сводка основных риск‑метрик (средние значения).")
        try:
            items = []
            # DPD shares quarterly
            if not df_dpd.empty:
                tmp = df_dpd.copy()
                totals = tmp.groupby('period_month')['loans_count'].sum().rename('total')
                tmp = tmp.merge(totals, left_on='period_month', right_index=True)
                tmp['q'] = pd.to_datetime(tmp['period_month']).dt.to_period('Q').astype(str)
                tmp['share'] = tmp['loans_count'] / tmp['total'].replace(0, pd.NA)
                bq = tmp.pivot_table(index='q', columns='DPD_bucket', values='share', aggfunc='mean').fillna(0)
                items.append(("DPD (доли по счетам)", bq))
            # PAR quarterly
            if not df_par.empty:
                pq = pd.DataFrame({
                    'q': pd.to_datetime(df_par['period_month']).dt.to_period('Q').astype(str),
                    'PAR30': df_par['PAR30'].astype(float),
                    'PAR60': df_par['PAR60'].astype(float),
                    'PAR90': df_par['PAR90'].astype(float),
                }).groupby('q').mean()
                items.append(("PAR (по балансу)", pq))
            # IFRS9 quarterly
            if not df_stage.empty:
                sq = pd.DataFrame({
                    'q': pd.to_datetime(df_stage['period_month']).dt.to_period('Q').astype(str),
                    'Stage 1': df_stage['stage1'].astype(float),
                    'Stage 2': df_stage['stage2'].astype(float),
                    'Stage 3': df_stage['stage3'].astype(float),
                }).groupby('q').mean()
                items.append(("IFRS9 Stage mix", sq))
            # Collections quarterly
            if not df_cure.empty:
                cq = pd.DataFrame({
                    'q': pd.to_datetime(df_cure['period_month']).dt.to_period('Q').astype(str),
                    'Cure rate': df_cure['cure_rate'].astype(float),
                    'Default rate': df_cure['default_rate'].astype(float),
                }).groupby('q').mean()
                items.append(("Collections", cq))
            # Payments quarterly
            if not df_pay.empty:
                payq = pd.DataFrame({
                    'q': pd.to_datetime(df_pay['period_month']).dt.to_period('Q').astype(str),
                    'Actual/Scheduled': df_pay['actual_vs_scheduled'].astype(float),
                }).groupby('q').mean()
                items.append(("Payments", payq))

            if not items:
                st.info("Нет данных для квартальных метрик.")
            else:
                for title, data in items:
                    st.subheader(title)
                    df_show = data.reset_index()
                    st.dataframe(df_show, use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка построения квартальных метрик: {e}")


def tab_sql_sandbox(agent):
    """Вкладка с SQL песочницей."""
    st.header("🔧 SQL Песочница")
    
    st.info("💡 Выполняйте прямые SQL запросы к базе данных для детального анализа")
    
    # Информация о таблицах
    with st.expander("📁 Структура таблиц"):
        table = st.selectbox("Выберите таблицу", ["loan_issue", "credit_fact_history", "macro_params_log"])
        st.code(agent.get_table_info(table), language="sql")
    
    # Примеры запросов
    examples = {
        "Топ-10 кредитов по сумме": """
SELECT loan_id, issue_date, loan_amount, interest_rate
FROM loan_issue
ORDER BY loan_amount DESC
LIMIT 10""",
        "Статистика по годам": """
SELECT 
    substr(issue_date, 1, 4) as year,
    COUNT(*) as loans_count,
    ROUND(AVG(loan_amount), 2) as avg_amount,
    ROUND(AVG(interest_rate), 2) as avg_rate
FROM loan_issue
GROUP BY year
ORDER BY year""",
        "DPD распределение на последнюю дату": """
SELECT 
    DPD_bucket,
    COUNT(*) as count,
    ROUND(SUM(balance_principal)/1000000.0, 2) as balance_mln
FROM credit_fact_history
WHERE period_month = (SELECT MAX(period_month) FROM credit_fact_history)
    AND status = 'Active'
GROUP BY DPD_bucket
ORDER BY DPD_bucket"""
    }
    
    selected_example = st.selectbox("Примеры запросов", ["Свой запрос"] + list(examples.keys()))
    
    # Редактор SQL
    if selected_example == "Свой запрос":
        sql_query = st.text_area(
            "SQL запрос",
            height=200,
            placeholder="SELECT * FROM loan_issue LIMIT 10"
        )
    else:
        sql_query = st.text_area(
            "SQL запрос",
            value=examples[selected_example],
            height=200
        )
    
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        execute = st.button("▶️ Выполнить", type="primary", use_container_width=True)
    with col2:
        clear = st.button("🗑️ Очистить", use_container_width=True)
    
    if clear:
        st.rerun()
    
    # Выполнение запроса
    if execute and sql_query.strip():
        try:
            from sqlalchemy import text
            import time
            t0 = time.perf_counter()
            with agent.engine.connect() as conn:
                result = conn.execute(text(sql_query))
                rows = result.fetchall()
                cols = list(result.keys()) if hasattr(result, "keys") else None
            dt = (time.perf_counter() - t0) * 1000.0
            log_sql_event(agent.config.history_file, name="sandbox", sql=sql_query, success=True, rowcount=len(rows), duration_ms=dt)

            if rows:
                st.success(f"✅ Запрос выполнен успешно. Строк: {len(rows)}")
                st.subheader("Результаты")
                # Формируем DataFrame корректно
                if cols:
                    df_result = pd.DataFrame(rows, columns=cols)
                else:
                    # Фолбэк для списка кортежей или скаляров
                    if isinstance(rows[0], (list, tuple)):
                        df_result = pd.DataFrame(rows)
                    else:
                        df_result = pd.DataFrame({"value": rows})
                # Приведение dict/list столбцов к строкам (для совместимости с Arrow)
                for c in df_result.columns:
                    if df_result[c].map(lambda v: isinstance(v, (dict, list))).any():
                        df_result[c] = df_result[c].apply(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                st.dataframe(df_result, use_container_width=True)
                # Скачать CSV
                csv = df_result.to_csv(index=False)
                st.download_button(
                    label="📥 Скачать CSV",
                    data=csv,
                    file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Запрос выполнен, но не вернул результатов")
        except Exception as e:
            log_sql_event(agent.config.history_file, name="sandbox", sql=sql_query, success=False, rowcount=0, duration_ms=0.0, error=str(e))
            st.error(f"❌ Ошибка выполнения запроса:\n{str(e)}")


def tab_history(agent):
    """Вкладка с историей."""
    st.header("📜 История запросов")
    
    history_file = Path("logs/agent_history.jsonl")
    
    if not history_file.exists():
        st.info("История запросов пуста")
        return
    
    # Загрузить историю
    interactions = []
    with open(history_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                interactions.append(json.loads(line))
            except:
                continue
    
    if not interactions:
        st.info("История запросов пуста")
        return
    
    # Статистика
    st.subheader("📊 Статистика")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Всего запросов", len(interactions))
    
    with col2:
        successful = sum(1 for i in interactions if i.get("success"))
        st.metric("Успешных", successful)
    
    with col3:
        failed = len(interactions) - successful
        st.metric("С ошибками", failed)
    
    with col4:
        success_rate = (successful / len(interactions) * 100) if interactions else 0
        st.metric("Успешность", f"{success_rate:.1f}%")
    
    st.divider()
    
    # Фильтры
    col1, col2 = st.columns(2)
    
    with col1:
        filter_success = st.radio(
            "Статус",
            ["Все", "Только успешные", "Только с ошибками"],
            horizontal=True
        )
    
    with col2:
        limit = st.slider("Показать последних", 10, 100, 50)
    
    # Фильтрация
    filtered = interactions[-limit:]
    
    if filter_success == "Только успешные":
        filtered = [i for i in filtered if i.get("success")]
    elif filter_success == "Только с ошибками":
        filtered = [i for i in filtered if not i.get("success")]
    
    # Отображение
    st.subheader("История")
    
    for i, interaction in enumerate(reversed(filtered), 1):
        with st.expander(
            f"{'✅' if interaction.get('success') else '❌'} "
            f"{interaction.get('timestamp', 'N/A')[:19]} - "
            f"{interaction.get('question', 'N/A')[:100]}"
        ):
            st.markdown(f"**Вопрос:** {interaction.get('question')}")
            
            if interaction.get('success'):
                st.markdown(f"**Ответ:** {interaction.get('answer')}")
            else:
                st.error(f"**Ошибка:** {interaction.get('error')}")
            
            st.caption(f"Session: {interaction.get('session_id')}")


def main():
    """Главная функция."""
    # Навигационная панель в сайдбаре
    with st.sidebar:
        st.markdown("""
        <div style='padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    border-radius: 10px; margin-bottom: 20px;'>
            <h2 style='color: white; margin: 0;'>📊 NCL Analytics</h2>
            <p style='color: white; opacity: 0.9; font-size: 14px; margin: 5px 0 15px 0;'>
                Платформа аналитики
            </p>
            <a href='http://localhost:8000' target='_blank' 
               style='display: block; padding: 10px; background: white; color: #667eea; 
                      border-radius: 8px; text-decoration: none; text-align: center; 
                      font-weight: 600; margin-bottom: 10px;'>
                🏠 Главная страница
            </a>
            <a href='http://localhost:8050' target='_blank' 
               style='display: block; padding: 10px; background: rgba(255,255,255,0.2); 
                      color: white; border-radius: 8px; text-decoration: none; 
                      text-align: center; font-weight: 600;'>
                📊 Дашборд аналитики
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
    
    # Заголовок
    st.title("🤖 AI-агент для анализа кредитного портфеля")
    st.caption("Интеллектуальный анализ данных Credit Simulation (2010-2015)")
    
    # Инициализация агента
    agent, error = init_agent()
    
    if error:
        st.error(f"❌ Ошибка инициализации: {error}")
        st.stop()
    
    # Вкладки
    tab1, tab2, tab3, tab4 = st.tabs([
        "💬 Чат",
        "📊 Аналитика",
        "🔧 SQL",
        "📜 История"
    ])
    
    with tab1:
        tab_chat(agent)
    
    with tab2:
        tab_analytics(agent)
    
    with tab3:
        tab_sql_sandbox(agent)
    
    with tab4:
        tab_history(agent)


if __name__ == "__main__":
    main()

