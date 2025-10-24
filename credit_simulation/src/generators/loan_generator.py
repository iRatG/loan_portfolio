from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil
from random import Random
from typing import Dict, List

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .macro_calculator import MacroParams, SeasonalParams, calculate_k_macro, get_seasonal_params


@dataclass
class LoanParamsCfg:
    avg_amount: float
    min_amount: float
    max_amount: float
    avg_term_months: int
    min_term_months: int
    max_term_months: int


def first_day_of_month(dt: date) -> date:
    return date(dt.year, dt.month, 1)


def normal_clamped(rng: Random, mean: float, std: float, min_val: float, max_val: float) -> float:
    val = rng.normalvariate(mean, std)
    return max(min_val, min(max_val, val))


def calculate_monthly_issuance(
    base_monthly_issuance: int,
    macro: MacroParams,
    seasonal: SeasonalParams,
    rng: Random,
) -> int:
    k_macro = calculate_k_macro(macro, alpha_rate=0.08, beta_employment=0.12)
    k_season = seasonal.k_issue
    k_random = rng.uniform(0.9, 1.1)
    n = int(round(base_monthly_issuance * k_macro * k_season * k_random))
    return max(0, n)


def calculate_loan_amount(cfg: LoanParamsCfg, seasonal: SeasonalParams, rng: Random) -> float:
    base = cfg.avg_amount * (1.0 + rng.normalvariate(0.0, 0.3))
    amount = base * seasonal.k_amount
    return float(max(cfg.min_amount, min(cfg.max_amount, amount)))


def calculate_interest_rate(macro: MacroParams, rng: Random) -> float:
    margin_base = 0.05
    rate = macro.rate_cbr / 100.0 + margin_base + rng.normalvariate(0.0, 0.02)
    return float(max(0.0, rate))


def calculate_term_months(cfg: LoanParamsCfg, rng: Random) -> int:
    base = cfg.avg_term_months * (1.0 + rng.normalvariate(0.0, 0.2))
    term = int(round(base))
    return max(cfg.min_term_months, min(cfg.max_term_months, term))


def spread_over_month(n: int, year: int, month: int, rng: Random) -> List[date]:
    start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    days = (next_month - start).days
    return [start + timedelta(days=rng.randrange(0, days)) for _ in range(n)]


def generate_loans_for_month(
    n_loans: int,
    year: int,
    month: int,
    macro: MacroParams,
    seasonal: SeasonalParams,
    cfg: LoanParamsCfg,
    rng: Random,
    batch_id: str,
) -> List[Dict]:
    issue_dates = spread_over_month(n_loans, year, month, rng)
    loans: List[Dict] = []
    for dt in issue_dates:
        amount = calculate_loan_amount(cfg, seasonal, rng)
        rate = calculate_interest_rate(macro, rng)
        term = calculate_term_months(cfg, rng)
        loans.append(
            {
                "issue_date": dt.isoformat(),
                "cohort_month": first_day_of_month(dt).isoformat(),
                "loan_amount": round(amount, 2),
                "interest_rate": round(rate * 100.0, 2),  # store as percent
                "term_months": term,
                "product_type": "consumer_loan",
                "macro_rate_cbr": round(macro.rate_cbr, 2),
                "macro_employment_rate": round(macro.employment_rate, 2),
                "macro_unemployment_rate": round(macro.unemployment_rate, 2),
                "macro_index": round(macro.macro_index, 2),
                "season_k_issue": round(seasonal.k_issue, 2),
                "season_k_amount": round(seasonal.k_amount, 2),
                "season_period_name": seasonal.period_name,
                "batch_id": batch_id,
            }
        )
    return loans


def save_loans_to_db(engine: Engine, loans: List[Dict]) -> int:
    if not loans:
        return 0
    cols = [
        "issue_date",
        "cohort_month",
        "loan_amount",
        "interest_rate",
        "term_months",
        "product_type",
        "macro_rate_cbr",
        "macro_employment_rate",
        "macro_unemployment_rate",
        "macro_index",
        "season_k_issue",
        "season_k_amount",
        "season_period_name",
        "batch_id",
    ]
    df = pd.DataFrame(loans, columns=cols)
    placeholders = ", ".join([":" + c for c in cols])
    sql = (
        "INSERT INTO loan_issue (" + ", ".join(cols) + ") VALUES (" + placeholders + ")"
    )
    with engine.begin() as conn:
        conn.execute(text(sql), df.to_dict(orient="records"))
    return len(loans)
