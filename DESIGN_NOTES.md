# Design Notes

Trade-offs and judgment calls made while building this, and why.

## A warning rule I built, tested against real data, and removed

The first version of `validation.py` warned whenever a line posted against
an account's "normal balance" direction — e.g. crediting an Asset (Assets
are debit-normal) would flag as "unusual, confirm this is intentional."

Running the seed data through it immediately showed the problem: 6 of the
first 13 entries got flagged, and every single one was completely correct
— recognizing a period of a prepaid (credits the prepaid asset, reducing
it), recognizing previously deferred revenue (debits the deferred-revenue
liability, reducing it), writing off a receivable (credits the
receivable). Reducing a balance is not unusual; it's what settlement,
amortization, and recognition entries *do*, and they're some of the most
common entries there are. A rule that flags most of them isn't a useful
signal, it's noise that teaches preparers to ignore every warning the tool
produces — which defeats the entire purpose of having warnings.

The fix was to remove that check entirely and keep only the one that
turned out to actually be valid: does the line's account *type* match what
the entry's template expects (an Expense/Liability pair for an accrual, an
Expense/contra-Asset pair for depreciation, etc). That check only fires
when something is actually questionable, and it fired zero times on the
13 correctly-constructed entries and exactly once on the one entry
deliberately built to trigger it. `accounts.normal_balance()` is still
there and still correct — it's just used as an informational label (shown
in the chart-of-accounts view) rather than a validation rule, because
"which side increases this account" and "was this line probably a
mistake" turned out to be two different questions.

## Multi-org isolation is enforced in the write path, not just by convention

Every account, employee, and entry carries an `org_id`. That alone doesn't
prevent a bug (or a copy-pasted account ID) from posting a Client B
account onto a Client A entry — so `entries.create_entry` explicitly
checks every line's account against the entry's `org_id` before writing
anything, and rejects the whole entry if any line fails. This is checked
in `tests/test_entries.py::test_account_from_another_org_is_rejected`
specifically because "the schema has an org_id column" and "cross-org
posting is actually impossible" are different claims, and only the second
one matters.

## Why prepaid over-amortization is a hard error but account-type mismatches are a warning

These look similar (both are "you're doing something with this account
that seems off") but they're different kinds of claims. An unusual
account type *might* be a legitimate unusual transaction — someone
building this tool can't enumerate every valid exception in advance, so it
gets surfaced for a human to judge. Recognizing more of a prepaid than
exists is not a judgment call at all; the schedule's total amount is a
known, fixed number, and posting past it is arithmetically wrong no matter
the business context. Where a rule check is unambiguous, it blocks;
where it's a heuristic, it warns.

## Segregation of duties is enforced at approval, not at entry creation

A preparer can create and even submit their own entry, but
`validate_approval` refuses to let the same person approve it — checked at
the moment of approval, against the entry's stored `preparer_id`, rather
than trying to restrict who's "allowed" to prepare an entry in the first
place. This mirrors how the control actually works in practice: anyone can
draft an entry, but sign-off requires a second, different person.

## SQLite via the standard library, not an ORM

`sqlite3` is in the Python standard library, requires no extra dependency,
and the schema is small enough (6 tables) that an ORM's main benefit —
not writing SQL by hand — doesn't outweigh its cost here: an ORM would
add a dependency and a layer of abstraction to a schema simple enough to
read directly in `db.py`. `sqlite3.Row` gives dict-style column access
without needing model classes at all.

## PDF export via reportlab, not an external service

`reportlab` is a pure-Python, pip-installable library with no external API
calls, account, or network dependency — appropriate for a self-contained
demo tool, and it produces genuinely clean output (see the README's sample
entry) without needing anything beyond `pip install`.

## What's intentionally out of scope

- **User authentication** — employees are records you pick from a list,
  not accounts you log into. Real access control (who can create vs.
  approve vs. only view) is a legitimate next step, but a demo tool
  serving one browser session doesn't need a login system to prove the
  documentation and validation logic works.
- **Editing a saved entry** — entries are created, submitted, approved, or
  rejected; there's no "edit and resave" path. This mirrors how real
  accounting systems generally work: correcting a mistake means posting a
  new correcting entry (the tool has a template for exactly this), not
  rewriting history, which is itself part of why journal entry audit
  trails are trustworthy.
- **Currency/multi-currency** — every organization's accounts and entries
  are assumed to be in one currency. Multi-currency would need an FX-rate
  concept threaded through every amount, which is a meaningfully different
  scope than what this tool demonstrates.
