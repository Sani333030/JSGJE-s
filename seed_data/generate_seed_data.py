"""
Builds a demo database with two client organizations, each with its own
chart of accounts, staff, prepaid schedule, and a run of journal entries
covering every scenario called for in the brief: accrual, prepaid
recognition, depreciation, revenue recognition, reclassification, a
correcting entry, and a full draft -> submit -> approve/reject lifecycle.

Also deliberately attempts one out-of-balance entry and shows it gets
rejected -- proving the debit=credit validation actually works, without
ever letting a broken entry reach the database (there's no legitimate way
for an unbalanced entry to exist, so it's demonstrated as a rejection, not
stored as data).

All organizations, people, and figures are fictional.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from je_tool import accounts, db, employees, entries, organizations, prepaid
from je_tool.validation import LineInput

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.db")


def build_org_acme(conn):
    org_id = organizations.add_organization(conn, "Acme Manufacturing Co.")

    jordan = employees.add_employee(conn, org_id, "Jordan Blake", "preparer", "jordan@acme.example")
    casey = employees.add_employee(conn, org_id, "Casey Nguyen", "reviewer", "casey@acme.example")

    a = {}
    a["cash"] = accounts.add_account(conn, org_id, "1010", "Cash", "Asset")
    a["ar"] = accounts.add_account(conn, org_id, "1200", "Accounts Receivable", "Asset")
    a["prepaid_ins"] = accounts.add_account(conn, org_id, "1400", "Prepaid Insurance", "Asset", subtype="Prepaid Expense")
    a["equipment"] = accounts.add_account(conn, org_id, "1500", "Equipment", "Asset")
    a["accum_dep"] = accounts.add_account(
        conn, org_id, "1510", "Accumulated Depreciation - Equipment", "Asset", is_contra=True,
        subtype="Accumulated Depreciation",
    )
    a["ap"] = accounts.add_account(conn, org_id, "2010", "Accounts Payable", "Liability")
    a["accrued"] = accounts.add_account(conn, org_id, "2100", "Accrued Expenses", "Liability", subtype="Accrued Liability")
    a["deferred_rev"] = accounts.add_account(conn, org_id, "2200", "Deferred Revenue", "Liability")
    a["common_stock"] = accounts.add_account(conn, org_id, "3000", "Common Stock", "Equity")
    a["sales_rev"] = accounts.add_account(conn, org_id, "4000", "Sales Revenue", "Revenue")
    a["cogs"] = accounts.add_account(conn, org_id, "5000", "Cost of Goods Sold", "Expense")
    a["utilities_exp"] = accounts.add_account(conn, org_id, "5100", "Utilities Expense", "Expense")
    a["insurance_exp"] = accounts.add_account(conn, org_id, "5200", "Insurance Expense", "Expense")
    a["dep_exp"] = accounts.add_account(conn, org_id, "5300", "Depreciation Expense", "Expense")
    a["supplies_exp"] = accounts.add_account(conn, org_id, "5400", "Office Supplies Expense", "Expense")

    schedule_id = prepaid.create_schedule(
        conn, org_id, a["prepaid_ins"], "FY26 General Liability Insurance Policy",
        total_amount=1200.00, monthly_amount=100.00, periods_total=12, start_date="2026-01-01",
    )

    # 1. Accrual -- approved
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Accrue December utilities", reason="Utilities used in December; invoice not received until mid-January.",
        preparer_id=jordan, entry_type="accrual", supporting_reference="Estimate per meter reading log",
        lines=[LineInput(a["utilities_exp"], "debit", 450.00), LineInput(a["accrued"], "credit", 450.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, casey)

    # 2. Prepaid recognition (period 1 of 12) -- approved
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Recognize January insurance expense", reason="Monthly recognition of FY26 general liability policy prepaid in full in December.",
        preparer_id=jordan, entry_type="prepaid_recognition", supporting_reference="Prepaid schedule: FY26 GL Insurance",
        lines=[LineInput(a["insurance_exp"], "debit", 100.00), LineInput(a["prepaid_ins"], "credit", 100.00)],
        prepaid_schedule_id=schedule_id,
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, casey)

    # 3. Depreciation -- approved
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="January depreciation - manufacturing equipment", reason="Straight-line monthly depreciation per fixed asset schedule.",
        preparer_id=jordan, entry_type="depreciation", supporting_reference="Fixed asset schedule, Equipment #EQ-4482",
        lines=[LineInput(a["dep_exp"], "debit", 200.00), LineInput(a["accum_dep"], "credit", 200.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, casey)

    # 4. Revenue recognition -- approved
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Recognize revenue for completed January order", reason="Customer deposit taken in December is now earned; goods shipped and accepted 1/28.",
        preparer_id=jordan, entry_type="revenue_recognition", supporting_reference="Sales Order SO-3391, Bill of Lading #7724",
        lines=[LineInput(a["deferred_rev"], "debit", 500.00), LineInput(a["sales_rev"], "credit", 500.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, casey)

    # 5. Reclassification -- approved
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Reclassify miscoded office supplies purchase", reason="Purchase was coded to COGS in error; it is a general office supplies expense.",
        preparer_id=jordan, entry_type="reclassification", supporting_reference="Original entry JE-ref AP-1187",
        lines=[LineInput(a["supplies_exp"], "debit", 75.00), LineInput(a["cogs"], "credit", 75.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, casey)

    # 6. Correcting entry -- approved
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Correct omitted November sale", reason="Invoice #2291 to a customer was never recorded in November; recording now with current-period correcting entry.",
        preparer_id=jordan, entry_type="correcting", supporting_reference="Invoice #2291",
        lines=[LineInput(a["ar"], "debit", 300.00), LineInput(a["sales_rev"], "credit", 300.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, casey)

    # 7. Left pending review (not yet approved) -- shows an in-flight entry on the dashboard
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-02-28",
        description="February depreciation - manufacturing equipment", reason="Straight-line monthly depreciation per fixed asset schedule.",
        preparer_id=jordan, entry_type="depreciation", supporting_reference="Fixed asset schedule, Equipment #EQ-4482",
        lines=[LineInput(a["dep_exp"], "debit", 200.00), LineInput(a["accum_dep"], "credit", 200.00)],
    )
    entries.submit_for_review(conn, eid)

    # 8. Rejected by reviewer (technically valid, but reviewer wants more support) -- shows the rejection path
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-02-15",
        description="Write off aged receivable", reason="Customer balance appears uncollectible.",
        preparer_id=jordan, entry_type="standard", supporting_reference=None,
        lines=[LineInput(a["cogs"], "debit", 150.00), LineInput(a["ar"], "credit", 150.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.reject_entry(conn, eid, casey, note="Please attach collections correspondence and use a bad debt expense account rather than COGS before resubmitting.")

    # 9. Depreciation entry that credits the asset directly instead of Accumulated
    # Depreciation -- a common real mistake. Saved (warnings never block), but left
    # pending review rather than approved, since a reviewer should catch this.
    eid, result = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-02-28",
        description="February depreciation - equipment (posted directly to asset account)",
        reason="Straight-line monthly depreciation per fixed asset schedule.",
        preparer_id=jordan, entry_type="depreciation", supporting_reference="Fixed asset schedule, Equipment #EQ-4482",
        lines=[LineInput(a["dep_exp"], "debit", 200.00), LineInput(a["equipment"], "credit", 200.00)],
    )
    entries.submit_for_review(conn, eid)
    print(f"Acme entry {eid} saved with system warnings (expected -- demonstrates the template account-type check):")
    for w in result.warnings:
        print(f"  - {w}")

    # 10. Deliberately unbalanced -- demonstrates the debit=credit validation rejecting it outright
    bad_id, bad_result = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-02-20",
        description="Attempted entry with mismatched debits/credits", reason="Demonstration of validation failure.",
        preparer_id=jordan, entry_type="standard",
        lines=[LineInput(a["cash"], "debit", 500.00), LineInput(a["ar"], "credit", 400.00)],
    )
    assert bad_id is None, "unbalanced entry should never be saved"
    print("Demonstration -- attempted unbalanced entry was correctly rejected:")
    for err in bad_result.errors:
        print(f"  - {err}")

    return org_id


def build_org_blue_sky(conn):
    org_id = organizations.add_organization(conn, "Blue Sky Consulting LLC")

    riley = employees.add_employee(conn, org_id, "Riley Chen", "preparer", "riley@blueskyconsulting.example")
    sam = employees.add_employee(conn, org_id, "Sam Patel", "reviewer", "sam@blueskyconsulting.example")

    a = {}
    a["cash"] = accounts.add_account(conn, org_id, "1010", "Cash", "Asset")
    a["ar"] = accounts.add_account(conn, org_id, "1200", "Accounts Receivable", "Asset")
    a["prepaid_rent"] = accounts.add_account(conn, org_id, "1400", "Prepaid Rent", "Asset", subtype="Prepaid Expense")
    a["computer_equip"] = accounts.add_account(conn, org_id, "1500", "Computer Equipment", "Asset")
    a["accum_dep"] = accounts.add_account(
        conn, org_id, "1510", "Accumulated Depreciation - Computer Equipment", "Asset", is_contra=True,
        subtype="Accumulated Depreciation",
    )
    a["ap"] = accounts.add_account(conn, org_id, "2010", "Accounts Payable", "Liability")
    a["accrued_payroll"] = accounts.add_account(conn, org_id, "2100", "Accrued Payroll", "Liability", subtype="Accrued Liability")
    a["deferred_rev"] = accounts.add_account(conn, org_id, "2200", "Deferred Revenue", "Liability")
    a["owners_equity"] = accounts.add_account(conn, org_id, "3000", "Owner's Equity", "Equity")
    a["consulting_rev"] = accounts.add_account(conn, org_id, "4000", "Consulting Revenue", "Revenue")
    a["payroll_exp"] = accounts.add_account(conn, org_id, "5000", "Payroll Expense", "Expense")
    a["rent_exp"] = accounts.add_account(conn, org_id, "5100", "Rent Expense", "Expense")
    a["software_exp"] = accounts.add_account(conn, org_id, "5200", "Software Subscriptions Expense", "Expense")
    a["dep_exp"] = accounts.add_account(conn, org_id, "5300", "Depreciation Expense", "Expense")

    schedule_id = prepaid.create_schedule(
        conn, org_id, a["prepaid_rent"], "FY26 Office Lease - 6 Month Prepay",
        total_amount=18000.00, monthly_amount=3000.00, periods_total=6, start_date="2026-01-01",
    )

    # Accrual
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Accrue January contractor payroll", reason="Contractor hours worked in January are invoiced the first week of February.",
        preparer_id=riley, entry_type="accrual", supporting_reference="Timesheet summary, January",
        lines=[LineInput(a["payroll_exp"], "debit", 4200.00), LineInput(a["accrued_payroll"], "credit", 4200.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, sam)

    # Prepaid recognition
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Recognize January office rent", reason="Monthly recognition of 6-month office lease prepaid in December.",
        preparer_id=riley, entry_type="prepaid_recognition", supporting_reference="Prepaid schedule: FY26 Office Lease",
        lines=[LineInput(a["rent_exp"], "debit", 3000.00), LineInput(a["prepaid_rent"], "credit", 3000.00)],
        prepaid_schedule_id=schedule_id,
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, sam)

    # Depreciation
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="January depreciation - office computers", reason="Straight-line monthly depreciation per fixed asset schedule.",
        preparer_id=riley, entry_type="depreciation", supporting_reference="Fixed asset schedule, Computers #C-2026",
        lines=[LineInput(a["dep_exp"], "debit", 85.00), LineInput(a["accum_dep"], "credit", 85.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, sam)

    # Revenue recognition
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Recognize revenue for completed retainer month", reason="January retainer fee collected in advance in December is now earned.",
        preparer_id=riley, entry_type="revenue_recognition", supporting_reference="Engagement letter, Client: Northfield Retail",
        lines=[LineInput(a["deferred_rev"], "debit", 6000.00), LineInput(a["consulting_rev"], "credit", 6000.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, sam)

    # Reclassification -- account types deliberately vary entry to entry for this
    # template, so no type expectations apply; this one just moves a miscoded
    # charge to the right expense account.
    eid, _ = entries.create_entry(
        conn, org_id=org_id, entry_date="2026-01-31",
        description="Reclassify software cost miscoded to revenue account", reason="Data-entry error posted a software subscription charge to a revenue account; moving to the correct expense account.",
        preparer_id=riley, entry_type="reclassification", supporting_reference="Original entry JE-ref AP-0552",
        lines=[LineInput(a["software_exp"], "debit", 60.00), LineInput(a["consulting_rev"], "credit", 60.00)],
    )
    entries.submit_for_review(conn, eid)
    entries.approve_entry(conn, eid, sam)

    return org_id


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    db.init_db(DB_PATH)

    with db.session(DB_PATH) as conn:
        acme_id = build_org_acme(conn)
        blue_sky_id = build_org_blue_sky(conn)

    print(f"\nSeeded database at {DB_PATH}")
    print(f"  Org 1: Acme Manufacturing Co. (id={acme_id})")
    print(f"  Org 2: Blue Sky Consulting LLC (id={blue_sky_id})")


if __name__ == "__main__":
    main()
