from __future__ import annotations

import json
from contextlib import contextmanager
from collections.abc import Iterator

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

from slicingpie.i18n import t
from slicingpie.models import PieReport, Ticket

BAR_WIDTH = 28


@contextmanager
def waiting(message: str) -> Iterator[None]:
    """Show a spinner on stderr while a long task runs."""
    console = Console(stderr=True)
    if not console.is_terminal:
        yield
        return
    with Status(f"[cyan]{message}", console=console, spinner="line"):
        yield


def clear_screen() -> None:
    console = Console()
    if console.is_terminal:
        console.clear()


def format_hours(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}"
    return f"{value:.1f}".replace(".", ",")


def format_amount(value: float, symbol: str) -> str:
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{symbol}{formatted}"


def format_percent(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


def ticket_label(ticket: Ticket | object) -> str:
    number = getattr(ticket, "number", None)
    title = getattr(ticket, "title", "")
    if number is not None:
        return f"#{number} {title}"
    return title


def render_report(
    report: PieReport,
    *,
    verbose: bool,
    currency_symbol: str,
    show_no_estimate: bool = False,
    show_unassigned: bool = False,
) -> None:
    console = Console()
    subtitle_parts = [
        f"Done: {report.done_count}",
        t("display.counted", count=report.counted_count),
    ]
    skipped = (
        len(report.skipped_no_estimate)
        + len(report.skipped_no_assignee)
        + len(report.skipped_zero_hours)
    )
    if skipped:
        subtitle_parts.append(t("display.skipped", count=skipped))

    title = Text()
    title.append("SLICING PIE", style="bold")
    title.append(t("display.subtitle_hours"))
    body = Text()
    body.append(report.project_title, style="bold cyan")
    if report.project_url:
        body.append(f"\n{report.project_url}", style="dim")
    body.append("\n" + "  -  ".join(subtitle_parts), style="dim")
    body.append(
        t("display.formula", multiplier=format_hours(report.time_multiplier)),
        style="dim",
    )
    console.print(Panel(body, title=title, border_style="magenta"))

    if not report.people:
        console.print(t("display.empty"))
        _print_skipped(
            console,
            report,
            show_no_estimate=show_no_estimate,
            show_unassigned=show_unassigned,
        )
        return

    table = Table(
        title=t("display.table.title"),
        title_style="bold",
        show_lines=False,
        pad_edge=True,
    )
    table.add_column(t("display.col.person"), style="cyan", no_wrap=True)
    table.add_column(t("display.col.hours"), justify="right")
    table.add_column(t("display.col.rate"), justify="right")
    table.add_column(t("display.col.seniority"), justify="right")
    table.add_column(t("display.col.slices"), justify="right")
    table.add_column(t("display.col.percent"), justify="right", style="bold")

    for person in report.people:
        rate = format_amount(person.hourly_rate, currency_symbol)
        if person.used_default_rate:
            rate += "*"
        table.add_row(
            _person_label(person),
            format_hours(person.hours),
            rate,
            format_hours(person.seniority),
            format_amount(person.slices, currency_symbol),
            format_percent(person.percent),
        )

    table.add_section()
    table.add_row(
        "total",
        format_hours(report.total_hours),
        "",
        "",
        format_amount(report.total_slices, currency_symbol),
        "100,0%",
        style="bold",
    )
    console.print(table)

    if any(person.used_default_rate for person in report.people):
        console.print(
            t(
                "display.default_rate_hint",
                rate=format_amount(report.default_hourly_rate, currency_symbol),
            )
        )

    console.print()
    dist = Table(
        title=t("display.distribution"),
        show_header=False,
        box=None,
        padding=(0, 1),
    )
    dist.add_column(t("display.col.person"), style="cyan", no_wrap=True)
    dist.add_column(t("display.col.bar"))
    dist.add_column("%", justify="right")
    for person in report.people:
        filled = int(round((person.percent / 100.0) * BAR_WIDTH))
        filled = min(BAR_WIDTH, max(filled, 1 if person.percent > 0 else 0))
        bar = "#" * filled + "-" * (BAR_WIDTH - filled)
        dist.add_row(
            _person_label(person),
            f"[magenta]{bar}[/magenta]",
            format_percent(person.percent),
        )
    console.print(dist)

    if verbose:
        _print_tickets(console, report)

    _print_skipped(
        console,
        report,
        show_no_estimate=show_no_estimate,
        show_unassigned=show_unassigned,
    )


def _print_tickets(console: Console, report: PieReport) -> None:
    console.print()
    table = Table(title=t("display.tickets_title"), show_lines=False)
    table.add_column(t("display.col.person"), style="cyan")
    table.add_column("Ticket")
    table.add_column(t("display.col.hours"), justify="right")
    for person in report.people:
        for index, share in enumerate(person.tickets):
            table.add_row(
                _person_label(person) if index == 0 else "",
                ticket_label(share),
                format_hours(share.hours),
            )
    console.print(table)


def _print_skipped(
    console: Console,
    report: PieReport,
    *,
    show_no_estimate: bool,
    show_unassigned: bool,
) -> None:
    groups = []
    if show_no_estimate:
        groups.append((t("display.skip.no_estimate"), report.skipped_no_estimate))
    if show_unassigned:
        groups.append((t("display.skip.no_assignee"), report.skipped_no_assignee))
    groups.append((t("display.skip.zero_hours"), report.skipped_zero_hours))
    pending = [(label, tickets) for label, tickets in groups if tickets]
    if not pending:
        return
    console.print()
    table = Table(title=t("display.skipped_title"), show_lines=False)
    table.add_column(t("display.col.reason"), style="yellow")
    table.add_column("Ticket")
    for label, tickets in pending:
        for index, ticket in enumerate(tickets):
            table.add_row(label if index == 0 else "", ticket_label(ticket))
    console.print(table)


def report_to_json(report: PieReport) -> str:
    payload = {
        "project": {"title": report.project_title, "url": report.project_url},
        "formula": {
            "slices": "hours * hourly_rate * seniority * time_multiplier",
            "time_multiplier": report.time_multiplier,
            "default_hourly_rate": report.default_hourly_rate,
        },
        "totals": {
            "hours": report.total_hours,
            "slices": report.total_slices,
            "done": report.done_count,
            "counted": report.counted_count,
        },
        "people": [
            {
                "login": person.login,
                "name": person.name,
                "hours": person.hours,
                "hourly_rate": person.hourly_rate,
                "seniority": person.seniority,
                "slices": person.slices,
                "percent": person.percent,
                "used_default_rate": person.used_default_rate,
                "tickets": [
                    {
                        "title": share.title,
                        "number": share.number,
                        "url": share.url,
                        "hours": share.hours,
                        "assignees": list(share.assignees),
                    }
                    for share in person.tickets
                ],
            }
            for person in report.people
        ],
        "skipped": {
            "no_estimate": [_ticket_json(ticket) for ticket in report.skipped_no_estimate],
            "no_assignee": [_ticket_json(ticket) for ticket in report.skipped_no_assignee],
            "zero_hours": [_ticket_json(ticket) for ticket in report.skipped_zero_hours],
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _person_label(person: object) -> str:
    name = str(getattr(person, "name", "") or "").strip()
    if name:
        return name
    return str(getattr(person, "login", ""))


def _ticket_json(ticket: Ticket) -> dict:
    return {
        "title": ticket.title,
        "number": ticket.number,
        "url": ticket.url,
        "assignees": list(ticket.assignees),
        "status": ticket.status,
        "estimate": ticket.estimate_raw,
    }
