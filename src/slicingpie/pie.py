from __future__ import annotations

import re

from slicingpie.config import AppConfig
from slicingpie.models import PersonSlice, PieReport, Ticket, TicketShare


_ESTIMATE = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(h|hr|hrs|hora|horas)?\s*$",
    re.IGNORECASE,
)


def parse_estimate_hours(value: object, hours_per_unit: float) -> float | None:
    """Convierte el campo estimado a horas de trabajo."""
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


def rate_for(login: str, config: AppConfig) -> tuple[float, bool]:
    rates = config.slicing_pie.rates
    key = login.lower()
    if key in rates:
        return rates[key], False
    return config.slicing_pie.default_hourly_rate, True


def build_pie(tickets: list[Ticket], config: AppConfig, *, project_title: str, project_url: str | None) -> PieReport:
    pie_cfg = config.slicing_pie
    done_names = {value.casefold() for value in config.fields.done}

    skipped_no_estimate: list[Ticket] = []
    skipped_no_assignee: list[Ticket] = []
    skipped_zero_hours: list[Ticket] = []

    hours_by_person: dict[str, float] = {}
    tickets_by_person: dict[str, list[TicketShare]] = {}
    display_login: dict[str, str] = {}

    done_tickets = [
        ticket
        for ticket in tickets
        if ticket.status is not None and ticket.status.casefold() in done_names
    ]

    for ticket in done_tickets:
        hours = parse_estimate_hours(ticket.estimate_raw, pie_cfg.hours_per_estimate_unit)
        if hours is None:
            skipped_no_estimate.append(ticket)
            continue
        if hours == 0:
            skipped_zero_hours.append(ticket)
            continue
        if not ticket.assignees:
            skipped_no_assignee.append(ticket)
            continue

        recipients = (
            ticket.assignees
            if pie_cfg.split_among_assignees
            else ticket.assignees[:1]
        )
        hours_each = hours / len(recipients)
        share = TicketShare(
            title=ticket.title,
            number=ticket.number,
            url=ticket.url,
            hours=hours_each,
            assignees=ticket.assignees,
        )
        for login in recipients:
            key = login.lower()
            display_login.setdefault(key, login)
            hours_by_person[key] = hours_by_person.get(key, 0.0) + hours_each
            tickets_by_person.setdefault(key, []).append(share)

    people: list[PersonSlice] = []
    total_slices = 0.0
    total_hours = 0.0
    for key, hours in hours_by_person.items():
        login = display_login[key]
        hourly_rate, used_default = rate_for(login, config)
        slices = hours * hourly_rate * pie_cfg.time_multiplier
        total_slices += slices
        total_hours += hours
        people.append(
            PersonSlice(
                login=login,
                hours=hours,
                hourly_rate=hourly_rate,
                multiplier=pie_cfg.time_multiplier,
                slices=slices,
                percent=0.0,
                used_default_rate=used_default,
                tickets=tuple(tickets_by_person.get(key, ())),
            )
        )

    people.sort(key=lambda person: (-person.slices, person.login.lower()))
    if total_slices > 0:
        people = [
            PersonSlice(
                login=person.login,
                hours=person.hours,
                hourly_rate=person.hourly_rate,
                multiplier=person.multiplier,
                slices=person.slices,
                percent=(person.slices / total_slices) * 100.0,
                used_default_rate=person.used_default_rate,
                tickets=person.tickets,
            )
            for person in people
        ]

    return PieReport(
        project_title=project_title,
        project_url=project_url,
        people=tuple(people),
        total_hours=total_hours,
        total_slices=total_slices,
        done_count=len(done_tickets),
        counted_count=len(done_tickets)
        - len(skipped_no_estimate)
        - len(skipped_no_assignee)
        - len(skipped_zero_hours),
        skipped_no_estimate=tuple(skipped_no_estimate),
        skipped_no_assignee=tuple(skipped_no_assignee),
        skipped_zero_hours=tuple(skipped_zero_hours),
        time_multiplier=pie_cfg.time_multiplier,
        default_hourly_rate=pie_cfg.default_hourly_rate,
    )
