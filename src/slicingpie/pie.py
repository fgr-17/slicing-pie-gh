from __future__ import annotations

from dataclasses import replace
import re

from slicingpie.config import AppConfig, PersonConfig
from slicingpie.models import PersonSlice, PieReport, Ticket, TicketShare


_ESTIMATE = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(h|hr|hrs|hora|horas)?\s*$",
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
    done_names = {value.casefold() for value in config.fields.done}
    done_tickets = [
        ticket
        for ticket in tickets
        if ticket.status is not None and ticket.status.casefold() in done_names
    ]

    hours_by_person: dict[str, float] = {}
    tickets_by_person: dict[str, list[TicketShare]] = {}
    display_login: dict[str, str] = {}
    skipped_no_estimate: list[Ticket] = []
    skipped_no_assignee: list[Ticket] = []
    skipped_zero_hours: list[Ticket] = []

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
        return key

    for ticket in done_tickets:
        _accumulate_ticket(
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

    for user in pie_cfg.users.values():
        if user.effective_rate != 0:
            ensure_person(user.login)

    people, total_slices, total_hours = _build_people(
        hours_by_person, tickets_by_person, display_login, config
    )

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
) -> None:
    hours = parse_estimate_hours(ticket.estimate_raw, hours_per_unit)
    if hours is None:
        skipped_no_estimate.append(ticket)
        return
    if hours == 0:
        skipped_zero_hours.append(ticket)
        for login in recipients_of(ticket):
            ensure_person(login)
        return
    if not ticket.assignees:
        skipped_no_assignee.append(ticket)
        return

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
