from je_tool.prepaid import check_recognition, remaining_balance


def schedule(periods_recognized=0, total_amount=1200.0, monthly_amount=100.0, periods_total=12):
    return {
        "description": "Test prepaid schedule",
        "total_amount": total_amount,
        "monthly_amount": monthly_amount,
        "periods_total": periods_total,
        "periods_recognized": periods_recognized,
    }


def test_remaining_balance_before_any_recognition():
    assert remaining_balance(schedule()) == 1200.0


def test_remaining_balance_after_some_recognition():
    assert remaining_balance(schedule(periods_recognized=3)) == 900.0


def test_recognition_within_remaining_is_allowed():
    assert check_recognition(schedule(periods_recognized=3), 100.0) is None


def test_recognition_exceeding_remaining_is_blocked():
    error = check_recognition(schedule(periods_recognized=11), 200.0)  # only 100 left
    assert error is not None
    assert "exceed" in error


def test_recognition_against_fully_recognized_schedule_is_blocked():
    error = check_recognition(schedule(periods_recognized=12), 100.0)
    assert error is not None
    assert "fully recognized" in error
