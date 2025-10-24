from decimal import Decimal


def test_dpd_aging_progression():
    dpd_days = 0
    # имитация накопления дней при наличии арреаров 4 месяца подряд
    months_days = [31, 30, 31, 30]
    for d in months_days:
        dpd_days += d
    assert dpd_days >= 120  # должно эскалировать до 90+


def test_cure_extra_payment_allocation():
    overdue_interest = Decimal("1000")
    overdue_principal = Decimal("5000")
    interest_scheduled = Decimal("800")
    scheduled_principal = Decimal("2000")
    extra = Decimal("5000")
    pay_left = extra
    # порядок списания: overdue_interest -> interest_scheduled -> overdue_principal -> scheduled_principal
    paid_oi = min(pay_left, overdue_interest); pay_left -= paid_oi
    paid_is = min(pay_left, interest_scheduled); pay_left -= paid_is
    paid_op = min(pay_left, overdue_principal); pay_left -= paid_op
    paid_sp = min(pay_left, scheduled_principal); pay_left -= paid_sp
    # проверяем, что просроченные проценты закрылись полностью
    assert paid_oi == overdue_interest
    # проверяем, что часть overdue_principal погашена
    assert paid_op > 0


