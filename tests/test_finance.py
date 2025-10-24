from decimal import Decimal, ROUND_HALF_UP

from credit_simulation.src.module2_simulator import annuity_payment


def test_annuity_payment_basic():
    # P=100000, annual 12% => monthly=1% => n=12 => expected ~ 8884.88
    p = 100000.0
    r_month = 0.12 / 12.0
    n = 12
    a = annuity_payment(p, r_month, n)
    assert round(a, 2) == 8884.88


def test_annuity_payment_zero_rate():
    p = 120000.0
    a = annuity_payment(p, 0.0, 12)
    assert round(a, 2) == 10000.00


