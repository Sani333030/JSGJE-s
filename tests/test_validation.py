from je_tool.validation import LineInput, validate_approval, validate_entry

ACCOUNTS = {
    1: {"id": 1, "code": "1010", "name": "Cash", "type": "Asset", "is_contra": 0},
    2: {"id": 2, "code": "1400", "name": "Prepaid Insurance", "type": "Asset", "is_contra": 0},
    3: {"id": 3, "code": "2100", "name": "Accrued Expenses", "type": "Liability", "is_contra": 0},
    4: {"id": 4, "code": "5100", "name": "Utilities Expense", "type": "Expense", "is_contra": 0},
    5: {"id": 5, "code": "1500", "name": "Equipment", "type": "Asset", "is_contra": 0},
    6: {"id": 6, "code": "1510", "name": "Accumulated Depreciation", "type": "Asset", "is_contra": 1},
    7: {"id": 7, "code": "5300", "name": "Depreciation Expense", "type": "Expense", "is_contra": 0},
}


def base_kwargs(**overrides):
    kwargs = dict(
        entry_date="2026-01-31",
        description="Test entry",
        reason="Because testing requires a reason.",
        preparer_id=1,
        accounts_by_id=ACCOUNTS,
    )
    kwargs.update(overrides)
    return kwargs


def test_balanced_entry_is_valid():
    result = validate_entry(
        **base_kwargs(
            lines=[LineInput(4, "debit", 450.0), LineInput(3, "credit", 450.0)],
            entry_type="accrual",
        )
    )
    assert result.is_valid
    assert result.warnings == []


def test_unbalanced_entry_is_rejected():
    result = validate_entry(
        **base_kwargs(lines=[LineInput(1, "debit", 500.0), LineInput(2, "credit", 400.0)])
    )
    assert not result.is_valid
    assert any("must equal credits" in e for e in result.errors)


def test_missing_reason_is_rejected():
    result = validate_entry(
        **base_kwargs(reason="   ", lines=[LineInput(1, "debit", 100.0), LineInput(2, "credit", 100.0)])
    )
    assert not result.is_valid
    assert any("Reason" in e for e in result.errors)


def test_missing_debit_or_credit_side_is_rejected():
    result = validate_entry(**base_kwargs(lines=[LineInput(1, "debit", 100.0), LineInput(2, "debit", 100.0)]))
    assert not result.is_valid
    assert any("credit line is required" in e for e in result.errors)


def test_depreciation_crediting_non_contra_asset_warns():
    result = validate_entry(
        **base_kwargs(
            lines=[LineInput(7, "debit", 200.0), LineInput(5, "credit", 200.0)],  # credits Equipment, not Accum. Dep.
            entry_type="depreciation",
        )
    )
    assert result.is_valid  # warnings never block
    assert any("contra-asset" in w for w in result.warnings)


def test_depreciation_crediting_contra_asset_is_clean():
    result = validate_entry(
        **base_kwargs(
            lines=[LineInput(7, "debit", 200.0), LineInput(6, "credit", 200.0)],  # correctly credits Accum. Dep.
            entry_type="depreciation",
        )
    )
    assert result.is_valid
    assert result.warnings == []


def test_routine_balance_reducing_entries_do_not_warn():
    # Paying down an accrued liability: debiting a credit-normal account is
    # completely routine and should never be flagged.
    result = validate_entry(
        **base_kwargs(lines=[LineInput(3, "debit", 450.0), LineInput(1, "credit", 450.0)], entry_type="standard")
    )
    assert result.is_valid
    assert result.warnings == []


def test_approval_requires_different_reviewer():
    result = validate_approval(preparer_id=1, reviewer_id=1)
    assert not result.is_valid

    result = validate_approval(preparer_id=1, reviewer_id=2)
    assert result.is_valid
