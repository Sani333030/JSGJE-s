"""Organization (client) records -- the top-level scope everything else hangs off."""
from __future__ import annotations

import sqlite3


def add_organization(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("INSERT INTO organizations (name) VALUES (?)", (name,))
    return cur.lastrowid


def list_organizations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM organizations ORDER BY name").fetchall()


def get_organization(conn: sqlite3.Connection, org_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
