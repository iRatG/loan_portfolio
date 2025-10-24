from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from calendar import monthrange
from pathlib import Path
from random import Random
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from credit_simulation.src.utils.config_loader import get_project_root, load_settings
from credit_simulation.src.database.connection import get_engine, run_ddl_sqlite, run_sql_file
from decimal import Decimal, ROUND_HALF_UP, getcontext


DDL_CREDIT_FACT = """
DROP TABLE IF EXISTS credit_fact_history;
CREATE TABLE credit_fact_history (
    loan_id INTEGER NOT NULL,
    period_month TEXT NOT NULL,
    MOB INTEGER NOT NULL,
    balance_principal NUMERIC NOT NULL,
    overdue_principal NUMERIC NOT NULL,
    interest_scheduled NUMERIC NOT NULL,
    overdue_interest NUMERIC NOT NULL,
    scheduled_payment NUMERIC NOT NULL,
    actual_payment NUMERIC NOT NULL,
    DPD_bucket TEXT NOT NULL,
    overdue_days INTEGER NOT NULL,
    status TEXT NOT NULL,
    migration_scenario TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    batch_id TEXT NOT NULL,
    UNIQUE(loan_id, period_month, batch_id)
);
CREATE INDEX IF NOT EXISTS idx_fact_loan ON credit_fact_history(loan_id);
CREATE INDEX IF NOT EXISTS idx_fact_month ON credit_fact_history(period_month);
"""


BUCKETS = ["0", "1-30", "31-60", "61-90", "90+"]


@dataclass
class ProductSpec:
    code: str
    type: str
    base_margin: float
    fee_rate: float


def load_json(path: Path) -> dict:
    """Read JSON file into dict.

    Parameters:
        path: Полный путь к JSON-файлу.

    Returns:
        Словарь с данными JSON.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def first_day_of_month(y: int, m: int) -> date:
    """Вернуть первую дату месяца (YYYY-MM-01)."""
    return date(y, m, 1)


def month_add(y: int, m: int, add: int) -> Tuple[int, int]:
    """Сместить месяц на add и вернуть (год, месяц)."""
    total = (y * 12 + (m - 1)) + add
    ny = total // 12
    nm = total % 12 + 1
    return ny, nm


def annuity_payment(principal: float, monthly_rate: float, term_months: int) -> float:
    """Аннуитетный платёж по классической формуле.

    Формула: A = P * r * (1+r)^n / ((1+r)^n - 1), где
    P — сумма, r — месячная ставка, n — срок в месяцах.
    """
    if monthly_rate == 0:
        return principal / term_months
    k = (monthly_rate * (1 + monthly_rate) ** term_months) / ((1 + monthly_rate) ** term_months - 1)
    return principal * k


def choose_bucket(rng: Random, probs: Dict[str, float]) -> str:
    """Случайный выбор бакета согласно вероятностям (без нормализации)."""
    total = sum(probs.values())
    if total <= 0:
        return "0"
    acc = 0.0
    r = rng.random() * total
    for b, p in probs.items():
        acc += p
        if r <= acc:
            return b
    return list(probs.keys())[-1]


def end_of_month(y: int, m: int) -> date:
    """Вернуть дату последнего дня месяца."""
    last_day = monthrange(y, m)[1]
    return date(y, m, last_day)


def simulate(engine: Engine, project_root: Path, batch_id: str, seed: int = 42) -> None:
    """Основной цикл симуляции операционного факта по всем кредитам.

    Считывает настройки/справочники, создаёт таблицу фактов, моделирует помесячные
    платежи, эйджинг просрочки, cure/default и записывает историю в БД.
    """
    logger = logging.getLogger("module2")
    rng = Random(seed)

    # DDL: создаём таблицу фактов из SQL файла
    run_sql_file(engine, project_root / "sql" / "create_fact_tables.sql")

    # Load refs
    cfg_dir = project_root / "credit_simulation" / "config"
    settings = load_settings(cfg_dir / "config.toml")
    coll = settings.collections
    bucket_priority = coll.bucket_priority
    dpd_mode = coll.dpd_mode
    escalation_after = coll.escalation_after_n_missed_principal
    p_cure = coll.p_cure_by_bucket
    typical_cure_multiple = coll.typical_cure_multiple
    intent_worsen_multiplier_2014_2015 = coll.intent_worsen_multiplier_2014_2015
    policy = coll.payment_policy_by_bucket
    migration = load_json(cfg_dir / "migration_matrix.json")
    products = load_json(cfg_dir / "product_reference.json")
    noise_ref = load_json(cfg_dir / "noise_reference.json")
    season_ref = load_json(cfg_dir / "season_reference.json")

    # Load loans
    with engine.begin() as conn:
        loans = pd.read_sql(
            text("SELECT loan_id, issue_date, cohort_month, loan_amount, interest_rate, term_months, product_type, season_k_issue, season_k_amount, season_period_name, macro_rate_cbr, macro_employment_rate, macro_unemployment_rate, macro_index, batch_id FROM loan_issue"),
            conn,
            parse_dates=["issue_date", "cohort_month"],
        )

    if loans.empty:
        logger.warning("loan_issue пуст — запустите модуль 1 (main.py)")
        return

    facts: List[dict] = []

    # Настройка точности Decimal
    getcontext().prec = 28
    TWO = Decimal("0.01")

    def D(x) -> Decimal:
        return Decimal(str(x))

    for _, row in loans.iterrows():
        loan_id = int(row["loan_id"])
        principal: Decimal = D(row["loan_amount"]).quantize(TWO, ROUND_HALF_UP)
        rate_percent: Decimal = D(row["interest_rate"])  # годовые проценты, например 18.50
        term = int(row["term_months"])
        prod_code = str(row["product_type"]) or "consumer_loan"
        season_factor = float(row["season_k_issue"])  # прокси
        macro_rate = float(row["macro_rate_cbr"])
        start_y = int(row["cohort_month"].year)
        start_m = int(row["cohort_month"].month)

        # Месячная ставка как доля
        monthly_rate: Decimal = (rate_percent / Decimal("100")) / Decimal("12")
        # Константный аннуитетный платёж на весь срок
        if monthly_rate == 0:
            sched_payment_const: Decimal = (principal / Decimal(term)).quantize(TWO, ROUND_HALF_UP)
        else:
            r = monthly_rate
            k = (r * (Decimal(1) + r) ** term) / (((Decimal(1) + r) ** term) - Decimal(1))
            sched_payment_const = (principal * k).quantize(TWO, ROUND_HALF_UP)
        mob = 0
        bucket_for_migration = "0"
        balance_principal: Decimal = principal
        overdue_principal: Decimal = Decimal("0")
        overdue_interest: Decimal = Decimal("0")
        status = "active"
        dpd_days = 0

        while mob < term and status == "active" and balance_principal > Decimal("0.01"):
            cur_y, cur_m = month_add(start_y, start_m, mob)
            period = end_of_month(cur_y, cur_m)

            # Migration: по году (используем фактический прошлый бакет как from)
            year_key = str(cur_y)
            yearly = migration.get("yearly", {})
            base_probs = yearly.get(year_key, {}).get(bucket_for_migration, {"0": 1.0})
            probs = dict(base_probs)

            # Season impact (простая мультипликативная корректировка)
            probs = {b: p * season_factor for b, p in probs.items()}

            # Macro impact: рост ставки ЦБ повышает шанс ухудшения статуса
            worsen = ["1-30", "31-60", "61-90", "90+"]
            for b in worsen:
                if b in probs:
                    probs[b] *= (1.0 + max(0.0, (macro_rate - 10.0)) / 50.0)
            # Ослабляем ухудшения в 2014–2015
            if cur_y in (2014, 2015):
                for b in worsen:
                    if b in probs:
                        probs[b] *= intent_worsen_multiplier_2014_2015

            # Расчет платежа и аллокация (на конец месяца)
            interest_scheduled: Decimal = (balance_principal * monthly_rate).quantize(TWO, ROUND_HALF_UP)
            scheduled_principal: Decimal = max(Decimal("0"), min(balance_principal, (sched_payment_const - interest_scheduled)))

            # Noise scenarios (упрощённо)
            if rng.random() < noise_ref["noise"]["full_early_repay_prob"]:
                intent_bucket = "0"
                scenario = "early_repay"
                actual: Decimal = balance_principal + overdue_principal + overdue_interest + interest_scheduled
                paid_oi = overdue_interest
                paid_is = interest_scheduled
                paid_op = overdue_principal
                paid_sp = balance_principal
                overdue_interest = Decimal("0")
                overdue_principal = Decimal("0")
                balance_principal = Decimal("0")
                status = "repaid"
            else:
                intent_bucket = choose_bucket(rng, probs)
                scenario = "base"

                # Политика оплаты по бакету из конфига (fallback по умолчанию)
                policy_vec = policy.get(intent_bucket)
                if policy_vec and len(policy_vec) == 4:
                    frac_oi, frac_is, frac_op, frac_sp = [Decimal(str(x)) for x in policy_vec]
                else:
                    if intent_bucket == "0":
                        frac_oi, frac_is, frac_op, frac_sp = Decimal("1"), Decimal("1"), Decimal("1"), Decimal("1")
                    elif intent_bucket == "1-30":
                        frac_oi, frac_is, frac_op, frac_sp = Decimal("1"), Decimal("1"), Decimal("0"), Decimal("0")
                    elif intent_bucket == "31-60":
                        frac_oi, frac_is, frac_op, frac_sp = Decimal("0.5"), Decimal("0"), Decimal("0"), Decimal("0")
                    else:
                        frac_oi, frac_is, frac_op, frac_sp = Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")

                due_total: Decimal = overdue_interest + interest_scheduled + overdue_principal + scheduled_principal
                target_pay = (overdue_interest * frac_oi + interest_scheduled * frac_is +
                              overdue_principal * frac_op + scheduled_principal * frac_sp)
                actual: Decimal = min(due_total, target_pay.quantize(TWO, ROUND_HALF_UP))

                # Аллокация платежа: проценты (overdue -> текущие) -> проср. осн. -> текущее осн.
                pay_left = actual
                paid_oi = min(pay_left, overdue_interest); pay_left -= paid_oi
                paid_is = min(pay_left, interest_scheduled); pay_left -= paid_is
                paid_op = min(pay_left, overdue_principal); pay_left -= paid_op
                paid_sp = min(pay_left, scheduled_principal); pay_left -= paid_sp

                # Обновляем просрочки
                overdue_interest = max(Decimal("0"), overdue_interest - paid_oi)
                interest_unpaid = max(Decimal("0"), interest_scheduled - paid_is)
                overdue_interest += interest_unpaid

                overdue_principal = max(Decimal("0"), overdue_principal - paid_op)
                scheduled_principal_unpaid = max(Decimal("0"), scheduled_principal - paid_sp)
                overdue_principal += scheduled_principal_unpaid

                # Обновляем основной долг
                principal_paid_total = paid_op + paid_sp
                balance_principal = max(Decimal("0"), balance_principal - principal_paid_total)

            # Cure: вероятность и размер (сверху базового платежа поведения)
            if (overdue_principal > 0 or overdue_interest > 0) and intent_bucket != "0":
                prob = float(p_cure.get(intent_bucket, 0.0))
                if rng.random() < prob:
                    extra = (sched_payment_const * Decimal(str(typical_cure_multiple))).quantize(TWO, ROUND_HALF_UP)
                    pay_left = extra
                    paid_oi = min(pay_left, overdue_interest); pay_left -= paid_oi; overdue_interest -= paid_oi
                    paid_op = min(pay_left, overdue_principal); pay_left -= paid_op; overdue_principal -= paid_op
                    if pay_left > 0:
                        paid_is = min(pay_left, interest_scheduled); pay_left -= paid_is
                        paid_sp = min(pay_left, scheduled_principal); pay_left -= paid_sp
                        # отражаем доп.платёж в actual
                        actual += (extra - pay_left)

            # DPD-эйджинг по самой старой копейке
            fact_bucket = "0"
            if overdue_principal > 0 or overdue_interest > 0:
                days_in_month = monthrange(cur_y, cur_m)[1]
                dpd_days += days_in_month
                if dpd_days <= 30:
                    fact_bucket = "1-30"
                elif dpd_days <= 60:
                    fact_bucket = "31-60"
                elif dpd_days <= 90:
                    fact_bucket = "61-90"
                else:
                    fact_bucket = "90+"
            else:
                dpd_days = 0
                fact_bucket = "0"

            # Эскалация при пропусках principal
            missed_principal = (scheduled_principal - paid_sp) > 0
            if missed_principal:
                miss_count = 1
            else:
                miss_count = 0

            # Финальный бакет: приоритет по правилу
            order = {"0": 0, "1-30": 1, "31-60": 2, "61-90": 3, "90+": 4}
            if bucket_priority == "intent":
                final_bucket = intent_bucket
            elif bucket_priority == "fact":
                final_bucket = fact_bucket
            else:
                final_bucket = intent_bucket if order[intent_bucket] > order[fact_bucket] else fact_bucket

            if final_bucket == "0":
                dpd_days = 0
            else:
                # Приоритет age_oldest: не ограничиваем верхней границей бакета
                pass
            overdue_days = dpd_days

            # Правило дефолта: если бакет 90+
            if final_bucket == "90+" and status == "active":
                status = "default"

            facts.append(
                {
                    "loan_id": loan_id,
                    "period_month": period.strftime("%Y-%m-%d"),
                    "MOB": mob,
                    "DPD_bucket": final_bucket,
                    "overdue_days": overdue_days,
                    "balance_principal": float(balance_principal.quantize(TWO, ROUND_HALF_UP)),
                    "overdue_principal": float(overdue_principal.quantize(TWO, ROUND_HALF_UP)),
                    "interest_scheduled": float(interest_scheduled.quantize(TWO, ROUND_HALF_UP)),
                    "overdue_interest": float(overdue_interest.quantize(TWO, ROUND_HALF_UP)),
                    "scheduled_payment": float(sched_payment_const.quantize(TWO, ROUND_HALF_UP)),
                    "actual_payment": float(actual.quantize(TWO, ROUND_HALF_UP)),
                    "status": status,
                    "migration_scenario": scenario,
                    "batch_id": batch_id,
                }
            )

            # Обновляем бакет для подачи в матрицу на следующий месяц
            bucket_for_migration = final_bucket
            mob += 1

    # Batch insert
    if facts:
        df_facts = pd.DataFrame(facts)
        with engine.begin() as conn:
            df_facts.to_sql("credit_fact_history", conn, if_exists="append", index=False)


def main() -> None:
    """CLI-обёртка: читает строку подключения, применяет базовый DDL и запускает симуляцию."""
    project_root = get_project_root(Path(__file__).resolve())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Reuse existing DB connection string from config
    cfg_path = project_root / "credit_simulation" / "config" / "config.toml"
    cfg_text = cfg_path.read_text(encoding="utf-8")
    conn_str = None
    for line in cfg_text.splitlines():
        if line.strip().startswith("connection_string"):
            conn_str = line.split("=", 1)[1].strip().strip('"')
            break
    if not conn_str:
        raise RuntimeError("connection_string not found in config.toml")

    engine = get_engine(conn_str)
    # Ensure base DDL applied (loan_issue, refs)
    run_ddl_sqlite(engine, project_root)

    simulate(engine, project_root, batch_id="module2")


if __name__ == "__main__":
    main()


