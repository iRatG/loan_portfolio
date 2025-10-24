from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator


class PaymentPolicy(BaseModel):
    bucket: str
    fractions: List[float] = Field(..., description="[overdue_interest, interest_scheduled, overdue_principal, scheduled_principal]")

    @validator("fractions")
    def four_nonneg(cls, v: List[float]) -> List[float]:
        if len(v) != 4:
            raise ValueError("fractions must have 4 elements")
        if any(x < 0 for x in v):
            raise ValueError("fractions must be non-negative")
        return v


class CollectionsSettings(BaseModel):
    bucket_priority: str = Field("max")
    dpd_mode: str = Field("age_oldest")
    escalation_after_n_missed_principal: int = Field(3, ge=0)
    p_cure_by_bucket: Dict[str, float]
    typical_cure_multiple: float
    intent_worsen_multiplier_2014_2015: float = 0.85
    payment_policy_by_bucket: Dict[str, List[float]]


class SimulationSettings(BaseModel):
    start_year: int
    end_year: int
    base_monthly_issuance: int
    random_seed: int


class LoanParameters(BaseModel):
    min_amount: float
    max_amount: float
    avg_amount: float
    min_term_months: int
    max_term_months: int
    avg_term_months: int


class Sensitivity(BaseModel):
    alpha_rate: float
    beta_employment: float
    gamma_macro: float


class DatabaseSettings(BaseModel):
    connection_string: str
    table_name: str


class AppSettings(BaseModel):
    simulation: SimulationSettings
    loan_parameters: LoanParameters
    sensitivity: Sensitivity
    database: DatabaseSettings
    collections: CollectionsSettings


