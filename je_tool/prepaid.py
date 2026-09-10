"""
Prepaid amortization schedules: the specific pain point named for this
tool ("trouble pushing prepaids to the right accounts over time").

A prepaid schedule tracks a prepaid asset's total amount, how much gets
recognized as expense each period, and how many periods have already been
recognized. Recording a "prepaid_recognition" journal entry against a
schedule decrements its remaining balance -- and, unlike the soft
validation warnings elsewhere, over-recognizing a schedule (posting more
than what's left) is a hard error. There's no legitimate reason to
amortize a prepaid past its total amount; that's just a data error.
"""
from __future__ import annotations

import sqlite3


def create_schedule(
    conn: sqlite3.Connection,
    org_id: int,
    account_id: int,
    description: str,
    total_amount: float,
    monthly_amount: float,
    periods_total: int,
    start_date: str,
) -> int:
    cur = conn.execute(
        """INSERT INTO prepaid_schedules
           (org_id, account_id, description, total_amount, monthly_amount, periods_total, start_date)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (org_id, account_id, description, total_amount, monthly_amount, periods_total, start_date),
    )
    return cur.lastrowid


def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM prepaid_schedules WHERE id = ?", (schedule_id,)).fetchone()


def list_schedules(conn: sqlite3.Connection, org_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM prepaid_schedules WHERE org_id = ? ORDER BY start_date", (org_id,)).fetchall()


def remaining_balance(schedule: sqlite3.Row) -> float:
    return round(schedule["total_amount"] - (schedule["monthly_amount"] * schedule["periods_recognized"]), 2)


def check_recognition(schedule: sqlite3.Row, amount: float) -> str | None:
    """Returns an error message if recognizing `amount` against this schedule would over-amortize it, else None."""
    remaining = remaining_balance(schedule)
    if schedule["periods_recognized"] >= schedule["periods_total"]:
        return (
            f"Prepaid schedule '{schedule['description']}' is already fully recognized "
            f"({schedule['periods_total']} of {schedule['periods_total']} periods)."
        )
    if amount - remaining > 0.005:
        return (
            f"Recognizing {amount:,.2f} would exceed the {remaining:,.2f} remaining on prepaid schedule "
            f"'{schedule['description']}'."
        )
    return None


def recognize_period(conn: sqlite3.Connection, schedule_id: int) -> None:
    conn.execute(
        "UPDATE prepaid_schedules SET periods_recognized = periods_recognized + 1 WHERE id = ?",
        (schedule_id,),
    )
