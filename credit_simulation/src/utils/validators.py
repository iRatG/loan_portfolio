from typing import Dict, Any


def validate_config(cfg: Dict[str, Any]) -> None:
    required_sections = [
        "simulation",
        "loan_parameters",
        "sensitivity",
        "database",
    ]
    for section in required_sections:
        if section not in cfg:
            raise ValueError(f"Missing required config section: {section}")

    sim = cfg["simulation"]
    if sim["start_year"] > sim["end_year"]:
        raise ValueError("start_year must be <= end_year")

    loan = cfg["loan_parameters"]
    if loan["min_amount"] <= 0 or loan["max_amount"] <= 0:
        raise ValueError("Loan amounts must be positive")
    if loan["min_amount"] >= loan["max_amount"]:
        raise ValueError("min_amount must be < max_amount")

    if loan["min_term_months"] < 1 or loan["max_term_months"] < 1:
        raise ValueError("Loan terms must be >= 1 month")
    if loan["min_term_months"] >= loan["max_term_months"]:
        raise ValueError("min_term_months must be < max_term_months")
