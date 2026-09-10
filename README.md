# Journal Entry Documentation Tool

Standardizes how journal entries get recorded and explained — every entry
carries what happened, why, and what evidence supports it — for a
bookkeeping/advisory practice serving multiple client organizations at
once, each with its own chart of accounts and staff.

## Why this matters

An auditor reviewing a journal entry isn't just checking that the math
works — they're checking that someone can explain *why* the entry exists
and point to something that proves it. A debit and credit with no
justification is not documentation, it's an unexplained number, and
inconsistent JE documentation is one of the most common findings in a SOX-
style internal controls review. This tool makes the documentation
mandatory rather than aspirational: an entry without a reason, without a
preparer, or without debits equal to credits simply cannot be saved.

It also encodes two things that "debits = credits" alone doesn't catch:
whether an entry is landing in the *kind* of account it should (an easy
mistake when a client has dozens of accounts across assets, liabilities,
and prepaids), and whether a prepaid/accrual schedule is being amortized
correctly over time rather than by memory each month.

## Multi-client from the ground up

Every account, employee, and entry belongs to one organization. A
bookkeeping/advisory practice serving several clients runs one database,
switches organizations in the sidebar (Streamlit) or passes `--org`
(CLI), and each client's chart of accounts, staff, and entries stay fully
separated — an account from Client A's books can never be posted to on a
Client B entry (enforced in code, not just by discipline; see
`entries.create_entry`, which checks every line's account against the
entry's `org_id` before anything is saved).

## Core validation: two tiers

- **Errors block the save.** Debits must equal credits. Date, description,
  reason, and preparer are required. At least one debit line and one
  credit line are required. This is the one truly non-negotiable rule in
  the tool.
- **Warnings never block anything**, but they're saved with the entry
  (`creation_warnings`) so a reviewer or auditor can see later exactly
  what the system flagged. They fire when a line's account *type* doesn't
  match what the entry's template expects — e.g. picking "Depreciation"
  and crediting the asset account directly instead of its contra
  (Accumulated Depreciation), a very common real mistake.

Deliberately **not** flagged: which side (debit/credit) a line posts to
relative to an account's normal balance. Paying down a payable, drawing
down a prepaid, and recognizing previously deferred revenue all move
against normal balance and are completely routine — see
[DESIGN_NOTES.md](DESIGN_NOTES.md) for why an earlier version of this
check turned out to be noise, not signal, and was removed.

## Prepaid schedules

A prepaid schedule tracks a prepaid asset's total amount, its monthly
recognition amount, and how many periods have been recognized so far.
Posting a "Prepaid Recognition" entry against a schedule automatically
decrements its remaining balance — and posting more than what's left, or
posting against an already-fully-recognized schedule, is a **hard error**,
not a warning. There's no legitimate reason to amortize a prepaid past its
total; that's a data error, not a judgment call.

## Running it

```bash
pip install -r requirements.txt

# Load the demo data (two client organizations, charts of accounts, staff, and 14 entries)
python seed_data/generate_seed_data.py

# Web UI
streamlit run app.py

# Or the CLI
python cli.py --db seed_data/demo.db list-orgs
python cli.py --db seed_data/demo.db list-accounts --org 1
python cli.py --db seed_data/demo.db list-entries --org 1
python cli.py --db seed_data/demo.db export-entry --entry-id 9 --output entry_9.pdf
```

Creating an entry from the CLI takes a JSON lines file:

```bash
cat > lines.json <<'EOF'
[
  {"account_id": 12, "side": "debit", "amount": 450.00},
  {"account_id": 7, "side": "credit", "amount": 450.00}
]
EOF

python cli.py --db seed_data/demo.db create-entry \
  --org 1 --date 2026-03-31 --preparer 1 --type accrual \
  --description "Accrue March utilities" \
  --reason "Utilities used in March; invoice not yet received." \
  --lines-file lines.json
```

## A sample entry, end to end

From the seeded demo data — a deliberate example of the account-type
warning firing (see `seed_data/generate_seed_data.py`, entry #9):

| Field | Value |
|---|---|
| Description | February depreciation - equipment (posted directly to asset account) |
| Reason | Straight-line monthly depreciation per fixed asset schedule. |
| Preparer | Jordan Blake |
| Debit | 5300 - Depreciation Expense — 200.00 |
| Credit | 1500 - Equipment — 200.00 |
| System warning | "Depreciation" entries typically credit a contra-asset account (e.g. Accumulated Depreciation); 'Equipment' is not marked as contra. |

The entry still saves (warnings never block), but it's left in
`pending_review` rather than approved — exactly the kind of thing a
reviewer should catch before sign-off, and now they have a system flag
telling them where to look. Exporting it (`export-entry`) produces a
clean one-page PDF with the same information, ready to hand to an auditor.

Also seeded: an entry that violates debit=credit is attempted and
rejected outright (see the console output when you run the seed script) —
demonstrating that the one non-negotiable rule actually holds.

> Add your own note here if you want to connect this project back to a
> real experience for interviews — e.g. what inconsistent JE
> documentation actually cost a team you worked with. That context is
> yours to add; nothing here should read as a story that isn't true.

## Project structure

```
je_tool/
  db.py           SQLite schema + connection helper
  organizations.py, employees.py, accounts.py   scoped CRUD for each entity
  templates.py    entry-type templates (expected account types per side)
  validation.py   hard errors (debit=credit, required fields) + soft warnings (account-type mismatch)
  prepaid.py      prepaid schedule tracking, including the over-amortization hard block
  entries.py      ties it together: create/list/approve/reject, scoped per org
  export.py       PDF export (single entry + period listing) via reportlab
cli.py            command-line interface
app.py            Streamlit UI: org switcher, entry form, review queue, search/export
seed_data/        generate_seed_data.py + the resulting demo.db (2 orgs, 14 entries)
tests/            one test file per module, plus end-to-end entry lifecycle tests
```

See [DESIGN_NOTES.md](DESIGN_NOTES.md) for the reasoning behind specific
rules, including one I built, found to be wrong via the seed data, and
removed.

## Tests

```bash
pytest
```

## License

MIT — see [LICENSE](LICENSE).
