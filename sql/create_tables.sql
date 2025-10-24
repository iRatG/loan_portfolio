-- Schema for SQLite based on Technical Specification (loan_issue and macro_params_log)
-- This script adapts PostgreSQL-like definitions to SQLite types and index syntax.

BEGIN TRANSACTION;

-- Main table: loan_issue
CREATE TABLE IF NOT EXISTS loan_issue (
    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_date TEXT NOT NULL,            -- ISO date string YYYY-MM-DD
    cohort_month TEXT NOT NULL,          -- ISO date string (first day of month)
    loan_amount NUMERIC NOT NULL,        -- amount in RUB
    interest_rate NUMERIC NOT NULL,      -- percent, e.g., 12.50
    term_months INTEGER NOT NULL,
    product_type TEXT DEFAULT 'consumer_loan',

    -- Macroeconomic parameters at issuance date
    macro_rate_cbr NUMERIC NOT NULL,
    macro_employment_rate NUMERIC NOT NULL,
    macro_unemployment_rate NUMERIC NOT NULL,
    macro_index NUMERIC NOT NULL,

    -- Seasonal coefficients
    season_k_issue NUMERIC NOT NULL,
    season_k_amount NUMERIC NOT NULL,
    season_period_name TEXT,

    -- Service fields
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    batch_id TEXT
);

-- Indexes for loan_issue
CREATE INDEX IF NOT EXISTS idx_issue_date ON loan_issue(issue_date);
CREATE INDEX IF NOT EXISTS idx_cohort_month ON loan_issue(cohort_month);
CREATE INDEX IF NOT EXISTS idx_batch_id ON loan_issue(batch_id);

-- Reference/log table: macro_params_log
CREATE TABLE IF NOT EXISTS macro_params_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_month TEXT NOT NULL,            -- ISO date string YYYY-MM-01
    rate_cbr NUMERIC,
    employment_rate NUMERIC,
    unemployment_rate NUMERIC,
    macro_index NUMERIC,
    k_macro_calculated NUMERIC,
    source TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Unique constraint for macro_params_log
CREATE UNIQUE INDEX IF NOT EXISTS idx_year_month ON macro_params_log(year_month);

COMMIT;


