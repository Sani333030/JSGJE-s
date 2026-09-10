"""
Chart of accounts operations, scoped per organization, plus the normal-
balance rule every other module relies on.

Normal balance is *computed*, never stored as its own column: an account's
type (Asset/Liability/Equity/Revenue/Expense) plus whether it's a contra
account fully determines which side (debit/credit) increases it. Storing
it separately would let it drift out of sync with type/is_contra if either
ever got edited -- computing it from first principles means there's exactly
one place this rule lives.
"""
from __future__ import annotations

import sqlite3

DEBIT_NORMAL_TYPES = {"Asset", "Expense"}


def normal_balance(account_type: str, is_contra: bool = False) -> str:
    is_debit_normal = account_type in DEBIT_NORMAL_TYPES
    if is_contra:
        is_debit_normal = not is_debit_normal
    return "debit" if is_debit_normal else "credit"


def add_account(
    conn: sqlite3.Connection,
    org_id: int,
    code: str,
    name: str,
    account_type: str,
    is_contra: bool = False,
    subtype: str | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO accounts (org_id, code, name, type, is_contra, subtype) VALUES (?, ?, ?, ?, ?, ?)",
        (org_id, code, name, account_type, int(is_contra), subtype),
    )
    return cur.lastrowid


def list_accounts(conn: sqlite3.Connection, org_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM accounts WHERE org_id = ? ORDER BY code", (org_id,)).fetchall()


def get_account(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
