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
