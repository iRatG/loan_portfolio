from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go


def load_facts(conn_str: str) -> pd.DataFrame:
    """Load facts from DB.

    Args:
      conn_str: SQLAlchemy connection string.

    Returns:
      DataFrame with credit facts and parsed period_month.
    """
    engine = create_engine(conn_str, future=True)
    with engine.begin() as conn:
        df = pd.read_sql(
            text(
                """
                SELECT loan_id, period_month, MOB, DPD_bucket, overdue_days,
                       balance_principal, overdue_principal, overdue_interest,
                       interest_scheduled, scheduled_payment, actual_payment, status
                FROM credit_fact_history
                """
            ),
            conn,
            parse_dates=["period_month"],
        )
    return df


def filter_period(df: pd.DataFrame, start_ym: str | None, end_ym: str | None) -> pd.DataFrame:
    """Trim dataset by inclusive monthly range.

    Args:
      df: Input DataFrame containing period_month.
      start_ym: Start YYYY-MM (inclusive) or None.
      end_ym: End YYYY-MM (inclusive) or None.

    Returns:
      Filtered DataFrame with normalized monthly timestamps.
    """
    df = df.copy()
    pm = pd.to_datetime(df["period_month"]).dt.to_period("M").dt.to_timestamp()
    df["period_month"] = pm
    if start_ym:
        start_dt = pd.to_datetime(start_ym + "-01").to_period("M").to_timestamp()
        df = df[df["period_month"] >= start_dt]
    if end_ym:
        end_dt = pd.to_datetime(end_ym + "-01").to_period("M").to_timestamp()
        df = df[df["period_month"] <= end_dt]
    return df


def compute_bucket_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly distribution of DPD buckets (shares by count)."""
    g = df.groupby([df["period_month"].dt.to_period("M").dt.to_timestamp(), "DPD_bucket"]).size().rename("cnt").reset_index()
    total = g.groupby("period_month")["cnt"].transform("sum")
    g["share"] = g["cnt"] / total
    return g.sort_values(["period_month", "DPD_bucket"])  


def compute_roll_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly roll-rate matrix prev_bucket -> current bucket.

    Returns:
      Long-format DataFrame with columns: period_month, prev_bucket, DPD_bucket, cnt, rate.
    """
    df = df.sort_values(["loan_id", "period_month"])  
    df["prev_bucket"] = df.groupby("loan_id")["DPD_bucket"].shift(1)
    pm = df["period_month"].dt.to_period("M").dt.to_timestamp()
    g = (
        df.assign(pm=pm)
          .groupby(["pm", "prev_bucket", "DPD_bucket"])  
          .size()
          .rename("cnt")
          .reset_index()
          .rename(columns={"pm": "period_month"})
    )
    if len(g):
        denom = g.groupby(["period_month", "prev_bucket"])['cnt'].transform('sum')
        g["rate"] = g["cnt"] / denom
    else:
        g["rate"] = []
    return g.sort_values(["period_month", "prev_bucket", "DPD_bucket"])  


def compute_cure_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly cure rate (share returning to bucket 0 from any delinquency)."""
    df = df.sort_values(["loan_id", "period_month"])  
    df["prev_bucket"] = df.groupby("loan_id")["DPD_bucket"].shift(1)
    df["is_cure"] = (df["DPD_bucket"] == "0") & (df["prev_bucket"].isin(["1-30", "31-60", "61-90", "90+"]))
    g = df.groupby(df["period_month"].dt.to_period("M").dt.to_timestamp())["is_cure"].mean().rename("cure_rate").reset_index()
    return g


def compute_default_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly default rate (share of status==default)."""
    df = df.sort_values(["loan_id", "period_month"])  
    df["is_default"] = df["status"] == "default"
    g = df.groupby(df["period_month"].dt.to_period("M").dt.to_timestamp())["is_default"].mean().rename("default_rate").reset_index()
    return g


def compute_summary_kpis(
    df: pd.DataFrame,
    bucket_dist: pd.DataFrame,
    cure: pd.DataFrame,
    default_r: pd.DataFrame,
    pay: pd.DataFrame,
) -> pd.DataFrame:
    pm = df["period_month"].dt.to_period("M").dt.to_timestamp()
    base = df.assign(pm=pm).groupby("pm").agg(
        loans_cnt=("loan_id", "nunique"),
        bal_sum=("balance_principal", "sum"),
        ovd_pr_sum=("overdue_principal", "sum"),
        ovd_int_sum=("overdue_interest", "sum"),
    ).reset_index()

    piv = bucket_dist.pivot(index="period_month", columns="DPD_bucket", values="share").fillna(0)
    piv = piv.rename_axis(None, axis=1).reset_index().rename(columns={"period_month": "pm"})

    out = (
        base
        .merge(piv, on="pm", how="left")
        .merge(cure.rename(columns={"period_month": "pm"}), on="pm", how="left")
        .merge(default_r.rename(columns={"period_month": "pm"}), on="pm", how="left")
        .merge(pay.rename(columns={"period_month": "pm"}), on="pm", how="left")
    )
    out = out.rename(columns={
        "0": "share_0",
        "1-30": "share_1_30",
        "31-60": "share_31_60",
        "61-90": "share_61_90",
        "90+": "share_90p",
    })
    return out.sort_values("pm")


def compute_payment_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly payment aggregates and actual/scheduled ratio."""
    g = df.groupby(df["period_month"].dt.to_period("M").dt.to_timestamp()).agg(
        scheduled_sum=("scheduled_payment", "sum"),
        actual_sum=("actual_payment", "sum"),
        interest_scheduled_sum=("interest_scheduled", "sum"),
        overdue_interest_sum=("overdue_interest", "sum"),
        overdue_principal_sum=("overdue_principal", "sum"),
    ).reset_index()
    g["actual_vs_scheduled"] = (g["actual_sum"] / g["scheduled_sum"]).fillna(0)
    return g


def compute_vintage_pd(df: pd.DataFrame) -> pd.DataFrame:
    """Compute Vintage PD 12m by cohort: any default within first 12 MOB."""
    # Простая proxy: PD_vintage(MOB<=12) = доля кредитов, у которых за первые 12 мес. был default
    first_period = df.groupby("loan_id")["period_month"].transform("min")
    df["cohort_month"] = first_period.dt.to_period("M").dt.to_timestamp()
    is_default_12m = df[df["MOB"] <= 12].groupby("loan_id")["status"].apply(lambda s: (s == "default").any())
    vint = is_default_12m.reset_index().rename(columns={"status": "default_12m"})
    # Привязываем к когорте
    cohorts = df.groupby("loan_id")["cohort_month"].first().reset_index()
    vint = vint.merge(cohorts, on="loan_id", how="left")
    vint = vint.groupby("cohort_month")["default_12m"].mean().rename("vintage_pd_12m").reset_index()
    return vint


def compute_par_and_stage(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute PAR30/60/90 and IFRS9 Stage mix (proxy) by month.

    Returns:
      Tuple (par, stage) DataFrames indexed by month.
    """
    pm = df["period_month"].dt.to_period("M").dt.to_timestamp()
    d = df.assign(pm=pm)
    # PAR (balance-based)
    par = d.groupby("pm").apply(
        lambda s: pd.Series({
            "par30": float(s.loc[s["overdue_days"] >= 30, "balance_principal"].sum() / max(1.0, s["balance_principal"].sum())),
            "par60": float(s.loc[s["overdue_days"] >= 60, "balance_principal"].sum() / max(1.0, s["balance_principal"].sum())),
            "par90": float(s.loc[s["overdue_days"] >= 90, "balance_principal"].sum() / max(1.0, s["balance_principal"].sum())),
        })
    ).reset_index()
    # Stage mix (IFRS9 proxy)
    def stage_row(s: pd.DataFrame) -> pd.Series:
        bal = max(1.0, s["balance_principal"].sum())
        stage1 = float(s.loc[s["overdue_days"] < 30, "balance_principal"].sum() / bal)
        stage2 = float(s.loc[(s["overdue_days"] >= 30) & (s["overdue_days"] < 90), "balance_principal"].sum() / bal)
        stage3 = float(s.loc[s["overdue_days"] >= 90, "balance_principal"].sum() / bal)
        return pd.Series({"stage1": stage1, "stage2": stage2, "stage3": stage3})
    stage = d.groupby("pm").apply(stage_row).reset_index()
    return par, stage


def main() -> None:
    """CLI entrypoint: compute CSV metrics and optional charts/HTML dashboards."""
    parser = argparse.ArgumentParser(description="Risk metrics for module 2 (credit_fact_history)")
    parser.add_argument("--conn", default="sqlite:///credit_sim.db")
    parser.add_argument("--outdir", default="logs")
    parser.add_argument("--plots", action="store_true", help="Save PNG charts alongside CSVs")
    parser.add_argument("--plotly", action="store_true", help="Save interactive HTML dashboards")
    parser.add_argument("--alert_90p", type=float, default=0.15, help="Threshold for 90+ share alert (default 0.15)")
    parser.add_argument("--alert_cure", type=float, default=0.05, help="Threshold for cure rate alert (default 0.05)")
    parser.add_argument("--start", type=str, default="2010-01", help="Start YYYY-MM (default 2010-01)")
    parser.add_argument("--end", type=str, default="2015-12", help="End YYYY-MM (default 2015-12)")
    args = parser.parse_args()

    df = load_facts(args.conn)
    df = filter_period(df, args.start, args.end)
    if df.empty:
        print("credit_fact_history пуста. Запустите симуляцию модуля 2.")
        return

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    bucket_dist = compute_bucket_distribution(df)
    roll = compute_roll_rates(df)
    cure = compute_cure_rates(df)
    default_r = compute_default_rate(df)
    pay = compute_payment_ratios(df)
    vint = compute_vintage_pd(df)
    par, stage = compute_par_and_stage(df)
    summary = compute_summary_kpis(df, bucket_dist, cure, default_r, pay)

    bucket_dist.to_csv(outdir / "risk_bucket_distribution.csv", index=False)
    roll.to_csv(outdir / "risk_roll_rates.csv", index=False)
    cure.to_csv(outdir / "risk_cure_rates.csv", index=False)
    default_r.to_csv(outdir / "risk_default_rates.csv", index=False)
    pay.to_csv(outdir / "risk_payment_ratios.csv", index=False)
    vint.to_csv(outdir / "risk_vintage_pd_12m.csv", index=False)
    par.to_csv(outdir / "risk_par.csv", index=False)
    stage.to_csv(outdir / "risk_stage_mix.csv", index=False)
    summary.to_csv(outdir / "risk_summary_monthly.csv", index=False)
    if not summary.empty:
        summary.tail(1).to_csv(outdir / "risk_summary_last.csv", index=False)

    print("Saved:")
    for f in [
        "risk_bucket_distribution.csv",
        "risk_roll_rates.csv",
        "risk_cure_rates.csv",
        "risk_default_rates.csv",
        "risk_payment_ratios.csv",
        "risk_vintage_pd_12m.csv",
        "risk_par.csv",
        "risk_stage_mix.csv",
        "risk_summary_monthly.csv",
        "risk_summary_last.csv",
    ]:
        print(outdir / f)

    if args.plots:
        # 1) Bucket distribution stacked area
        try:
            pivot = bucket_dist.pivot(index="period_month", columns="DPD_bucket", values="share").fillna(0)
            plt.figure(figsize=(10, 5))
            plt.stackplot(pivot.index, [pivot[c] for c in sorted(pivot.columns)], labels=sorted(pivot.columns), alpha=0.85)
            plt.legend(loc="upper left", fontsize=8)
            plt.title("Распределение портфеля по бакетам DPD")
            plt.ylabel("Доля")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(outdir / "risk_plot_bucket_distribution.png", dpi=150)
            plt.close()
        except Exception:
            pass

    if args.plotly:
        try:
            # Bucket distribution interactive
            fig = px.area(bucket_dist, x="period_month", y="share", color="DPD_bucket", title="DPD bucket distribution")
            fig.write_html(str(outdir / "risk_bucket_distribution.html"))

            # Cure/default/payment ratios
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=cure["period_month"], y=cure["cure_rate"], name="Cure", mode="lines+markers"))
            fig2.add_trace(go.Scatter(x=default_r["period_month"], y=default_r["default_rate"], name="Default", mode="lines+markers"))
            fig2.add_trace(go.Scatter(x=pay["period_month"], y=pay["actual_vs_scheduled"], name="Actual/Scheduled", mode="lines+markers", yaxis="y2"))
            fig2.update_layout(title="Cure / Default / Payment ratios", yaxis2=dict(overlaying='y', side='right'))
            fig2.write_html(str(outdir / "risk_cure_default_payment.html"))
        except Exception:
            pass

        # 2) Roll-rate: по каждому prev_bucket — линии в текущие бакеты
        try:
            for prev in roll["prev_bucket"].dropna().unique().tolist():
                sub = roll[roll["prev_bucket"] == prev]
                pivot = sub.pivot(index="period_month", columns="DPD_bucket", values="rate").fillna(0)
                plt.figure(figsize=(10, 5))
                for col in sorted(pivot.columns):
                    plt.plot(pivot.index, pivot[col], label=f"→ {col}")
                plt.title(f"Roll-rate из бакета {prev}")
                plt.ylabel("Доля")
                plt.grid(True, alpha=0.3)
                plt.legend(loc="upper right", fontsize=8)
                plt.tight_layout()
                fname = f"risk_plot_roll_rate_from_{str(prev).replace('>','gt').replace('+','plus').replace(' ','_').replace('/','_')}.png"
                plt.savefig(outdir / fname, dpi=150)
                plt.close()
        except Exception:
            pass

        # 3) Cure rate
        try:
            plt.figure(figsize=(10, 4))
            plt.plot(cure["period_month"], cure["cure_rate"], marker="o")
            plt.title("Cure rate (возврат в 0 из просрочки)")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(outdir / "risk_plot_cure_rate.png", dpi=150)
            plt.close()
        except Exception:
            pass

        # 4) Default rate
        try:
            plt.figure(figsize=(10, 4))
            plt.plot(default_r["period_month"], default_r["default_rate"], marker="o", color="#d62728")
            plt.title("Default rate")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(outdir / "risk_plot_default_rate.png", dpi=150)
            plt.close()
        except Exception:
            pass

        # 5) Payment ratios
        try:
            plt.figure(figsize=(10, 4))
            plt.plot(pay["period_month"], pay["actual_vs_scheduled"], marker="o")
            plt.title("Отношение фактических к плановым платежам")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(outdir / "risk_plot_actual_vs_scheduled.png", dpi=150)
            plt.close()
        except Exception:
            pass

        # 6) Vintage PD 12m
        try:
            plt.figure(figsize=(10, 4))
            plt.plot(vint["cohort_month"], vint["vintage_pd_12m"], marker="o")
            plt.title("Vintage PD (12m)")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(outdir / "risk_plot_vintage_pd_12m.png", dpi=150)
            plt.close()
        except Exception:
            pass

        # 7) PAR30/60/90
        try:
            plt.figure(figsize=(10, 4))
            plt.plot(par["pm"], par["par30"], label="PAR30")
            plt.plot(par["pm"], par["par60"], label="PAR60")
            plt.plot(par["pm"], par["par90"], label="PAR90")
            plt.title("PAR 30/60/90 (по балансу)")
            plt.grid(True, alpha=0.3)
            plt.legend()
            plt.tight_layout()
            plt.savefig(outdir / "risk_plot_par.png", dpi=150)
            plt.close()
        except Exception:
            pass

        # 8) Stage mix
        try:
            plt.figure(figsize=(10, 5))
            plt.stackplot(stage["pm"], stage["stage1"], stage["stage2"], stage["stage3"], labels=["Stage1","Stage2","Stage3"], alpha=0.85)
            plt.title("IFRS9 Stage mix (proxy)")
            plt.grid(True, alpha=0.3)
            plt.legend(loc="upper left", fontsize=8)
            plt.tight_layout()
            plt.savefig(outdir / "risk_plot_stage_mix.png", dpi=150)
            plt.close()
        except Exception:
            pass

        # Интерпретация-резюме
        try:
            last = bucket_dist["period_month"].max()
            bd_last = bucket_dist[bucket_dist["period_month"] == last]
            share_90 = float(bd_last.loc[bd_last["DPD_bucket"] == "90+", "share"].sum()) if not bd_last.empty else 0.0
            def_last = float(default_r[default_r["period_month"] == last]["default_rate"].sum()) if len(default_r) else 0.0
            cure_last = float(cure[cure["period_month"] == last]["cure_rate"].sum()) if len(cure) else 0.0
            avs_last = float(pay[pay["period_month"] == last]["actual_vs_scheduled"].mean()) if len(pay) else 0.0

            alerts = []
            if share_90 > args.alert_90p:
                alerts.append(f"ALERT: Доля 90+ ({share_90:.2%}) выше порога {args.alert_90p:.2%}")
            if cure_last < args.alert_cure:
                alerts.append(f"ALERT: Cure rate ({cure_last:.2%}) ниже порога {args.alert_cure:.2%}")

            lines = [
                f"Период: {last.date() if hasattr(last, 'date') else last}",
                f"Доля 90+ в портфеле: {share_90:.2%}",
                f"Default rate (последний период): {def_last:.2%}",
                f"Cure rate (последний период): {cure_last:.2%}",
                f"Actual/Scheduled (последний период): {avs_last:.2f}",
                *(alerts or ["ALERTS: OK"])
            ]
            (outdir / "risk_interpretation.txt").write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    main()


