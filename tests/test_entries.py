import os

import pytest

from je_tool import accounts, db, employees, entries, organizations, prepaid
from je_tool.validation import LineInput


@pytest.fixture
def two_orgs(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)

    with db.session(db_path) as conn:
        org_a = organizations.add_organization(conn, "Org A")
        org_b = organizations.add_organization(conn, "Org B")

        prep_a = employees.add_employee(conn, org_a, "Preparer A", "preparer")
        rev_a = employees.add_employee(conn, org_a, "Reviewer A", "reviewer")

        cash_a = accounts.add_account(conn, org_a, "1010", "Cash", "Asset")
        ar_a = accounts.add_account(conn, org_a, "1200", "Accounts Receivable", "Asset")
        prepaid_a = accounts.add_account(conn, org_a, "1400", "Prepaid Insurance", "Asset")
        exp_a = accounts.add_account(conn, org_a, "5200", "Insurance Expense", "Expense")

        cash_b = accounts.add_account(conn, org_b, "1010", "Cash", "Asset")

    return {
        "db_path": db_path,
        "org_a": org_a,
        "org_b": org_b,
        "prep_a": prep_a,
        "rev_a": rev_a,
        "cash_a": cash_a,
        "ar_a": ar_a,
        "prepaid_a": prepaid_a,
        "exp_a": exp_a,
        "cash_b": cash_b,
    }


def test_create_entry_persists_lines(two_orgs):
    with db.session(two_orgs["db_path"]) as conn:
        entry_id, result = entries.create_entry(
            conn, org_id=two_orgs["org_a"], entry_date="2026-01-31", description="Test sale",
            reason="Recording a cash sale.", preparer_id=two_orgs["prep_a"],
            lines=[LineInput(two_orgs["cash_a"], "debit", 100.0), LineInput(two_orgs["ar_a"], "credit", 100.0)],
        )
        assert result.is_valid
        assert entry_id is not None
        lines = entries.get_lines(conn, entry_id)
        assert len(lines) == 2


def test_unbalanced_entry_is_never_persisted(two_orgs):
    with db.session(two_orgs["db_path"]) as conn:
        entry_id, result = entries.create_entry(
            conn, org_id=two_orgs["org_a"], entry_date="2026-01-31", description="Broken",
            reason="Should fail.", preparer_id=two_orgs["prep_a"],
            lines=[LineInput(two_orgs["cash_a"], "debit", 100.0), LineInput(two_orgs["ar_a"], "credit", 50.0)],
        )
        assert entry_id is None
        assert not result.is_valid

        remaining = entries.list_entries(conn, two_orgs["org_a"])
        assert remaining == []


def test_account_from_another_org_is_rejected(two_orgs):
    with db.session(two_orgs["db_path"]) as conn:
        entry_id, result = entries.create_entry(
            conn, org_id=two_orgs["org_a"], entry_date="2026-01-31", description="Cross-org leak",
            reason="Should fail.", preparer_id=two_orgs["prep_a"],
            lines=[LineInput(two_orgs["cash_b"], "debit", 100.0), LineInput(two_orgs["ar_a"], "credit", 100.0)],
        )
        assert entry_id is None
        assert any("does not belong to this organization" in e for e in result.errors)


def test_full_lifecycle_draft_to_approved(two_orgs):
    with db.session(two_orgs["db_path"]) as conn:
        entry_id, _ = entries.create_entry(
            conn, org_id=two_orgs["org_a"], entry_date="2026-01-31", description="Test",
            reason="Testing lifecycle.", preparer_id=two_orgs["prep_a"],
            lines=[LineInput(two_orgs["cash_a"], "debit", 100.0), LineInput(two_orgs["ar_a"], "credit", 100.0)],
        )
        assert entries.get_entry(conn, entry_id)["status"] == "draft"

        entries.submit_for_review(conn, entry_id)
        assert entries.get_entry(conn, entry_id)["status"] == "pending_review"

        result = entries.approve_entry(conn, entry_id, two_orgs["rev_a"])
        assert result.is_valid
        assert entries.get_entry(conn, entry_id)["status"] == "approved"


def test_approval_blocked_when_reviewer_is_preparer(two_orgs):
    with db.session(two_orgs["db_path"]) as conn:
        entry_id, _ = entries.create_entry(
            conn, org_id=two_orgs["org_a"], entry_date="2026-01-31", description="Test",
            reason="Testing segregation of duties.", preparer_id=two_orgs["prep_a"],
            lines=[LineInput(two_orgs["cash_a"], "debit", 100.0), LineInput(two_orgs["ar_a"], "credit", 100.0)],
        )
        entries.submit_for_review(conn, entry_id)

        result = entries.approve_entry(conn, entry_id, two_orgs["prep_a"])
        assert not result.is_valid
        assert entries.get_entry(conn, entry_id)["status"] == "pending_review"  # unchanged


def test_prepaid_recognition_updates_schedule_and_blocks_overrecognition(two_orgs):
    with db.session(two_orgs["db_path"]) as conn:
        schedule_id = prepaid.create_schedule(
            conn, two_orgs["org_a"], two_orgs["prepaid_a"], "Test policy",
            total_amount=300.0, monthly_amount=100.0, periods_total=3, start_date="2026-01-01",
        )

        for _ in range(3):
            entry_id, result = entries.create_entry(
                conn, org_id=two_orgs["org_a"], entry_date="2026-01-31", description="Recognize prepaid",
                reason="Monthly recognition.", preparer_id=two_orgs["prep_a"], entry_type="prepaid_recognition",
                lines=[LineInput(two_orgs["exp_a"], "debit", 100.0), LineInput(two_orgs["prepaid_a"], "credit", 100.0)],
                prepaid_schedule_id=schedule_id,
            )
            assert entry_id is not None

        schedule = prepaid.get_schedule(conn, schedule_id)
        assert schedule["periods_recognized"] == 3
        assert prepaid.remaining_balance(schedule) == 0.0

        # A 4th recognition should be blocked -- the schedule is fully amortized
        entry_id, result = entries.create_entry(
            conn, org_id=two_orgs["org_a"], entry_date="2026-02-28", description="Over-recognize prepaid",
            reason="Should fail.", preparer_id=two_orgs["prep_a"], entry_type="prepaid_recognition",
            lines=[LineInput(two_orgs["exp_a"], "debit", 100.0), LineInput(two_orgs["prepaid_a"], "credit", 100.0)],
            prepaid_schedule_id=schedule_id,
        )
        assert entry_id is None
        assert any("fully recognized" in e for e in result.errors)
