"""
Entry-type templates: the expected account *types* for each side of a
common recurring entry, so picking "Prepaid Recognition" from a list tells
you what kind of account belongs on each side, instead of having to
re-derive the debit/credit direction and account category from memory
every time. This is the direct fix for "trouble pushing assets/liabilities/
prepaids to the right accounts" -- the tool tells you what's expected, and
validation.py flags it (softly -- see below) when the actual pick doesn't
match.

These are deliberately soft expectations, not hard rules: a "correcting
entry" or "reclassification" can legitimately touch almost any pair of
accounts, and even accrual/prepaid/depreciation entries occasionally have
a legitimate exception. So a mismatch is surfaced as a warning to double-
check, never a blocked save.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EntryTemplate:
    label: str
    expected_debit_types: list[str] | None
    expected_credit_types: list[str] | None
    hint: str
    requires_contra_credit: bool = False


TEMPLATES: dict[str, EntryTemplate] = {
    "accrual": EntryTemplate(
        label="Accrual",
        expected_debit_types=["Expense"],
        expected_credit_types=["Liability"],
        hint="Recognize an expense incurred but not yet invoiced or paid (e.g. utilities used but not yet billed).",
    ),
    "prepaid_recognition": EntryTemplate(
        label="Prepaid Expense Recognition",
        expected_debit_types=["Expense"],
        expected_credit_types=["Asset"],
        hint="Recognize one period's portion of a prepaid asset as expense.",
    ),
    "depreciation": EntryTemplate(
        label="Depreciation",
        expected_debit_types=["Expense"],
        expected_credit_types=["Asset"],
        hint="Record periodic depreciation. The credit side should be a contra-asset (Accumulated Depreciation), not the asset account itself.",
        requires_contra_credit=True,
    ),
    "revenue_recognition": EntryTemplate(
        label="Revenue Recognition",
        expected_debit_types=["Asset", "Liability"],
        expected_credit_types=["Revenue"],
        hint="Recognize earned revenue -- either a new receivable (debit Asset) or previously deferred revenue now earned (debit the deferred-revenue Liability).",
    ),
    "reclassification": EntryTemplate(
        label="Reclassification",
        expected_debit_types=None,
        expected_credit_types=None,
        hint="Move an amount from one account or category to another. Account types vary by what's being reclassified.",
    ),
    "correcting": EntryTemplate(
        label="Correcting Entry",
        expected_debit_types=None,
        expected_credit_types=None,
        hint="Fix a prior misclassification or error. Reference the entry being corrected in the reason field.",
    ),
    "standard": EntryTemplate(
        label="Standard / Other",
        expected_debit_types=None,
        expected_credit_types=None,
        hint="",
    ),
}


def get_template(entry_type: str) -> EntryTemplate:
    return TEMPLATES.get(entry_type, TEMPLATES["standard"])
