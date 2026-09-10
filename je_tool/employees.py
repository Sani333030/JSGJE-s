"""Employee (preparer/reviewer/admin) records, scoped per organization."""
from __future__ import annotations

import sqlite3


def add_employee(conn: sqlite3.Connection, org_id: int, name: str, role: str, email: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO employees (org_id, name, role, email) VALUES (?, ?, ?, ?)", (org_id, name, role, email)
    )
    return cur.lastrowid


def list_employees(conn: sqlite3.Connection, org_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM employees WHERE org_id = ? ORDER BY name", (org_id,)).fetchall()


def get_employee(conn: sqlite3.Connection, employee_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
