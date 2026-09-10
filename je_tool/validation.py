"""
Journal entry validation, split deliberately into two tiers:

- Errors block the save. This is where the one truly non-negotiable
  accounting rule lives: debits must equal credits. Missing required
  fields (description, reason, date, at least one line on each side) are
  errors too -- a journal entry with no justification is not a journal
  entry, it's an unexplained number.
- Warnings never block anything. They flag when a line's account *type*
  doesn't match what the entry's template expects (e.g. crediting a
  Liability on a "prepaid recognition" entry, or crediting a non-contra
  asset on a "depreciation" entry instead of Accumulated Depreciation).

Deliberately NOT flagged: which side (debit/credit) a line posts to
relative to the account's normal balance. That's not a useful signal --
paying down a payable, drawing down a prepaid, and recognizing previously
deferred revenue all legitimately move against normal balance, and they're
some of the most common entries there are. Warning on every one of those
would just train preparers to ignore the warnings entirely. Normal balance
is still exposed (see accounts.normal_balance) as an informational label,
just not as a validation check.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from .templates import get_template

AMOUNT_TOLERANCE = 0.005


@dataclass
class LineInput:
    account_id: int
    side: str  # "debit" or "credit"
    amount: float
    memo: str = ""


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_entry(
    *,
    entry_date: str,
    description: str,
    reason: str,
    preparer_id: int | None,
    lines: list[LineInput],
    accounts_by_id: dict,
    entry_type: str = "standard",
) -> ValidationResult:
    result = ValidationResult()

    if not entry_date:
        result.errors.append("Entry date is required.")
    if not description or not description.strip():
        result.errors.append("Description is required.")
    if not reason or not reason.strip():
        result.errors.append("Reason/justification is required -- explain why this entry is needed.")
    if not preparer_id:
        result.errors.append("Preparer is required.")

    debit_lines = [l for l in lines if l.side == "debit"]
    credit_lines = [l for l in lines if l.side == "credit"]
    if not debit_lines:
        result.errors.append("At least one debit line is required.")
    if not credit_lines:
        result.errors.append("At least one credit line is required.")

    for line in lines:
        if line.amount <= 0:
            result.errors.append(f"Line amounts must be positive (got {line.amount}).")
        if line.account_id not in accounts_by_id:
            result.errors.append(f"Account id {line.account_id} was not found for this organization.")

    if result.errors:
        return result  # don't bother with balance/template checks against data we already know is broken

    total_debits = sum(l.amount for l in debit_lines)
    total_credits = sum(l.amount for l in credit_lines)
    if abs(total_debits - total_credits) > AMOUNT_TOLERANCE:
        result.errors.append(
            f"Debits ({total_debits:,.2f}) must equal credits ({total_credits:,.2f}) -- "
            f"difference of {total_debits - total_credits:,.2f}."
        )
        return result

    template = get_template(entry_type)
    for line in lines:
        account = accounts_by_id[line.account_id]

        expected_types = template.expected_debit_types if line.side == "debit" else template.expected_credit_types
        if expected_types and account["type"] not in expected_types:
            result.warnings.append(
                f"'{template.label}' entries typically {line.side} a "
                f"{'/'.join(expected_types)} account; '{account['name']}' is type {account['type']}."
            )

        if template.requires_contra_credit and line.side == "credit" and not bool(account["is_contra"]):
            result.warnings.append(
                f"'{template.label}' entries typically credit a contra-asset account (e.g. Accumulated "
                f"Depreciation); '{account['name']}' is not marked as contra."
            )

    return result


def validate_approval(preparer_id: int, reviewer_id: int) -> ValidationResult:
    result = ValidationResult()
    if reviewer_id == preparer_id:
        result.errors.append(
            "Reviewer must be a different person than the preparer (segregation of duties)."
        )
    return result
