"""
Journal entry creation, retrieval, and the approval workflow -- the layer
that ties the chart of accounts, validation, and prepaid schedules
together into one operation per request, scoped to one organization at a
time.
"""
from __future__ import annotations

import sqlite3

from . import prepaid
from .accounts import get_account, list_accounts
from .validation import LineInput, ValidationResult, validate_approval, validate_entry


def create_entry(
    conn: sqlite3.Connection,
    *,
    org_id: int,
    entry_date: str,
    description: str,
    reason: str,
    preparer_id: int,
    lines: list[LineInput],
    entry_type: str = "standard",
    supporting_reference: str | None = None,
    prepaid_schedule_id: int | None = None,
) -> tuple[int | None, ValidationResult]:
    accounts_by_id = {a["id"]: a for a in list_accounts(conn, org_id)}

    for line in lines:
        account = accounts_by_id.get(line.account_id)
        if account is None or account["org_id"] != org_id:
            result = ValidationResult()
            result.errors.append(f"Account id {line.account_id} does not belong to this organization.")
            return None, result

    result = validate_entry(
        entry_date=entry_date,
        description=description,
        reason=reason,
        preparer_id=preparer_id,
        lines=lines,
        accounts_by_id=accounts_by_id,
        entry_type=entry_type,
    )
    if not result.is_valid:
        return None, result

    if entry_type == "prepaid_recognition" and prepaid_schedule_id is not None:
        schedule = prepaid.get_schedule(conn, prepaid_schedule_id)
        if schedule is None:
            result.errors.append(f"Prepaid schedule {prepaid_schedule_id} not found.")
            return None, result
        credit_to_schedule_account = next(
            (l for l in lines if l.side == "credit" and l.account_id == schedule["account_id"]), None
        )
        if credit_to_schedule_account is None:
            result.errors.append(
                "Prepaid recognition entries must credit the same account the schedule was set up against."
            )
            return None, result
        over_amort_error = prepaid.check_recognition(schedule, credit_to_schedule_account.amount)
        if over_amort_error:
            result.errors.append(over_amort_error)
            return None, result

    cur = conn.execute(
        """INSERT INTO journal_entries
           (org_id, entry_date, description, reason, entry_type, supporting_reference,
            preparer_id, status, prepaid_schedule_id, creation_warnings)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)""",
        (
            org_id,
            entry_date,
            description,
            reason,
            entry_type,
            supporting_reference,
            preparer_id,
            prepaid_schedule_id,
            "; ".join(result.warnings) if result.warnings else None,
        ),
    )
    entry_id = cur.lastrowid

    for line in lines:
        conn.execute(
            "INSERT INTO journal_entry_lines (entry_id, account_id, side, amount, memo) VALUES (?, ?, ?, ?, ?)",
            (entry_id, line.account_id, line.side, line.amount, line.memo),
        )

    if entry_type == "prepaid_recognition" and prepaid_schedule_id is not None:
        prepaid.recognize_period(conn, prepaid_schedule_id)

    return entry_id, result


def submit_for_review(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute(
        "UPDATE journal_entries SET status = 'pending_review' WHERE id = ? AND status = 'draft'", (entry_id,)
    )


def approve_entry(conn: sqlite3.Connection, entry_id: int, reviewer_id: int) -> ValidationResult:
    entry = get_entry(conn, entry_id)
    result = validate_approval(entry["preparer_id"], reviewer_id)
    if result.is_valid:
        conn.execute(
            "UPDATE journal_entries SET status = 'approved', reviewer_id = ? WHERE id = ?", (reviewer_id, entry_id)
        )
    return result


def reject_entry(conn: sqlite3.Connection, entry_id: int, reviewer_id: int, note: str = "") -> None:
    conn.execute(
        "UPDATE journal_entries SET status = 'rejected', reviewer_id = ?, review_note = ? WHERE id = ?",
        (reviewer_id, note, entry_id),
    )


def get_entry(conn: sqlite3.Connection, entry_id: int) -> sqlite3.Row:
    return conn.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,)).fetchone()


def get_lines(conn: sqlite3.Connection, entry_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT jel.*, a.code AS account_code, a.name AS account_name
           FROM journal_entry_lines jel JOIN accounts a ON a.id = jel.account_id
           WHERE jel.entry_id = ? ORDER BY jel.side DESC, jel.id""",
        (entry_id,),
    ).fetchall()


def list_entries(
    conn: sqlite3.Connection,
    org_id: int,
    *,
    account_id: int | None = None,
    preparer_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[sqlite3.Row]:
    query = "SELECT DISTINCT je.* FROM journal_entries je"
    conditions = ["je.org_id = ?"]
    params: list = [org_id]

    if account_id is not None:
        query += " JOIN journal_entry_lines jel ON jel.entry_id = je.id"
        conditions.append("jel.account_id = ?")
        params.append(account_id)
    if preparer_id is not None:
        conditions.append("je.preparer_id = ?")
        params.append(preparer_id)
    if status is not None:
        conditions.append("je.status = ?")
        params.append(status)
    if date_from is not None:
        conditions.append("je.entry_date >= ?")
        params.append(date_from)
    if date_to is not None:
        conditions.append("je.entry_date <= ?")
        params.append(date_to)

    query += " WHERE " + " AND ".join(conditions) + " ORDER BY je.entry_date, je.id"
    return conn.execute(query, params).fetchall()
