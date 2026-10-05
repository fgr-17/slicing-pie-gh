from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ticket:
    title: str
    number: int | None
    url: str | None
    assignees: tuple[str, ...]
    status: str | None
    estimate_raw: float | str | None
    item_type: str
    labels: tuple[str, ...] = ()
    occurred_at: str | None = None


@dataclass(frozen=True)
class TicketShare:
    title: str
    number: int | None
    url: str | None
    hours: float
    assignees: tuple[str, ...]


@dataclass(frozen=True)
class PersonSlice:
    login: str
    name: str
    hours: float
    hourly_rate: float
    seniority: float
    multiplier: float
    slices: float
    percent: float
    used_default_rate: bool
    tickets: tuple[TicketShare, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExpenseItem:
    title: str
    number: int | None
    url: str | None
    amount: float
    occurred_at: str | None
    assignees: tuple[str, ...]


@dataclass(frozen=True)
class PersonExpenses:
    login: str
    name: str
    amount: float
    slices: float
    percent: float
    items: tuple[ExpenseItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PersonSummary:
    login: str
    name: str
    work_slices: float
    expenses: float
    total: float
    percent: float


@dataclass(frozen=True)
class PieReport:
    project_title: str
    project_url: str | None
    people: tuple[PersonSlice, ...]
    total_hours: float
    total_slices: float
    done_count: int
    counted_count: int
    skipped_no_estimate: tuple[Ticket, ...]
    skipped_no_assignee: tuple[Ticket, ...]
    skipped_zero_hours: tuple[Ticket, ...]
    time_multiplier: float
    default_hourly_rate: float
    effort_unit: str = "hours"
    hours_per_day: float = 8.0
    days_per_story_point: float = 1.0
    hours_per_estimate_unit: float = 1.0
    expenses: tuple[PersonExpenses, ...] = ()
    total_expenses: float = 0.0
    total_expense_slices: float = 0.0
    counted_expenses: int = 0
    expense_currency: str = "USD"
    expense_label: str = ""
    cash_multiplier: float = 4.0
    summary: tuple[PersonSummary, ...] = ()
    total_contribution: float = 0.0
