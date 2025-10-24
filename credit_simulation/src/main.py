from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from random import Random
from typing import Dict, List

from sqlalchemy.engine import Engine

from utils.config_loader import ensure_dir, get_project_root, load_config, save_json
from utils.validators import validate_config
from database.connection import get_engine, run_ddl_sqlite
from database.models import MacroLogRecord, aggregate_report_counts, upsert_macro_log
from generators.macro_calculator import (
    MacroParams,
    calculate_k_macro,
    get_seasonal_params,
    interpolate_monthly_macro,
    load_macro_reference,
    load_season_reference,
    month_key,
)
from generators.loan_generator import (
    LoanParamsCfg,
    calculate_monthly_issuance,
    generate_loans_for_month,
    save_loans_to_db,
)


def setup_logging(project_root: Path) -> None:
    logs_dir = project_root / "logs"
    ensure_dir(logs_dir)
    log_path = logs_dir / "generation.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> None:
    project_root = get_project_root(Path(__file__).resolve())
    setup_logging(project_root)
    logger = logging.getLogger("main")

    # Load config and refs
    cfg_path = project_root / "credit_simulation" / "config" / "config.toml"
    season_path = project_root / "credit_simulation" / "config" / "season_reference.json"
    macro_path = project_root / "credit_simulation" / "config" / "macro_reference.json"

    cfg = load_config(cfg_path)
    validate_config(cfg)

    rng = Random(cfg["simulation"]["random_seed"])

    # DB
    engine: Engine = get_engine(cfg["database"]["connection_string"])
    run_ddl_sqlite(engine, project_root)

    # Load anchors and interpolate
    anchors = load_macro_reference(macro_path)
    seasons = load_season_reference(season_path)

    start_year = int(cfg["simulation"]["start_year"]) ; end_year = int(cfg["simulation"]["end_year"]) 
    monthly_macro = interpolate_monthly_macro(anchors, start_year, end_year)

    loan_cfg = LoanParamsCfg(
        avg_amount=float(cfg["loan_parameters"]["avg_amount"]),
        min_amount=float(cfg["loan_parameters"]["min_amount"]),
        max_amount=float(cfg["loan_parameters"]["max_amount"]),
        avg_term_months=int(cfg["loan_parameters"]["avg_term_months"]),
        min_term_months=int(cfg["loan_parameters"]["min_term_months"]),
        max_term_months=int(cfg["loan_parameters"]["max_term_months"]),
    )

    base_monthly_issuance = int(cfg["simulation"]["base_monthly_issuance"])

    total_inserted = 0
    batch_id = f"{start_year}-{end_year}"
    report_stats: Dict[str, int] = {}

    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            dt = date(y, m, 1)
            key = month_key(y, m)
            macro: MacroParams = monthly_macro[key]
            seasonal = get_seasonal_params(seasons, dt)

            n_loans = calculate_monthly_issuance(
                base_monthly_issuance=base_monthly_issuance,
                macro=macro,
                seasonal=seasonal,
                rng=rng,
            )

            loans = generate_loans_for_month(
                n_loans=n_loans,
                year=y,
                month=m,
                macro=macro,
                seasonal=seasonal,
                cfg=loan_cfg,
                rng=rng,
                batch_id=batch_id,
            )

            inserted = save_loans_to_db(engine, loans)
            total_inserted += inserted

            k_macro = calculate_k_macro(
                macro,
                alpha_rate=float(cfg["sensitivity"]["alpha_rate"]),
                beta_employment=float(cfg["sensitivity"]["beta_employment"]),
            )
            upsert_macro_log(
                engine,
                MacroLogRecord(
                    year_month=key,
                    rate_cbr=round(macro.rate_cbr, 2),
                    employment_rate=round(macro.employment_rate, 2),
                    unemployment_rate=round(macro.unemployment_rate, 2),
                    macro_index=round(macro.macro_index, 2),
                    k_macro_calculated=round(k_macro, 4),
                    source="interpolated",
                ),
            )

            logging.getLogger("generation").debug(
                "Generated %d loans for %04d-%02d (k_macro=%.3f, season=%s)",
                inserted,
                y,
                m,
                k_macro,
                seasonal.period_name,
            )

    report_dir = project_root / "logs"
    ensure_dir(report_dir)
    report = {
        "inserted_total": total_inserted,
        **aggregate_report_counts(engine),
    }
    save_json(report_dir / "generation_report.json", report)

    logger.info("Generation complete: %d loans", total_inserted)


if __name__ == "__main__":
    main()
