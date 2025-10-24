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


