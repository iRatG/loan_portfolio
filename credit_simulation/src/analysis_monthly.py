from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_loans_df(conn_str: str) -> pd.DataFrame:
    engine = create_engine(conn_str, future=True)
    with engine.begin() as conn:
        df = pd.read_sql(
            text(
                """
                SELECT
                    cohort_month,
                    issue_date,
                    loan_amount,
                    interest_rate,
                    term_months,
                    product_type,
                    season_period_name,
                    macro_rate_cbr,
                    macro_employment_rate,
                    macro_unemployment_rate,
                    macro_index
                FROM loan_issue
                """
            ),
            conn,
            parse_dates=["issue_date", "cohort_month"],
        )
    return df


def compute_monthly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Нормализуем ключ месяца как YYYY-MM-01
    if df["cohort_month"].dtype == object:
        df["month"] = pd.to_datetime(df["cohort_month"]).dt.to_period("M").dt.to_timestamp()
    else:
        df["month"] = df["cohort_month"].dt.to_period("M").dt.to_timestamp()

    grp = df.groupby("month", as_index=False)

    def pct(s: pd.Series) -> pd.Series:
        return pd.Series({
            "p25": s.quantile(0.25),
            "p50": s.quantile(0.50),
            "p75": s.quantile(0.75),
            "p90": s.quantile(0.90),
        })

    agg_amount = grp["loan_amount"].agg(["sum", "mean", "median", "count"]).rename(
        columns={"sum": "amount_sum", "mean": "amount_avg", "median": "amount_med", "count": "loans_cnt"}
    )
    agg_ir = grp["interest_rate"].mean().rename(columns={"interest_rate": "rate_avg"})
    agg_term = grp["term_months"].mean().rename(columns={"term_months": "term_avg"})

    # Перцентили корректно через quantile + unstack
    pct_amount = (
        df.groupby("month")["loan_amount"]
        .quantile([0.25, 0.50, 0.75, 0.90])
        .unstack()
        .reset_index()
        .rename(columns={0.25: "amount_p25", 0.5: "amount_p50", 0.75: "amount_p75", 0.9: "amount_p90"})
    )

    base = agg_amount.merge(agg_ir, on="month").merge(agg_term, on="month").merge(pct_amount, on="month")

    # MoM, YoY по ключевым метрикам
    base = base.sort_values("month").reset_index(drop=True)
    for col in ["amount_sum", "loans_cnt", "amount_avg", "rate_avg"]:
        base[f"{col}_mom"] = base[col].pct_change()
        base[f"{col}_yoy"] = base[col].pct_change(12)

    # Бинирование по суммам чеков (по всем данным)
    bins = pd.qcut(df["loan_amount"], q=5, duplicates="drop")
    df["amount_bin"] = bins
    bin_stats = (
        df.groupby(["month", "amount_bin"]).size().rename("cnt").reset_index()
    )
    bin_pivot = bin_stats.pivot(index="month", columns="amount_bin", values="cnt").fillna(0)
    # Нормируем доли
    bin_pivot = bin_pivot.div(bin_pivot.sum(axis=1), axis=0).reset_index()
    # Переименуем колонки более читабельно
    bin_pivot = bin_pivot.rename(columns=lambda c: f"bin_share_{c}" if c != "month" else c)

    res = base.merge(bin_pivot, on="month", how="left")
    return res


def compute_slices(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = df.copy()
    if df["cohort_month"].dtype == object:
        df["month"] = pd.to_datetime(df["cohort_month"]).dt.to_period("M").dt.to_timestamp()
    else:
        df["month"] = df["cohort_month"].dt.to_period("M").dt.to_timestamp()

    # Срез по сезону
    by_season = (
        df.groupby(["month", "season_period_name"]).agg(
            amount_sum=("loan_amount", "sum"),
            loans_cnt=("loan_amount", "count"),
            amount_avg=("loan_amount", "mean"),
            rate_avg=("interest_rate", "mean"),
        ).reset_index()
    )

    # Срез по продуктам (если появятся разные типы)
    by_product = (
        df.groupby(["month", "product_type"]).agg(
            amount_sum=("loan_amount", "sum"),
            loans_cnt=("loan_amount", "count"),
            amount_avg=("loan_amount", "mean"),
            rate_avg=("interest_rate", "mean"),
        ).reset_index()
    )

    # Корреляционный срез с макро (усреднение по месяцу)
    by_macro = (
        df.groupby("month").agg(
            macro_rate_cbr_avg=("macro_rate_cbr", "mean"),
            macro_employment_rate_avg=("macro_employment_rate", "mean"),
            macro_unemployment_rate_avg=("macro_unemployment_rate", "mean"),
            macro_index_avg=("macro_index", "mean"),
        ).reset_index()
    )

    return {
        "by_season": by_season,
        "by_product": by_product,
        "by_macro": by_macro,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Monthly risk analytics for credit_sim.db")
    parser.add_argument(
        "--conn",
        default="sqlite:///credit_sim.db",
        help="SQLAlchemy connection string (default: sqlite:///credit_sim.db)",
    )
    parser.add_argument(
        "--outdir",
        default="logs",
        help="Output directory for CSV files (default: logs)",
    )
    parser.add_argument(
        "--plots",
        action="store_true",
        help="Generate PNG charts into outdir",
    )
    args = parser.parse_args()

    df = load_loans_df(args.conn)
    if df.empty:
        print("loan_issue пуста. Сначала сгенерируйте данные (запустите main.py).")
        return

    monthly = compute_monthly_metrics(df)
    slices = compute_slices(df)

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(out_dir / "monthly_risk_metrics.csv", index=False)
    for k, v in slices.items():
        v.to_csv(out_dir / f"monthly_{k}.csv", index=False)

    # Краткий префикс в консоль
    print("Записано:")
    print(out_dir / "monthly_risk_metrics.csv")
    for k in slices:
        print(out_dir / f"monthly_{k}.csv")

    if args.plots:
        make_plots(monthly, slices, out_dir)
        print("Графики сохранены в:")
        for fname in [
            "plot_amount_sum.png",
            "plot_loans_cnt.png",
            "plot_amount_avg.png",
            "plot_rate_avg.png",
            "plot_mom_yoy.png",
            "plot_bin_shares.png",
            "plot_macro_rate_vs_amount.png",
        ]:
            print(out_dir / fname)


def _safe_plot_line(df: pd.DataFrame, x: str, y: str, title: str, ylabel: str, out_path: Path) -> None:
    if y not in df.columns:
        return
    plt.figure(figsize=(10, 4))
    plt.plot(df[x], df[y], marker="o")
    plt.grid(True, alpha=0.3)
    plt.title(title)
    plt.xlabel("month")
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()


def make_plots(monthly: pd.DataFrame, slices: dict[str, pd.DataFrame], out_dir: Path) -> None:
    m = monthly.copy()
    # Базовые линии
    _safe_plot_line(m, "month", "amount_sum", "Сумма выдач по месяцам", "RUB", out_dir / "plot_amount_sum.png")
    _safe_plot_line(m, "month", "loans_cnt", "Число кредитов по месяцам", "count", out_dir / "plot_loans_cnt.png")
    _safe_plot_line(m, "month", "amount_avg", "Средний чек по месяцам", "RUB", out_dir / "plot_amount_avg.png")
    _safe_plot_line(m, "month", "rate_avg", "Средняя ставка по месяцам", "%", out_dir / "plot_rate_avg.png")

    # MoM и YoY по сумме выдач
    if {"amount_sum_mom", "amount_sum_yoy"}.issubset(m.columns):
        fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        ax[0].plot(m["month"], m["amount_sum_mom"], marker="o", color="#1f77b4")
        ax[0].axhline(0, color="#999", linewidth=1)
        ax[0].set_title("MoM по сумме выдач")
        ax[0].grid(True, alpha=0.3)
        ax[0].set_ylabel("MoM, доля")
        ax[1].plot(m["month"], m["amount_sum_yoy"], marker="o", color="#ff7f0e")
        ax[1].axhline(0, color="#999", linewidth=1)
        ax[1].set_title("YoY по сумме выдач")
        ax[1].grid(True, alpha=0.3)
        ax[1].set_ylabel("YoY, доля")
        plt.tight_layout()
        plt.savefig(out_dir / "plot_mom_yoy.png", dpi=150)
        plt.close()

    # Доли по бинам суммы
    bin_cols = [c for c in m.columns if c.startswith("bin_share_")]
    if bin_cols:
        plt.figure(figsize=(10, 5))
        y_vals = [m[c].values for c in bin_cols]
        plt.stackplot(m["month"], y_vals, labels=bin_cols, alpha=0.8)
        plt.title("Структура по бинам суммы кредита")
        plt.legend(loc="upper left", fontsize=8)
        plt.grid(True, alpha=0.2)
        plt.tight_layout()
        plt.savefig(out_dir / "plot_bin_shares.png", dpi=150)
        plt.close()

    # Макро: ставка ЦБ против суммы выдач
    by_macro = slices.get("by_macro")
    if isinstance(by_macro, pd.DataFrame) and not by_macro.empty and "macro_rate_cbr_avg" in by_macro.columns:
        j = pd.merge(m[["month", "amount_sum"]], by_macro[["month", "macro_rate_cbr_avg"]], on="month", how="inner")
        if not j.empty:
            plt.figure(figsize=(6, 5))
            plt.scatter(j["macro_rate_cbr_avg"], j["amount_sum"], alpha=0.7)
            plt.xlabel("Средняя ставка ЦБ")
            plt.ylabel("Сумма выдач")
            plt.title("Ставка ЦБ vs Сумма выдач (месячные точки)")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.savefig(out_dir / "plot_macro_rate_vs_amount.png", dpi=150)
            plt.close()


if __name__ == "__main__":
    main()


