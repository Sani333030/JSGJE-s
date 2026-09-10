"""Command-line entry point for the journal entry tool. Best for scripted/
batch use and CI-style checks; the Streamlit app (app.py) is the more
natural interface for day-to-day entry creation and review."""
from __future__ import annotations

import argparse
import json
import sys

from je_tool import accounts, db, employees, entries, export, organizations, prepaid
from je_tool.validation import LineInput

DEFAULT_DB = "je_tool.db"


def cmd_init_db(args):
    db.init_db(args.db)
    print(f"Initialized database at {args.db}")


def cmd_list_orgs(args):
    with db.session(args.db) as conn:
        for org in organizations.list_organizations(conn):
            print(f"{org['id']:>3}  {org['name']}")


def cmd_list_accounts(args):
    with db.session(args.db) as conn:
        for a in accounts.list_accounts(conn, args.org):
            normal = accounts.normal_balance(a["type"], bool(a["is_contra"]))
            contra = " (contra)" if a["is_contra"] else ""
            print(f"{a['id']:>3}  {a['code']:<6} {a['name']:<40} {a['type']}{contra}  normal={normal}")


def cmd_list_employees(args):
    with db.session(args.db) as conn:
        for e in employees.list_employees(conn, args.org):
            print(f"{e['id']:>3}  {e['name']:<25} {e['role']}")


def cmd_create_entry(args):
    with open(args.lines_file) as f:
        raw_lines = json.load(f)
    lines = [LineInput(l["account_id"], l["side"], float(l["amount"]), l.get("memo", "")) for l in raw_lines]

    with db.session(args.db) as conn:
        entry_id, result = entries.create_entry(
            conn,
            org_id=args.org,
            entry_date=args.date,
            description=args.description,
            reason=args.reason,
            preparer_id=args.preparer,
            lines=lines,
            entry_type=args.type,
            supporting_reference=args.reference,
            prepaid_schedule_id=args.prepaid_schedule,
        )

    if entry_id is None:
        print("Entry rejected:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    print(f"Created entry {entry_id} (draft).")
    for w in result.warnings:
        print(f"  warning: {w}")


def cmd_submit(args):
    with db.session(args.db) as conn:
        entries.submit_for_review(conn, args.entry_id)
    print(f"Entry {args.entry_id} submitted for review.")


def cmd_approve(args):
    with db.session(args.db) as conn:
        result = entries.approve_entry(conn, args.entry_id, args.reviewer)
    if not result.is_valid:
        print("Approval rejected:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    print(f"Entry {args.entry_id} approved.")


def cmd_reject(args):
    with db.session(args.db) as conn:
        entries.reject_entry(conn, args.entry_id, args.reviewer, note=args.note or "")
    print(f"Entry {args.entry_id} rejected.")


def cmd_list_entries(args):
    with db.session(args.db) as conn:
        rows = entries.list_entries(
            conn, args.org, account_id=args.account, preparer_id=args.preparer, status=args.status,
            date_from=args.date_from, date_to=args.date_to,
        )
        for e in rows:
            flag = " [!]" if e["creation_warnings"] else ""
            print(f"{e['id']:>4}  {e['entry_date']}  {e['status']:<15} {e['entry_type']:<20} {e['description']}{flag}")


def cmd_export_entry(args):
    with db.session(args.db) as conn:
        entry = entries.get_entry(conn, args.entry_id)
        org = organizations.get_organization(conn, entry["org_id"])
        preparer = employees.get_employee(conn, entry["preparer_id"])
        reviewer = employees.get_employee(conn, entry["reviewer_id"]) if entry["reviewer_id"] else None
        export.export_entry_pdf(
            conn, args.entry_id, org["name"], preparer["name"], reviewer["name"] if reviewer else None, args.output
        )
    print(f"Wrote {args.output}")


def cmd_export_listing(args):
    with db.session(args.db) as conn:
        org = organizations.get_organization(conn, args.org)
        export.export_period_listing_pdf(
            conn, args.org, org["name"], args.label, args.output,
            status=args.status, date_from=args.date_from, date_to=args.date_to,
        )
    print(f"Wrote {args.output}")


def main():
    parser = argparse.ArgumentParser(description="Journal entry documentation tool")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to the SQLite database")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db").set_defaults(func=cmd_init_db)

    sub.add_parser("list-orgs").set_defaults(func=cmd_list_orgs)

    p = sub.add_parser("list-accounts")
    p.add_argument("--org", type=int, required=True)
    p.set_defaults(func=cmd_list_accounts)

    p = sub.add_parser("list-employees")
    p.add_argument("--org", type=int, required=True)
    p.set_defaults(func=cmd_list_employees)

    p = sub.add_parser("create-entry")
    p.add_argument("--org", type=int, required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--preparer", type=int, required=True)
    p.add_argument("--type", default="standard")
    p.add_argument("--reference")
    p.add_argument("--prepaid-schedule", type=int, dest="prepaid_schedule")
    p.add_argument("--lines-file", required=True, help="JSON file: list of {account_id, side, amount, memo}")
    p.set_defaults(func=cmd_create_entry)

    p = sub.add_parser("submit")
    p.add_argument("--entry-id", type=int, required=True)
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("approve")
    p.add_argument("--entry-id", type=int, required=True)
    p.add_argument("--reviewer", type=int, required=True)
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject")
    p.add_argument("--entry-id", type=int, required=True)
    p.add_argument("--reviewer", type=int, required=True)
    p.add_argument("--note")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("list-entries")
    p.add_argument("--org", type=int, required=True)
    p.add_argument("--account", type=int)
    p.add_argument("--preparer", type=int)
    p.add_argument("--status")
    p.add_argument("--date-from", dest="date_from")
    p.add_argument("--date-to", dest="date_to")
    p.set_defaults(func=cmd_list_entries)

    p = sub.add_parser("export-entry")
    p.add_argument("--entry-id", type=int, required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_export_entry)

    p = sub.add_parser("export-listing")
    p.add_argument("--org", type=int, required=True)
    p.add_argument("--label", default="Journal Entry Listing")
    p.add_argument("--status")
    p.add_argument("--date-from", dest="date_from")
    p.add_argument("--date-to", dest="date_to")
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_export_listing)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
