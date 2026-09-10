"""Streamlit UI: organization switcher, entry creation form, review/approval
queue, search, and PDF export -- built on the same je_tool library the CLI
uses, so every rule (validation, templates, prepaid schedules) behaves
identically in both places."""
from __future__ import annotations

import os
import tempfile

import streamlit as st

from je_tool import accounts, db, employees, entries, export, organizations, prepaid
from je_tool.templates import TEMPLATES
from je_tool.validation import LineInput

DB_PATH = os.environ.get("JE_TOOL_DB", os.path.join("seed_data", "demo.db"))

st.set_page_config(page_title="Journal Entry Documentation Tool", layout="wide")

if not os.path.exists(DB_PATH):
    db.init_db(DB_PATH)

st.title("Journal Entry Documentation Tool")
st.caption("Every entry carries its reason, its evidence, and a debit=credit check that can't be skipped.")

with db.session(DB_PATH) as conn:
    orgs = organizations.list_organizations(conn)

if not orgs:
    st.warning("No organizations yet. Run `python seed_data/generate_seed_data.py` to load the demo data, or add one below.")
    with st.form("new_org"):
        new_org_name = st.text_input("New organization name")
        if st.form_submit_button("Create organization") and new_org_name:
            with db.session(DB_PATH) as conn:
                organizations.add_organization(conn, new_org_name)
            st.rerun()
    st.stop()

org_names = {o["id"]: o["name"] for o in orgs}
org_id = st.sidebar.selectbox("Client organization", options=list(org_names), format_func=lambda i: org_names[i])

with db.session(DB_PATH) as conn:
    org_employees = employees.list_employees(conn, org_id)
    org_accounts = accounts.list_accounts(conn, org_id)
    org_schedules = prepaid.list_schedules(conn, org_id)

employee_names = {e["id"]: f"{e['name']} ({e['role']})" for e in org_employees}
account_labels = {a["id"]: f"{a['code']} - {a['name']}" for a in org_accounts}

tab_new, tab_review, tab_search, tab_coa = st.tabs(["New Entry", "Review Queue", "Search / Export", "Chart of Accounts"])

with tab_new:
    st.subheader(f"New journal entry -- {org_names[org_id]}")
    entry_type = st.selectbox(
        "Entry type", options=list(TEMPLATES.keys()), format_func=lambda k: TEMPLATES[k].label
    )
    template = TEMPLATES[entry_type]
    if template.hint:
        st.info(template.hint)

    prepaid_schedule_id = None
    if entry_type == "prepaid_recognition" and org_schedules:
        schedule_choice = st.selectbox(
            "Prepaid schedule (optional -- links this entry to a tracked schedule)",
            options=[None] + [s["id"] for s in org_schedules],
            format_func=lambda sid: "None"
            if sid is None
            else next(
                f"{s['description']} (remaining: {prepaid.remaining_balance(s):,.2f})"
                for s in org_schedules
                if s["id"] == sid
            ),
        )
        prepaid_schedule_id = schedule_choice

    with st.form("new_entry"):
        col1, col2 = st.columns(2)
        entry_date = col1.date_input("Entry date")
        preparer_id = col2.selectbox("Preparer", options=list(employee_names), format_func=lambda i: employee_names[i])
        description = st.text_input("Description (plain-language summary)")
        reason = st.text_area("Reason / justification -- why is this entry needed?")
        reference = st.text_input("Supporting documentation reference (invoice #, contract, etc.)")

        st.markdown("**Lines**")
        num_lines = st.number_input("Number of lines", min_value=2, max_value=10, value=2, step=1)
        line_inputs = []
        for i in range(int(num_lines)):
            c1, c2, c3, c4 = st.columns([3, 1.2, 1.2, 2])
            acct = c1.selectbox(
                f"Account {i+1}", options=list(account_labels), format_func=lambda i: account_labels[i], key=f"acct_{i}"
            )
            side = c2.selectbox("Side", options=["debit", "credit"], key=f"side_{i}")
            amount = c3.number_input("Amount", min_value=0.0, step=0.01, key=f"amt_{i}")
            memo = c4.text_input("Memo", key=f"memo_{i}")
            line_inputs.append((acct, side, amount, memo))

        submitted = st.form_submit_button("Create entry")

    if submitted:
        lines = [LineInput(a, s, amt, m) for a, s, amt, m in line_inputs if amt > 0]
        with db.session(DB_PATH) as conn:
            entry_id, result = entries.create_entry(
                conn,
                org_id=org_id,
                entry_date=str(entry_date),
                description=description,
                reason=reason,
                preparer_id=preparer_id,
                lines=lines,
                entry_type=entry_type,
                supporting_reference=reference or None,
                prepaid_schedule_id=prepaid_schedule_id,
            )
        if entry_id is None:
            for err in result.errors:
                st.error(err)
        else:
            st.success(f"Entry {entry_id} created (draft).")
            for w in result.warnings:
                st.warning(w)

with tab_review:
    st.subheader("Review queue")
    with db.session(DB_PATH) as conn:
        drafts = entries.list_entries(conn, org_id, status="draft")
        pending = entries.list_entries(conn, org_id, status="pending_review")

    if drafts:
        st.markdown("**Drafts (not yet submitted)**")
        for e in drafts:
            c1, c2 = st.columns([5, 1])
            c1.write(f"#{e['id']} -- {e['entry_date']} -- {e['description']}")
            if c2.button("Submit for review", key=f"submit_{e['id']}"):
                with db.session(DB_PATH) as conn:
                    entries.submit_for_review(conn, e["id"])
                st.rerun()

    st.markdown("**Pending review**")
    if not pending:
        st.write("Nothing pending.")
    for e in pending:
        with db.session(DB_PATH) as conn:
            lines = entries.get_lines(conn, e["id"])
        with st.expander(f"#{e['id']} -- {e['entry_date']} -- {e['description']}"):
            st.write(f"**Reason:** {e['reason']}")
            if e["creation_warnings"]:
                st.warning(e["creation_warnings"])
            st.table(
                [{"Account": f"{l['account_code']} - {l['account_name']}", "Side": l["side"], "Amount": l["amount"]} for l in lines]
            )
            reviewer_id = st.selectbox(
                "Reviewer", options=list(employee_names), format_func=lambda i: employee_names[i], key=f"rev_{e['id']}"
            )
            note = st.text_input("Review note (required for rejection)", key=f"note_{e['id']}")
            c1, c2 = st.columns(2)
            if c1.button("Approve", key=f"approve_{e['id']}"):
                with db.session(DB_PATH) as conn:
                    result = entries.approve_entry(conn, e["id"], reviewer_id)
                if result.is_valid:
                    st.rerun()
                else:
                    for err in result.errors:
                        st.error(err)
            if c2.button("Reject", key=f"reject_{e['id']}"):
                with db.session(DB_PATH) as conn:
                    entries.reject_entry(conn, e["id"], reviewer_id, note=note)
                st.rerun()

with tab_search:
    st.subheader("Search entries")
    status_filter = st.selectbox("Status", options=[None, "draft", "pending_review", "approved", "rejected"], format_func=lambda s: s or "All")
    with db.session(DB_PATH) as conn:
        results = entries.list_entries(conn, org_id, status=status_filter)

    for e in results:
        flag = " :warning:" if e["creation_warnings"] else ""
        st.write(f"#{e['id']} -- {e['entry_date']} -- {e['status']} -- {e['description']}{flag}")

    st.markdown("---")
    st.markdown("**Export**")
    entry_to_export = st.number_input("Entry # to export as PDF", min_value=0, step=1)
    if st.button("Export entry PDF") and entry_to_export:
        with db.session(DB_PATH) as conn:
            entry = entries.get_entry(conn, int(entry_to_export))
            if entry is None:
                st.error("Entry not found.")
            else:
                preparer = employees.get_employee(conn, entry["preparer_id"])
                reviewer = employees.get_employee(conn, entry["reviewer_id"]) if entry["reviewer_id"] else None
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp.close()
                export.export_entry_pdf(
                    conn, int(entry_to_export), org_names[org_id], preparer["name"],
                    reviewer["name"] if reviewer else None, tmp.name,
                )
                with open(tmp.name, "rb") as f:
                    st.download_button("Download PDF", f.read(), file_name=f"entry_{int(entry_to_export)}.pdf", mime="application/pdf")

with tab_coa:
    st.subheader(f"Chart of accounts -- {org_names[org_id]}")
    st.table(
        [
            {
                "Code": a["code"],
                "Name": a["name"],
                "Type": a["type"] + (" (contra)" if a["is_contra"] else ""),
                "Subtype": a["subtype"] or "",
                "Normal balance": accounts.normal_balance(a["type"], bool(a["is_contra"])),
            }
            for a in org_accounts
        ]
    )
    if org_schedules:
        st.markdown("**Prepaid schedules**")
        st.table(
            [
                {
                    "Description": s["description"],
                    "Total": s["total_amount"],
                    "Monthly": s["monthly_amount"],
                    "Periods": f"{s['periods_recognized']}/{s['periods_total']}",
                    "Remaining": prepaid.remaining_balance(s),
                }
                for s in org_schedules
            ]
        )
