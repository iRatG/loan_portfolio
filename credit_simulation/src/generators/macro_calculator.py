from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class MacroParams:
    rate_cbr: float
    employment_rate: float
    unemployment_rate: float
    macro_index: float


@dataclass
class SeasonalParams:
    k_issue: float
    k_amount: float
    period_name: str | None


def month_key(y: int, m: int) -> str:
    return f"{y:04d}-{m:02d}-01"


def load_macro_reference(path: Path) -> Dict[str, MacroParams]:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    anchors: Dict[str, MacroParams] = {}
    for rec in raw.get("macro_data", []):
        y = int(rec["year"]) ; m = int(rec["month"])
        anchors[month_key(y, m)] = MacroParams(
            rate_cbr=float(rec["rate_cbr"]),
            employment_rate=float(rec["employment_rate"]),
            unemployment_rate=float(rec["unemployment_rate"]),
            macro_index=float(rec["macro_index"]),
        )
    return anchors


def interpolate_monthly_macro(
    anchors: Dict[str, MacroParams], start_year: int, end_year: int
) -> Dict[str, MacroParams]:
    # Build time grid
    grid: List[Tuple[str, int]] = []
    idx = 0
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            grid.append((month_key(y, m), idx))
            idx += 1

    # Collect anchor indices and values
    if not anchors:
        raise ValueError("No macro anchors provided")

    keys_sorted = sorted(anchors.keys())
    anchor_indices = []
    values_rate: List[float] = []
    values_emp: List[float] = []
    values_unemp: List[float] = []
    values_macro: List[float] = []

    key_to_idx = {k: i for k, i in grid}

    for k in keys_sorted:
        if k in key_to_idx:
            anchor_indices.append(key_to_idx[k])
            mp = anchors[k]
            values_rate.append(mp.rate_cbr)
            values_emp.append(mp.employment_rate)
            values_unemp.append(mp.unemployment_rate)
            values_macro.append(mp.macro_index)

    if not anchor_indices:
        raise ValueError("Anchors do not overlap simulation period")

    x = np.array([i for _, i in grid], dtype=float)
    xa = np.array(anchor_indices, dtype=float)

    def interp(vals: List[float]) -> np.ndarray:
        va = np.array(vals, dtype=float)
        # Linear interpolation with edge fill
        result = np.interp(x, xa, va)
        return result

    rate = interp(values_rate)
    emp = interp(values_emp)
    unemp = interp(values_unemp)
    macro = interp(values_macro)

    out: Dict[str, MacroParams] = {}
    for (k, i) in grid:
        out[k] = MacroParams(
            rate_cbr=float(rate[i]),
            employment_rate=float(emp[i]),
            unemployment_rate=float(unemp[i]),
            macro_index=float(macro[i]),
        )
    return out


def load_season_reference(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("seasonal_coefficients", [])


def get_seasonal_params(seasons: List[Dict], dt: date) -> SeasonalParams:
    m = dt.month
    d = dt.day
    for period in seasons:
        sm = int(period["start_month"]) ; sd = int(period["start_day"]) ; em = int(period["end_month"]) ; ed = int(period["end_day"]) 
        in_range = False
        if sm < em or (sm == em and sd <= ed):
            in_range = (m > sm or (m == sm and d >= sd)) and (m < em or (m == em and d <= ed))
        else:
            # wrap around year end
            in_range = (m > sm or (m == sm and d >= sd)) or (m < em or (m == em and d <= ed))
        if in_range:
            return SeasonalParams(
                k_issue=float(period.get("k_issue", 1.0)),
                k_amount=float(period.get("k_amount", 1.0)),
                period_name=str(period.get("period_name")) if period.get("period_name") else None,
            )
    return SeasonalParams(k_issue=1.0, k_amount=1.0, period_name=None)


def calculate_k_macro(
    macro: MacroParams,
    alpha_rate: float,
    beta_employment: float,
) -> float:
    k_rate = 1.0 - alpha_rate * (macro.rate_cbr - 8.0) / 8.0
    k_emp = 1.0 + beta_employment * (macro.employment_rate - 94.0) / 94.0
    return float(k_rate * k_emp * macro.macro_index)
