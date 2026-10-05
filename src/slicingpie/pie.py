from __future__ import annotations

from dataclasses import replace
import re

from slicingpie.config import AppConfig, PersonConfig
from slicingpie.models import (
    ExpenseItem,
    PersonExpenses,
    PersonSlice,
    PersonSummary,
    PieReport,
    Ticket,
    TicketShare,
)


_ESTIMATE = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(h|hr|hrs|hora|horas)?\s*$",
    re.IGNORECASE,
)
_AMOUNT = re.compile(
    r"^\s*[$]?\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:usd|us\$|\$)?\s*$",
    re.IGNORECASE,
)


def parse_estimate_hours(value: object, hours_per_unit: float) -> float | None:
    """Convert the estimate field into work hours."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        hours = float(value) * hours_per_unit
        return hours if hours >= 0 else None

    text = str(value).strip()
    if not text:
        return None

    match = _ESTIMATE.match(text)
    if not match:
        return None

    amount = float(match.group(1).replace(",", "."))
    if match.group(2):
        return amount
    return amount * hours_per_unit


def parse_expense_amount(value: object) -> float | None:
    """Convert the estimate field into an expense amount (currency units)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        amount = float(value)
        return amount if amount >= 0 else None

    text = str(value).strip()
    if not text:
        return None
    match = _AMOUNT.match(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def is_expense_ticket(ticket: Ticket, label: str) -> bool:
    wanted = label.casefold()
    return any(item.casefold() == wanted for item in ticket.labels)


def user_for(login: str, config: AppConfig) -> tuple[PersonConfig, bool]:
    found = config.slicing_pie.users.get(login.lower())
    if found is not None:
        return found, False
    return (
        PersonConfig(
            login=login,
            name="",
            rate=config.slicing_pie.default_hourly_rate,
            seniority=1.0,
        ),
        True,
    )


def build_pie(
    tickets: list[Ticket],
    config: AppConfig,
    *,
    project_title: str,
    project_url: str | None,
) -> PieReport:
    pie_cfg = config.slicing_pie
    expense_label = config.expenses.label
    done_names = {value.casefold() for value in config.fields.done}
    done_tickets = [
        ticket
        for ticket in tickets
        if ticket.status is not None and ticket.status.casefold() in done_names
    ]

    hours_by_person: dict[str, float] = {}
    tickets_by_person: dict[str, list[TicketShare]] = {}
    amount_by_person: dict[str, float] = {}
    expenses_by_person: dict[str, list[ExpenseItem]] = {}
    display_login: dict[str, str] = {}
    display_name: dict[str, str] = {}
    skipped_no_estimate: list[Ticket] = []
    skipped_no_assignee: list[Ticket] = []
    skipped_zero_hours: list[Ticket] = []
    counted_work = 0
    counted_expenses = 0

    def recipients_of(ticket: Ticket) -> tuple[str, ...]:
        if not ticket.assignees:
            return ()
        if pie_cfg.split_among_assignees:
            return ticket.assignees
        return ticket.assignees[:1]

    def ensure_person(login: str) -> str:
        key = login.lower()
        display_login.setdefault(key, login)
        hours_by_person.setdefault(key, 0.0)
        tickets_by_person.setdefault(key, [])
        amount_by_person.setdefault(key, 0.0)
        expenses_by_person.setdefault(key, [])
        if key not in display_name:
            user, _used = user_for(login, config)
            display_name[key] = user.name
        return key

    for ticket in done_tickets:
        if is_expense_ticket(ticket, expense_label):
            counted = _accumulate_expense(
                ticket,
                recipients_of,
                ensure_person,
                amount_by_person,
                expenses_by_person,
                skipped_no_estimate,
                skipped_no_assignee,
                skipped_zero_hours,
            )
            counted_expenses += counted
        else:
            counted = _accumulate_ticket(
                ticket,
                pie_cfg.hours_per_estimate_unit,
                recipients_of,
                ensure_person,
                hours_by_person,
                tickets_by_person,
                skipped_no_estimate,
                skipped_no_assignee,
                skipped_zero_hours,
            )
            counted_work += counted

    for user in pie_cfg.users.values():
        if user.effective_rate != 0:
            ensure_person(user.login)

    people, total_slices, total_hours = _build_people(
        hours_by_person, tickets_by_person, display_login, config
    )
    expenses, total_expenses, total_expense_slices = _build_expenses(
        amount_by_person,
        expenses_by_person,
        display_login,
        display_name,
        config.expenses.cash_multiplier,
    )
    summary, total_contribution = _build_summary(people, expenses)

    return PieReport(
        project_title=project_title,
        project_url=project_url,
        people=tuple(people),
        total_hours=total_hours,
        total_slices=total_slices,
        done_count=len(done_tickets),
        counted_count=counted_work,
        skipped_no_estimate=tuple(skipped_no_estimate),
        skipped_no_assignee=tuple(skipped_no_assignee),
        skipped_zero_hours=tuple(skipped_zero_hours),
        time_multiplier=pie_cfg.time_multiplier,
        default_hourly_rate=pie_cfg.default_hourly_rate,
        expenses=tuple(expenses),
        total_expenses=total_expenses,
        total_expense_slices=total_expense_slices,
        counted_expenses=counted_expenses,
        expense_currency=config.expenses.currency,
        expense_label=expense_label,
        cash_multiplier=config.expenses.cash_multiplier,
        summary=tuple(summary),
        total_contribution=total_contribution,
    )


def _accumulate_ticket(
    ticket: Ticket,
    hours_per_unit: float,
    recipients_of,
    ensure_person,
    hours_by_person: dict[str, float],
    tickets_by_person: dict[str, list[TicketShare]],
    skipped_no_estimate: list[Ticket],
    skipped_no_assignee: list[Ticket],
    skipped_zero_hours: list[Ticket],
) -> int:
    hours = parse_estimate_hours(ticket.estimate_raw, hours_per_unit)
    if hours is None:
        skipped_no_estimate.append(ticket)
        return 0
    if hours == 0:
        skipped_zero_hours.append(ticket)
        for login in recipients_of(ticket):
            ensure_person(login)
        return 0
    if not ticket.assignees:
        skipped_no_assignee.append(ticket)
        return 0

    recipients = recipients_of(ticket)
    hours_each = hours / len(recipients)
    share = TicketShare(
        title=ticket.title,
        number=ticket.number,
        url=ticket.url,
        hours=hours_each,
        assignees=ticket.assignees,
    )
    for login in recipients:
        key = ensure_person(login)
        hours_by_person[key] = hours_by_person.get(key, 0.0) + hours_each
        tickets_by_person[key].append(share)
    return 1


def _accumulate_expense(
    ticket: Ticket,
    recipients_of,
    ensure_person,
    amount_by_person: dict[str, float],
    expenses_by_person: dict[str, list[ExpenseItem]],
    skipped_no_estimate: list[Ticket],
    skipped_no_assignee: list[Ticket],
    skipped_zero_hours: list[Ticket],
) -> int:
    amount = parse_expense_amount(ticket.estimate_raw)
    if amount is None:
        skipped_no_estimate.append(ticket)
        return 0
    if amount == 0:
        skipped_zero_hours.append(ticket)
        for login in recipients_of(ticket):
            ensure_person(login)
        return 0
    if not ticket.assignees:
        skipped_no_assignee.append(ticket)
        return 0

    recipients = recipients_of(ticket)
    amount_each = amount / len(recipients)
    item = ExpenseItem(
        title=ticket.title,
        number=ticket.number,
        url=ticket.url,
        amount=amount_each,
        occurred_at=ticket.occurred_at,
        assignees=ticket.assignees,
    )
    for login in recipients:
        key = ensure_person(login)
        amount_by_person[key] = amount_by_person.get(key, 0.0) + amount_each
        expenses_by_person[key].append(item)
    return 1


def _build_people(
    hours_by_person: dict[str, float],
    tickets_by_person: dict[str, list[TicketShare]],
    display_login: dict[str, str],
    config: AppConfig,
) -> tuple[list[PersonSlice], float, float]:
    people: list[PersonSlice] = []
    total_slices = 0.0
    total_hours = 0.0
    multiplier = config.slicing_pie.time_multiplier
    for key, hours in hours_by_person.items():
        login = display_login[key]
        user, used_default = user_for(login, config)
        if user.effective_rate == 0:
            continue
        slices = hours * user.effective_rate * multiplier
        total_slices += slices
        total_hours += hours
        people.append(
            PersonSlice(
                login=login,
                name=user.name,
                hours=hours,
                hourly_rate=user.rate,
                seniority=user.seniority,
                multiplier=multiplier,
                slices=slices,
                percent=0.0,
                used_default_rate=used_default,
                tickets=tuple(tickets_by_person.get(key, ())),
            )
        )

    people.sort(key=lambda person: (-person.slices, (person.name or person.login).lower()))
    if total_slices > 0:
        people = [
            replace(person, percent=(person.slices / total_slices) * 100.0)
            for person in people
        ]
    return people, total_slices, total_hours


def _build_expenses(
    amount_by_person: dict[str, float],
    expenses_by_person: dict[str, list[ExpenseItem]],
    display_login: dict[str, str],
    display_name: dict[str, str],
    cash_multiplier: float,
) -> tuple[list[PersonExpenses], float, float]:
    rows: list[PersonExpenses] = []
    total_amount = 0.0
    total_slices = 0.0
    for key, amount in amount_by_person.items():
        if amount <= 0:
            continue
        items = list(expenses_by_person.get(key, ()))
        items.sort(key=lambda item: (item.occurred_at or "", item.number or 0, item.title))
        slices = amount * cash_multiplier
        total_amount += amount
        total_slices += slices
        rows.append(
            PersonExpenses(
                login=display_login[key],
                name=display_name.get(key, ""),
                amount=amount,
                slices=slices,
                percent=0.0,
                items=tuple(items),
            )
        )
    rows.sort(key=lambda row: (-row.slices, (row.name or row.login).lower()))
    if total_slices > 0:
        rows = [
            replace(row, percent=(row.slices / total_slices) * 100.0) for row in rows
        ]
    return rows, total_amount, total_slices


def _build_summary(
    people: list[PersonSlice], expenses: list[PersonExpenses]
) -> tuple[list[PersonSummary], float]:
    by_key: dict[str, PersonSummary] = {}
    for person in people:
        key = person.login.lower()
        by_key[key] = PersonSummary(
            login=person.login,
            name=person.name,
            work_slices=person.slices,
            expenses=0.0,
            total=person.slices,
            percent=0.0,
        )
    for row in expenses:
        key = row.login.lower()
        current = by_key.get(key)
        if current is None:
            by_key[key] = PersonSummary(
                login=row.login,
                name=row.name,
                work_slices=0.0,
                expenses=row.slices,
                total=row.slices,
                percent=0.0,
            )
            continue
        total = current.work_slices + row.slices
        by_key[key] = PersonSummary(
            login=current.login,
            name=current.name or row.name,
            work_slices=current.work_slices,
            expenses=row.slices,
            total=total,
            percent=0.0,
        )

    rows = list(by_key.values())
    rows.sort(key=lambda row: (-row.total, (row.name or row.login).lower()))
    grand = sum(row.total for row in rows)
    if grand > 0:
        rows = [
            replace(row, percent=(row.total / grand) * 100.0) for row in rows
        ]
    return rows, grand
