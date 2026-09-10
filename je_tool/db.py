"""
SQLite schema and connection helper.

Everything below the organization level -- accounts, employees, journal
entries -- carries an org_id and is only ever queried scoped to one
organization. This is what makes the tool usable across multiple clients
without their charts of accounts, staff, or entries ever mixing: a bookkeeping
firm serving five clients runs one database, but every query is written
"for this org" rather than "for everyone," so client data stays separated
by construction, not by convention.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('preparer', 'reviewer', 'admin')),
    email TEXT
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL REFERENCES organizations(id),
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('Asset', 'Liability', 'Equity', 'Revenue', 'Expense')),
    is_contra INTEGER NOT NULL DEFAULT 0,
    subtype TEXT,
    UNIQUE (org_id, code)
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL REFERENCES organizations(id),
    entry_date TEXT NOT NULL,
    description TEXT NOT NULL,
    reason TEXT NOT NULL,
    entry_type TEXT NOT NULL DEFAULT 'standard',
    supporting_reference TEXT,
    preparer_id INTEGER NOT NULL REFERENCES employees(id),
    reviewer_id INTEGER REFERENCES employees(id),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'pending_review', 'approved', 'rejected')),
    creation_warnings TEXT,
    review_note TEXT,
    prepaid_schedule_id INTEGER REFERENCES prepaid_schedules(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS journal_entry_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES journal_entries(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    side TEXT NOT NULL CHECK (side IN ('debit', 'credit')),
    amount REAL NOT NULL CHECK (amount > 0),
    memo TEXT
);

CREATE TABLE IF NOT EXISTS prepaid_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id INTEGER NOT NULL REFERENCES organizations(id),
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    description TEXT NOT NULL,
    total_amount REAL NOT NULL,
    monthly_amount REAL NOT NULL,
    periods_total INTEGER NOT NULL,
    periods_recognized INTEGER NOT NULL DEFAULT 0,
    start_date TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str) -> None:
    conn = connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def session(path: str):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
