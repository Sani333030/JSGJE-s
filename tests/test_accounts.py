from je_tool.accounts import normal_balance


def test_asset_and_expense_are_debit_normal():
    assert normal_balance("Asset") == "debit"
    assert normal_balance("Expense") == "debit"


def test_liability_equity_revenue_are_credit_normal():
    assert normal_balance("Liability") == "credit"
    assert normal_balance("Equity") == "credit"
    assert normal_balance("Revenue") == "credit"


def test_contra_flips_normal_balance():
    # Accumulated Depreciation is an Asset-type account but credit-normal
    assert normal_balance("Asset", is_contra=True) == "credit"
    assert normal_balance("Liability", is_contra=True) == "debit"
