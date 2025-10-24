from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pandas as pd
import toml
from sqlalchemy import create_engine, text

import dash
from dash import dcc, html, dash_table
import plotly.express as px


def load_config(path: Path) -> dict:
    """Загрузить TOML‑конфигурацию.

    Args:
      path: Путь к файлу TOML.

    Returns:
      Словарь с параметрами конфигурации.
    """
    return toml.load(path)


def load_portfolio(conn_str: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Загрузить данные портфеля для дашборда.

    Args:
      conn_str: Строка подключения SQLAlchemy.

    Returns:
      Кортеж датафреймов: (facts, bucket, cure, default, pay, vint, par, stage, roll, iss, iss_q).
    """
    engine = create_engine(conn_str, future=True)
    with engine.begin() as conn:
        facts = pd.read_sql(text("SELECT * FROM credit_fact_history"), conn, parse_dates=["period_month"])  
        # Issuance from loan_issue
        issues = pd.read_sql(text("SELECT cohort_month, loan_amount, interest_rate, term_months FROM loan_issue"), conn, parse_dates=["cohort_month"])  
    if facts.empty:
        # пустые placeholder
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty

    facts["pm"] = facts["period_month"].dt.to_period("M").dt.to_timestamp()
    # KPI
    bucket = facts.groupby(["pm", "DPD_bucket"]).size().rename("cnt").reset_index()
    bucket["share"] = bucket["cnt"] / bucket.groupby("pm")["cnt"].transform("sum")
    # Roll-rate (prev_bucket -> DPD_bucket per month)
    facts = facts.sort_values(["loan_id", "period_month"])  
    facts["prev_bucket"] = facts.groupby("loan_id")["DPD_bucket"].shift(1)
    roll = (
        facts.groupby(["pm", "prev_bucket", "DPD_bucket"]).size().rename("cnt").reset_index()
    )
    if len(roll):
        roll["rate"] = roll["cnt"] / roll.groupby(["pm", "prev_bucket"])['cnt'].transform('sum')
    # Cure
    cure = facts.groupby("pm").apply(lambda s: ((s["DPD_bucket"] == "0") & (s["prev_bucket"].isin(["1-30","31-60","61-90","90+"])) ).mean()).rename("cure_rate").reset_index()
    # Default
    default = facts.groupby("pm")["status"].apply(lambda s: (s == "default").mean()).rename("default_rate").reset_index()
    # Payments
    pay = facts.groupby("pm").agg(scheduled_sum=("scheduled_payment","sum"), actual_sum=("actual_payment","sum")).reset_index()
    pay["actual_vs_scheduled"] = (pay["actual_sum"]/pay["scheduled_sum"]).fillna(0)
    # Vintage PD 12m (упрощенно)
    first_pm = facts.groupby("loan_id")["pm"].transform("min")
    facts["cohort"] = first_pm
    vint = facts[facts["MOB"] <= 12].groupby(["loan_id"]).apply(lambda s: (s["status"]=="default").any()).rename("default_12m").reset_index()
    vint = vint.merge(facts.groupby("loan_id")["cohort"].first().reset_index(), on="loan_id", how="left")
    vint = vint.groupby("cohort")["default_12m"].mean().rename("vintage_pd_12m").reset_index()

    # PAR/Stage
    def par_stage(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        pm = df["pm"]
        d = df
        # PAR
        par = d.groupby(pm).apply(
            lambda s: pd.Series({
                "par30": float(s.loc[s["overdue_days"] >= 30, "balance_principal"].sum() / max(1.0, s["balance_principal"].sum())),
                "par60": float(s.loc[s["overdue_days"] >= 60, "balance_principal"].sum() / max(1.0, s["balance_principal"].sum())),
                "par90": float(s.loc[s["overdue_days"] >= 90, "balance_principal"].sum() / max(1.0, s["balance_principal"].sum())),
            })
        ).reset_index(names=["pm"])    
        # Stage mix
        def stage_row(s: pd.DataFrame) -> pd.Series:
            bal = max(1.0, s["balance_principal"].sum())
            stage1 = float(s.loc[s["overdue_days"] < 30, "balance_principal"].sum() / bal)
            stage2 = float(s.loc[(s["overdue_days"] >= 30) & (s["overdue_days"] < 90), "balance_principal"].sum() / bal)
            stage3 = float(s.loc[s["overdue_days"] >= 90, "balance_principal"].sum() / bal)
            return pd.Series({"stage1": stage1, "stage2": stage2, "stage3": stage3})
        stage = d.groupby(pm).apply(stage_row).reset_index(names=["pm"])    
        return par, stage
    par, stage = par_stage(facts)

    # Summary
    summary = facts.groupby("pm").agg(
        loans_cnt=("loan_id","nunique"),
        bal_sum=("balance_principal","sum"),
        ovd_pr_sum=("overdue_principal","sum"),
        ovd_int_sum=("overdue_interest","sum"),
    ).reset_index()
    # Issuance monthly (2010-2015 window будет применяться позже)
    issues['pm'] = issues['cohort_month'].dt.to_period('M').dt.to_timestamp()
    iss = issues.groupby('pm').agg(
        loans_cnt=("cohort_month","count"),
        amount_sum=("loan_amount","sum"),
        amount_avg=("loan_amount","mean"),
        rate_avg=("interest_rate","mean"),
        term_avg=("term_months","mean"),
    ).reset_index()
    # Issuance quarterly
    iss_q = iss.copy()
    iss_q['q'] = pd.to_datetime(iss_q['pm']).dt.to_period('Q').dt.to_timestamp()
    iss_q = iss_q.groupby('q').agg(
        loans_cnt=("loans_cnt","sum"),
        amount_sum=("amount_sum","sum"),
        amount_avg=("amount_avg","mean"),
        rate_avg=("rate_avg","mean"),
        term_avg=("term_avg","mean"),
    ).reset_index()

    return facts, bucket, cure, default, pay, vint, par, stage, roll, iss, iss_q


def build_app(conn: str, cfg_path: Path) -> dash.Dash:
    """Собрать Dash‑приложение (read‑only) с вкладками и таблицами.

    Args:
      conn: Строка подключения к БД.
      cfg_path: Путь к файлу конфигурации TOML.

    Returns:
      Инициализированное приложение Dash.
    """
    cfg = load_config(cfg_path)
    facts, bucket, cure, default, pay, vint, par, stage, roll, iss, iss_q = load_portfolio(conn)

    app = dash.Dash(__name__)
    app.title = "Risk Dashboard (Read-only)"

    # Config as table with descriptions
    desc = cfg.get("descriptions", {})
    cfg_rows = []
    for section_name in ["simulation","loan_parameters","sensitivity","database","collections"]:
        if section_name in cfg:
            for k, v in cfg[section_name].items():
                dsc = desc.get(section_name, {}).get(k, "")
                cfg_rows.append({
                    "section": section_name,
                    "parameter": k,
                    "value": str(v),
                    "description": dsc,
                })
    cfg_table = dash_table.DataTable(
        columns=[
            {"name": "Section", "id": "section"},
            {"name": "Parameter", "id": "parameter"},
            {"name": "Value", "id": "value"},
            {"name": "Description", "id": "description"},
        ],
        data=cfg_rows,
        sort_action="native",
        filter_action="native",
        page_size=15,
        style_table={"overflowX":"auto"},
        style_cell={"textAlign":"left"},
    )

    # Charts (if data) — фильтр периода 2010–2015
    charts = []
    def trim_pm(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        df = df.copy()
        if "pm" in df.columns:
            pm_col = "pm"
        elif "period_month" in df.columns:
            pm_col = "period_month"
        elif "cohort" in df.columns:
            pm_col = "cohort"
        else:
            return df
        df[pm_col] = pd.to_datetime(df[pm_col]).dt.to_period("M").dt.to_timestamp()
        start = pd.Timestamp("2010-01-01")
        end = pd.Timestamp("2015-12-31")
        return df[(df[pm_col] >= start) & (df[pm_col] <= end)]

    bucket = trim_pm(bucket)
    cure = trim_pm(cure)
    default = trim_pm(default)
    pay = trim_pm(pay)
    vint = trim_pm(vint)
    par = trim_pm(par)
    stage = trim_pm(stage)
    roll = trim_pm(roll)
    iss = trim_pm(iss)
    if not bucket.empty:
        fig_bucket = px.area(bucket, x="pm", y="share", color="DPD_bucket", title="Доли бакетов DPD")
        charts.append(dcc.Graph(figure=fig_bucket))
    if not roll.empty:
        # Показать roll-rate из бакета 0 по умолчанию
        rr0 = roll[roll["prev_bucket"] == "0"].copy()
        if not rr0.empty:
            fig_rr0 = px.line(rr0, x="pm", y="rate", color="DPD_bucket", title="Roll-rate из бакета 0")
            charts.append(dcc.Graph(figure=fig_rr0))
    if not cure.empty:
        fig_cure = px.line(cure, x="pm", y="cure_rate", title="Cure rate")
        charts.append(dcc.Graph(figure=fig_cure))
    if not default.empty:
        fig_def = px.line(default, x="pm", y="default_rate", title="Default rate")
        charts.append(dcc.Graph(figure=fig_def))
    if not pay.empty:
        fig_pay = px.line(pay, x="pm", y="actual_vs_scheduled", title="Actual/Scheduled")
        charts.append(dcc.Graph(figure=fig_pay))
    if not vint.empty:
        fig_vint = px.line(vint, x="cohort", y="vintage_pd_12m", title="Vintage PD (12m)")
        charts.append(dcc.Graph(figure=fig_vint))
    if not par.empty:
        fig_par = px.line(par, x="pm", y=["par30","par60","par90"], title="PAR 30/60/90 (баланс)")
        charts.append(dcc.Graph(figure=fig_par))
    if not stage.empty:
        fig_stage = px.area(stage, x="pm", y=["stage1","stage2","stage3"], title="IFRS9 Stage mix (proxy)")
        charts.append(dcc.Graph(figure=fig_stage))
    # Issuance charts (2010–2015)
    issuance_charts = []
    if not iss.empty:
        fig_iss_cnt = px.line(iss, x="pm", y="loans_cnt", title="Выдачи: количество кредитов")
        fig_iss_amt = px.line(iss, x="pm", y="amount_sum", title="Выдачи: сумма (руб)")
        fig_iss_avg = px.line(iss, x="pm", y="amount_avg", title="Выдачи: средний чек (руб)")
        fig_iss_rate = px.line(iss, x="pm", y="rate_avg", title="Выдачи: средняя ставка (%)")
        issuance_charts += [dcc.Graph(figure=fig_iss_cnt), dcc.Graph(figure=fig_iss_amt), dcc.Graph(figure=fig_iss_avg), dcc.Graph(figure=fig_iss_rate)]

    # KPI table (последний месяц) с подсказками
    kpi_children = []
    try:
        if not bucket.empty:
            last = bucket["pm"].max()
            bd_last = bucket[bucket["pm"] == last]
            def get_share(b):
                return float(bd_last.loc[bd_last["DPD_bucket"]==b, "share"].sum())
            kpi_children = [
                html.Tr([html.Th(html.Abbr(title="Последний доступный месяц", children="Период")), html.Td(str(last.date()))]),
                html.Tr([html.Th(html.Abbr(title="Доля счетов без просрочки", children="Доля 0")), html.Td(f"{get_share('0'):.2%}")]),
                html.Tr([html.Th(html.Abbr(title="Доля 1–30 дней просрочки", children="Доля 1–30")), html.Td(f"{get_share('1-30'):.2%}")]),
                html.Tr([html.Th(html.Abbr(title="Доля 31–60 дней просрочки", children="Доля 31–60")), html.Td(f"{get_share('31-60'):.2%}")]),
                html.Tr([html.Th(html.Abbr(title="Доля 61–90 дней просрочки", children="Доля 61–90")), html.Td(f"{get_share('61-90'):.2%}")]),
                html.Tr([html.Th(html.Abbr(title="Доля 90+ дней просрочки (NPL)", children="Доля 90+")), html.Td(f"{get_share('90+'):.2%}")]),
            ]
    except Exception:
        pass

    # Quarterly tables of main metrics (бизнес-ориентированные названия и подсказки)
    quarterly_children = []
    try:
        def to_quarter(df, col):
            q = pd.to_datetime(df[col]).dt.to_period("Q").dt.to_timestamp()
            return df.assign(q=q)

        def fmt_percent_df(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
            d = df.reset_index().copy()
            d['q'] = pd.to_datetime(d['q']).dt.to_period('Q').astype(str)
            for c in cols:
                if c in d:
                    d[c] = (d[c].astype(float) * 100.0).round(2).map(lambda x: f"{x:.2f}%")
            return d

        # DPD shares
        if not bucket.empty:
            bq = to_quarter(bucket, "pm").pivot_table(index="q", columns="DPD_bucket", values="share", aggfunc="mean").fillna(0)
            if not bq.empty:
                dpd = fmt_percent_df(bq, [c for c in bq.columns])
                # Переименуем исходные бакеты в человеко-читаемые названия
                dpd = dpd.rename(columns={
                    '0': 'Доля 0',
                    '1-30': 'Доля 1–30',
                    '31-60': 'Доля 31–60',
                    '61-90': 'Доля 61–90',
                    '90+': 'Доля 90+',
                })
                dpd_cols = ["q", "Доля 0", "Доля 1–30", "Доля 31–60", "Доля 61–90", "Доля 90+"]
                dpd_tooltip = {
                    c: {'value': v, 'type': 'markdown'} for c, v in {
                        'q': 'Квартал',
                        'Доля 0': 'Доля счетов без просрочки',
                        'Доля 1–30': 'Доля счетов с просрочкой 1–30 дней',
                        'Доля 31–60': 'Доля счетов с просрочкой 31–60 дней',
                        'Доля 61–90': 'Доля счетов с просрочкой 61–90 дней',
                        'Доля 90+': 'Доля счетов с просрочкой 90+ дней (NPL)'
                    }.items()
                }
                # Debug preview first 3 rows
                preview = dpd[dpd_cols].head(3).to_dict("records")
                quarterly_children += [html.H4("DPD (доли, по счетам)"), dash_table.DataTable(
                    columns=[{"name": c, "id": c} for c in dpd_cols],
                    data=dpd[dpd_cols].to_dict("records"),
                    tooltip_header=dpd_tooltip,
                    sort_action="native", page_size=10,
                    style_table={"overflowX":"auto"}, style_cell={"textAlign":"left"},
                ), html.Details([html.Summary("DPD preview"), html.Pre(str(preview))])]

        # PAR
        if not par.empty:
            parq = to_quarter(par, "pm").groupby("q")[['par30','par60','par90']].mean()
            if not parq.empty:
                par_tbl = fmt_percent_df(parq, ['par30','par60','par90']).rename(columns={'par30':'PAR30','par60':'PAR60','par90':'PAR90'})
                par_cols = ["q","PAR30","PAR60","PAR90"]
                par_tooltip = {
                    "q": {'value': 'Квартал', 'type': 'markdown'},
                    "PAR30": {'value': 'Доля баланса с просрочкой ≥30 дней', 'type': 'markdown'},
                    "PAR60": {'value': 'Доля баланса с просрочкой ≥60 дней', 'type': 'markdown'},
                    "PAR90": {'value': 'Доля баланса с просрочкой ≥90 дней', 'type': 'markdown'},
                }
                preview_par = par_tbl[par_cols].head(3).to_dict("records")
                quarterly_children += [html.H4("PAR (по балансу)"), dash_table.DataTable(
                    columns=[{"name": c, "id": c} for c in par_cols],
                    data=par_tbl[par_cols].to_dict("records"),
                    tooltip_header=par_tooltip,
                    sort_action="native", page_size=10,
                    style_table={"overflowX":"auto"}, style_cell={"textAlign":"left"},
                ), html.Details([html.Summary("PAR preview"), html.Pre(str(preview_par))])]

        # IFRS9 Stage mix
        if not stage.empty:
            stq = to_quarter(stage, "pm").groupby("q")[['stage1','stage2','stage3']].mean()
            if not stq.empty:
                st_tbl = fmt_percent_df(stq, ['stage1','stage2','stage3']).rename(columns={'stage1':'Stage 1','stage2':'Stage 2','stage3':'Stage 3'})
                st_cols = ["q","Stage 1","Stage 2","Stage 3"]
                st_tooltip = {
                    "q": {'value': 'Квартал', 'type': 'markdown'},
                    "Stage 1": {'value': 'Доля баланса в Stage 1 (<30 дней просрочки)', 'type': 'markdown'},
                    "Stage 2": {'value': 'Доля баланса в Stage 2 (30–89 дней)', 'type': 'markdown'},
                    "Stage 3": {'value': 'Доля баланса в Stage 3 (≥90 дней / default)', 'type': 'markdown'},
                }
                preview_st = st_tbl[st_cols].head(3).to_dict("records")
                quarterly_children += [html.H4("IFRS9 Stage mix (proxy)"), dash_table.DataTable(
                    columns=[{"name": c, "id": c} for c in st_cols],
                    data=st_tbl[st_cols].to_dict("records"),
                    tooltip_header=st_tooltip,
                    sort_action="native", page_size=10,
                    style_table={"overflowX":"auto"}, style_cell={"textAlign":"left"},
                ), html.Details([html.Summary("IFRS9 preview"), html.Pre(str(preview_st))])]

        # Collections (cure/default)
        if not cure.empty or not default.empty:
            cuq = to_quarter(cure, "pm").groupby("q")[['cure_rate']].mean() if not cure.empty else pd.DataFrame()
            defq = to_quarter(default, "pm").groupby("q")[['default_rate']].mean() if not default.empty else pd.DataFrame()
            if not cuq.empty or not defq.empty:
                col_tbl = cuq.reset_index().merge(defq.reset_index(), on='q', how='outer')
                col_tbl = fmt_percent_df(col_tbl.set_index('q'), ['cure_rate','default_rate']).rename(columns={'cure_rate':'Cure rate','default_rate':'Default rate'})
                col_cols = ["q","Cure rate","Default rate"]
                col_tooltip = {
                    "q": {'value': 'Квартал', 'type': 'markdown'},
                    "Cure rate": {'value': 'Доля счетов, вернувшихся в 0 из просрочки за квартал', 'type': 'markdown'},
                    "Default rate": {'value': 'Доля счетов, перешедших в дефолт за квартал', 'type': 'markdown'},
                }
                preview_col = col_tbl[col_cols].head(3).to_dict("records")
                quarterly_children += [html.H4("Collections"), dash_table.DataTable(
                    columns=[{"name": c, "id": c} for c in col_cols],
                    data=col_tbl[col_cols].to_dict("records"),
                    tooltip_header=col_tooltip,
                    sort_action="native", page_size=10,
                    style_table={"overflowX":"auto"}, style_cell={"textAlign":"left"},
                ), html.Details([html.Summary("Collections preview"), html.Pre(str(preview_col))])]

        # Payments
        if not pay.empty:
            payq = to_quarter(pay, "pm").groupby("q")[['actual_vs_scheduled']].mean()
            if not payq.empty:
                pay_tbl = payq.reset_index()
                pay_tbl['q'] = pd.to_datetime(pay_tbl['q']).dt.to_period('Q').astype(str)
                pay_tbl['Actual/Scheduled'] = pay_tbl['actual_vs_scheduled'].astype(float).round(2)
                pay_cols = ["q","Actual/Scheduled"]
                pay_tooltip = {
                    "q": {'value': 'Квартал', 'type': 'markdown'},
                    "Actual/Scheduled": {'value': 'Отношение фактических к плановым платежам (среднее за квартал)', 'type': 'markdown'},
                }
                preview_pay = pay_tbl[pay_cols].head(3).to_dict("records")
                quarterly_children += [html.H4("Payments"), dash_table.DataTable(
                    columns=[{"name": c, "id": c} for c in pay_cols],
                    data=pay_tbl[pay_cols].to_dict("records"),
                    tooltip_header=pay_tooltip,
                    sort_action="native", page_size=10,
                    style_table={"overflowX":"auto"}, style_cell={"textAlign":"left"},
                ), html.Details([html.Summary("Payments preview"), html.Pre(str(preview_pay))])]
    except Exception as e:
        quarterly_children = [html.P("Ошибка построения квартальных метрик."), html.Pre(str(e))]

    if not quarterly_children:
        diag = f"bucket={len(bucket)}, par={len(par)}, stage={len(stage)}, cure={len(cure)}, default={len(default)}, pay={len(pay)}"
        quarterly_children = [html.P("Нет данных для квартальных метрик в выбранном периоде."), html.Small(diag)]

    # Tabs
    # Описания вкладок
    tab_desc = {
        "Config": "Таблица параметров конфигурации симуляции с пояснениями.",
        "DPD": "Распределение по бакетам просрочки и пример roll-rate из бакета 0.",
        "PAR": "Показатели PAR 30/60/90 по балансу (качество портфеля).",
        "IFRS9": "IFRS9 proxy: доли Stage 1/2/3 по балансу.",
        "Payments": "Дисциплина платежей: отношение фактических к плановым платежам.",
        "Vintages": "Vintage PD 12m по когортам выдачи.",
        "Quarterly": "Квартальная сводка основных риск‑метрик (средние значения).",
    }
    tabs = dcc.Tabs(children=[
        dcc.Tab(label="Config", children=[html.P(tab_desc["Config"]), cfg_table]),
        dcc.Tab(label="DPD", children=[html.P(tab_desc["DPD"]), html.Table(kpi_children, style={"border":"1px solid #ccc","marginBottom":"12px"})] + [c for c in charts if getattr(c, 'figure', None) and getattr(c.figure, 'layout', None) and ('DPD' in (c.figure.layout.title.text or '') or 'Roll-rate' in (c.figure.layout.title.text or ''))]),
        dcc.Tab(label="PAR", children=[html.P(tab_desc["PAR"])] + [c for c in charts if getattr(c, 'figure', None) and getattr(c.figure, 'layout', None) and ('PAR' in (c.figure.layout.title.text or ''))]),
        dcc.Tab(label="IFRS9", children=[html.P(tab_desc["IFRS9"])] + [c for c in charts if getattr(c, 'figure', None) and getattr(c.figure, 'layout', None) and ('IFRS9' in (c.figure.layout.title.text or ''))]),
        dcc.Tab(label="Payments", children=[html.P(tab_desc["Payments"])] + [c for c in charts if getattr(c, 'figure', None) and getattr(c.figure, 'layout', None) and ('Actual/Scheduled' in (c.figure.layout.title.text or ''))]),
        dcc.Tab(label="Vintages", children=[html.P(tab_desc["Vintages"])] + [c for c in charts if getattr(c, 'figure', None) and getattr(c.figure, 'layout', None) and ('Vintage PD' in (c.figure.layout.title.text or ''))]),
        dcc.Tab(label="Issuance", children=[html.P("Аналитика по выданному портфелю (2010–2015): объём, кол-во, средний чек и ставка."), *issuance_charts]),
        dcc.Tab(label="Quarterly", children=[html.P(tab_desc["Quarterly"])] + quarterly_children),
    ])

    app.layout = html.Div([
        html.H1("Risk Dashboard (Read-only)"),
        html.P("Просмотр конфигурации, описаний параметров и ключевых риск-метрик портфеля за 2010–2015."),
        tabs
    ], style={"margin":"20px"})

    return app


def main() -> None:
    """CLI для запуска дашборда (read‑only)."""
    parser = argparse.ArgumentParser(description="Run Risk Dashboard (read-only)")
    parser.add_argument("--conn", default="sqlite:///credit_sim.db")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    cfg_path = project_root / "credit_simulation" / "config" / "config.toml"
    app = build_app(args.conn, cfg_path)
    app.run_server(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
