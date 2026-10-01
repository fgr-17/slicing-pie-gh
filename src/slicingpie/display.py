from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from slicingpie.models import PieReport, Ticket

BAR_WIDTH = 28


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


def render_report(report: PieReport, *, verbose: bool, currency_symbol: str) -> None:
    console = Console()
    subtitle_parts = [
        f"Done: {report.done_count}",
        f"contados: {report.counted_count}",
    ]
    skipped = (
        len(report.skipped_no_estimate)
        + len(report.skipped_no_assignee)
        + len(report.skipped_zero_hours)
    )
    if skipped:
        subtitle_parts.append(f"omitidos: {skipped}")

    title = Text()
    title.append("SLICING PIE", style="bold")
    title.append("  ·  horas de trabajo")
    body = Text()
    body.append(report.project_title, style="bold cyan")
    if report.project_url:
        body.append(f"\n{report.project_url}", style="dim")
    body.append("\n" + "  ·  ".join(subtitle_parts), style="dim")
    body.append(
        f"\nRebanadas = horas × tarifa × {format_hours(report.time_multiplier)} "
        "(tiempo no pagado)",
        style="dim",
    )
    console.print(Panel(body, title=title, border_style="magenta"))

    if not report.people:
        console.print(
            "\n[yellow]No hay tickets Done con asignado y estimado para armar el pie.[/yellow]"
        )
        _print_skipped(console, report)
        return

    table = Table(
        title="Rebanadas por persona",
        title_style="bold",
        show_lines=False,
        pad_edge=True,
    )
    table.add_column("Persona", style="cyan", no_wrap=True)
    table.add_column("Horas", justify="right")
    table.add_column("Tarifa", justify="right")
    table.add_column("Rebanadas", justify="right")
    table.add_column("% pie", justify="right", style="bold")

    for person in report.people:
        rate = format_amount(person.hourly_rate, currency_symbol)
        if person.used_default_rate:
            rate += "*"
        table.add_row(
            person.login,
            format_hours(person.hours),
            rate,
            format_amount(person.slices, currency_symbol),
            format_percent(person.percent),
        )

    table.add_section()
    table.add_row(
        "total",
        format_hours(report.total_hours),
        "",
        format_amount(report.total_slices, currency_symbol),
        "100,0%",
        style="bold",
    )
    console.print(table)

    if any(person.used_default_rate for person in report.people):
        console.print(
            f"[dim]* tarifa por defecto ({format_amount(report.default_hourly_rate, currency_symbol)}/h). "
            "Añádela en [rates] del archivo de config.[/dim]"
        )

    console.print()
    dist = Table(title="Distribución", show_header=False, box=None, padding=(0, 1))
    dist.add_column("Persona", style="cyan", no_wrap=True)
    dist.add_column("Barra")
    dist.add_column("%", justify="right")
    for person in report.people:
        filled = int(round((person.percent / 100.0) * BAR_WIDTH))
        filled = min(BAR_WIDTH, max(filled, 1 if person.percent > 0 else 0))
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        dist.add_row(person.login, f"[magenta]{bar}[/magenta]", format_percent(person.percent))
    console.print(dist)

    if verbose:
        _print_tickets(console, report)

    _print_skipped(console, report)


def _print_tickets(console: Console, report: PieReport) -> None:
    console.print()
    table = Table(title="Tickets contados por persona", show_lines=False)
    table.add_column("Persona", style="cyan")
    table.add_column("Ticket")
    table.add_column("Horas", justify="right")
    for person in report.people:
        for index, share in enumerate(person.tickets):
            table.add_row(
                person.login if index == 0 else "",
                ticket_label(share),
                format_hours(share.hours),
            )
    console.print(table)


def _print_skipped(console: Console, report: PieReport) -> None:
    groups = (
        ("sin estimado", report.skipped_no_estimate),
        ("sin asignado", report.skipped_no_assignee),
        ("con 0 horas", report.skipped_zero_hours),
    )
    pending = [(label, tickets) for label, tickets in groups if tickets]
    if not pending:
        return
    console.print()
    table = Table(title="Tickets Done omitidos", show_lines=False)
    table.add_column("Motivo", style="yellow")
    table.add_column("Ticket")
    for label, tickets in pending:
        for index, ticket in enumerate(tickets):
            table.add_row(label if index == 0 else "", ticket_label(ticket))
    console.print(table)


def report_to_json(report: PieReport) -> str:
    payload = {
        "project": {"title": report.project_title, "url": report.project_url},
        "formula": {
            "slices": "hours * hourly_rate * time_multiplier",
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
                "hours": person.hours,
                "hourly_rate": person.hourly_rate,
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


def _ticket_json(ticket: Ticket) -> dict:
    return {
        "title": ticket.title,
        "number": ticket.number,
        "url": ticket.url,
        "assignees": list(ticket.assignees),
        "status": ticket.status,
        "estimate": ticket.estimate_raw,
    }
