from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class MacroLogRecord:
    year_month: str
    rate_cbr: float
    employment_rate: float
    unemployment_rate: float
    macro_index: float
    k_macro_calculated: float
    source: str


def upsert_macro_log(engine: Engine, rec: MacroLogRecord) -> None:
    sql = (
        "INSERT INTO macro_params_log (year_month, rate_cbr, employment_rate, unemployment_rate, macro_index, k_macro_calculated, source) "
        "VALUES (:year_month, :rate_cbr, :employment_rate, :unemployment_rate, :macro_index, :k_macro_calculated, :source) "
        "ON CONFLICT(year_month) DO UPDATE SET "
        "rate_cbr=excluded.rate_cbr, employment_rate=excluded.employment_rate, unemployment_rate=excluded.unemployment_rate, "
        "macro_index=excluded.macro_index, k_macro_calculated=excluded.k_macro_calculated, source=excluded.source"
    )
    # SQLite UPSERT requires a unique index on year_month (present in DDL)
    with engine.begin() as conn:
        conn.execute(
            text(sql),
            {
                "year_month": rec.year_month,
                "rate_cbr": rec.rate_cbr,
                "employment_rate": rec.employment_rate,
                "unemployment_rate": rec.unemployment_rate,
                "macro_index": rec.macro_index,
                "k_macro_calculated": rec.k_macro_calculated,
                "source": rec.source,
            },
        )


def aggregate_report_counts(engine: Engine) -> Dict[str, int]:
    with engine.begin() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM loan_issue")).scalar_one()
        by_year = conn.execute(
            text("SELECT substr(issue_date,1,4) as y, COUNT(*) FROM loan_issue GROUP BY y ORDER BY y")
        ).all()
    return {
        "total_loans": int(total),
        **{f"year_{row[0]}": int(row[1]) for row in by_year},
    }
