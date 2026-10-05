from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from collections.abc import Iterator

from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

from slicingpie.display_json import report_to_json
from slicingpie.i18n import t
from slicingpie.models import ExpenseItem, PersonExpenses, PieReport, Ticket

BAR_WIDTH = 28
# Full / light block for the final distribution chart (terminal bar).
BAR_FILLED = "\u2588"
BAR_EMPTY = "\u2591"

__all__ = [
    "waiting",
    "clear_screen",
    "format_hours",
    "format_amount",
    "format_percent",
    "ticket_label",
    "render_report",
    "report_to_json",
]


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
    show_skipped: bool = False,
    detail_expenses: bool = False,
    detail_review: bool = False,
) -> None:
    console = Console()
    subtitle_parts = [
        f"Done: {report.done_count}",
        t("display.counted", count=report.counted_count),
    ]
    if report.counted_expenses:
        subtitle_parts.append(
            t("display.counted_expenses", count=report.counted_expenses)
        )
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
    console.print(Panel(body, title=title, border_style="magenta"))

    if not report.people and not report.expenses:
        console.print(t("display.empty"))
        _print_skipped(
            console,
            report,
            show_no_estimate=show_no_estimate,
            show_unassigned=show_unassigned,
            show_skipped=show_skipped,
        )
        return

    detail_only = detail_expenses or detail_review
    if detail_only:
        if detail_expenses:
            console.print()
            if report.expenses:
                _print_expense_detail(console, report, currency_symbol)
            else:
                console.print(t("display.expenses.empty_detail"))
        if detail_review:
            console.print()
            _print_review_detail(console, report)
        _print_skipped(
            console,
            report,
            show_no_estimate=show_no_estimate,
            show_unassigned=show_unassigned,
            show_skipped=show_skipped,
        )
        return

    if report.people:
        _print_work_table(console, report, currency_symbol)
        if any(person.used_default_rate for person in report.people):
            console.print(
                t(
                    "display.default_rate_hint",
                    rate=format_amount(report.default_hourly_rate, currency_symbol),
                )
            )
        if verbose:
            _print_tickets(console, report)

    if report.expenses:
        console.print()
        _print_expenses_table(console, report, currency_symbol)

    if report.summary:
        console.print()
        _print_summary_table(console, report, currency_symbol)
        console.print()
        _print_distribution(console, report)

    _print_skipped(
        console,
        report,
        show_no_estimate=show_no_estimate,
        show_unassigned=show_unassigned,
        show_skipped=show_skipped,
    )


def _print_work_table(
    console: Console, report: PieReport, currency_symbol: str
) -> None:
    table = Table(
        title=Text(t("display.table.title"), style="bold"),
        caption=t(
            "display.table.caption",
            multiplier=format_hours(report.time_multiplier),
            effort_unit=report.effort_unit,
            hours_per_unit=format_hours(report.hours_per_estimate_unit),
        ),
        caption_style="dim",
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


def _print_distribution(console: Console, report: PieReport) -> None:
    if not report.summary:
        return
    dist = Table(
        title=Text(t("display.distribution"), style="bold"),
        caption=t("display.distribution.caption"),
        caption_style="dim",
        show_header=False,
        box=None,
        padding=(0, 1),
    )
    dist.add_column(t("display.col.person"), style="cyan", no_wrap=True)
    dist.add_column(t("display.col.bar"))
    dist.add_column("%", justify="right")
    for row in report.summary:
        filled = int(round((row.percent / 100.0) * BAR_WIDTH))
        filled = min(BAR_WIDTH, max(filled, 1 if row.percent > 0 else 0))
        bar = BAR_FILLED * filled + BAR_EMPTY * (BAR_WIDTH - filled)
        dist.add_row(
            _person_label(row),
            f"[magenta]{bar}[/magenta]",
            format_percent(row.percent),
        )
    console.print(dist)


def _print_expenses_table(
    console: Console, report: PieReport, currency_symbol: str
) -> None:
    table = Table(
        title=Text(
            t(
                "display.expenses.title",
                currency=report.expense_currency,
                label=report.expense_label,
            ),
            style="bold",
        ),
        caption=t(
            "display.expenses.caption",
            multiplier=format_hours(report.cash_multiplier),
        ),
        caption_style="dim",
        show_lines=False,
        pad_edge=True,
    )
    table.add_column(t("display.col.person"), style="cyan", no_wrap=True)
    table.add_column(t("display.col.amount"), justify="right")
    table.add_column(t("display.col.slices"), justify="right")
    table.add_column(t("display.col.percent"), justify="right", style="bold")
    for row in report.expenses:
        table.add_row(
            _person_label(row),
            format_amount(row.amount, currency_symbol),
            format_amount(row.slices, currency_symbol),
            format_percent(row.percent),
        )
    table.add_section()
    table.add_row(
        "total",
        format_amount(report.total_expenses, currency_symbol),
        format_amount(report.total_expense_slices, currency_symbol),
        "100,0%",
        style="bold",
    )
    console.print(table)


def _print_summary_table(
    console: Console, report: PieReport, currency_symbol: str
) -> None:
    table = Table(
        title=Text(t("display.summary.title"), style="bold"),
        caption=t(
            "display.summary.caption",
            time_multiplier=format_hours(report.time_multiplier),
            cash_multiplier=format_hours(report.cash_multiplier),
        ),
        caption_style="dim",
        show_lines=False,
        pad_edge=True,
    )
    table.add_column(t("display.col.person"), style="cyan", no_wrap=True)
    table.add_column(t("display.col.work_slices"), justify="right")
    table.add_column(t("display.col.expenses"), justify="right")
    table.add_column(t("display.col.total"), justify="right")
    table.add_column(t("display.col.percent"), justify="right", style="bold")
    for row in report.summary:
        table.add_row(
            _person_label(row),
            format_amount(row.work_slices, currency_symbol),
            format_amount(row.expenses, currency_symbol),
            format_amount(row.total, currency_symbol),
            format_percent(row.percent),
        )
    table.add_section()
    table.add_row(
        "total",
        format_amount(report.total_slices, currency_symbol),
        format_amount(report.total_expense_slices, currency_symbol),
        format_amount(report.total_contribution, currency_symbol),
        "100,0%",
        style="bold",
    )
    console.print(table)


def _print_expense_detail(
    console: Console, report: PieReport, currency_symbol: str
) -> None:
    table = Table(
        title=Text(t("display.expenses.detail_title"), style="bold"),
        caption=t(
            "display.expenses.detail_caption",
            multiplier=format_hours(report.cash_multiplier),
        ),
        caption_style="dim",
        show_lines=False,
        pad_edge=True,
    )
    table.add_column(t("display.col.person"), style="cyan", no_wrap=True)
    table.add_column(t("display.col.month"), no_wrap=True)
    table.add_column(t("display.col.date"), no_wrap=True)
    table.add_column("Ticket")
    table.add_column(t("display.col.expenses"), justify="right")

    for person in report.expenses:
        rows = _detail_rows(person)
        for index, (month, date, item) in enumerate(rows):
            table.add_row(
                _person_label(person) if index == 0 else "",
                month,
                date,
                ticket_label(item),
                format_amount(item.amount, currency_symbol),
            )
    console.print(table)


def _print_review_detail(console: Console, report: PieReport) -> None:
    rows = _review_detail_rows(report)
    if not rows:
        console.print(t("display.review.empty"))
        return
    table = Table(
        title=Text(t("display.review.detail_title"), style="bold"),
        caption=t(
            "display.review.detail_caption",
            percent=format_hours(report.review_percent),
            multiplier=format_hours(report.time_multiplier),
        ),
        caption_style="dim",
        show_lines=False,
        pad_edge=True,
    )
    table.add_column(t("display.col.person"), style="cyan", no_wrap=True)
    table.add_column("Ticket")
    table.add_column(t("display.col.hours"), justify="right")
    for index, (person_label, share) in enumerate(rows):
        prev = rows[index - 1][0] if index else None
        table.add_row(
            person_label if person_label != prev else "",
            ticket_label(share),
            format_hours(share.hours),
        )
    console.print(table)


def _review_detail_rows(
    report: PieReport,
) -> list[tuple[str, object]]:
    rows: list[tuple[str, object]] = []
    for person in report.people:
        label = _person_label(person)
        for share in person.tickets:
            if share.role != "review":
                continue
            rows.append((label, share))
    return rows


def _detail_rows(
    person: PersonExpenses,
) -> list[tuple[str, str, ExpenseItem]]:
    by_month: dict[str, list[ExpenseItem]] = defaultdict(list)
    for item in person.items:
        month = (item.occurred_at or "")[:7] or t("display.col.no_date")
        by_month[month].append(item)

    rows: list[tuple[str, str, ExpenseItem]] = []
    for month in sorted(by_month):
        items = sorted(
            by_month[month],
            key=lambda item: (item.occurred_at or "", item.number or 0, item.title),
        )
        for item in items:
            date = item.occurred_at or t("display.col.no_date")
            rows.append((month, date, item))
    return rows


def _print_tickets(console: Console, report: PieReport) -> None:
    console.print()
    table = Table(
        title=Text(t("display.tickets_title"), style="bold"),
        show_lines=False,
    )
    table.add_column(t("display.col.person"), style="cyan")
    table.add_column("Ticket")
    table.add_column(t("display.col.role"))
    table.add_column(t("display.col.hours"), justify="right")
    for person in report.people:
        for index, share in enumerate(person.tickets):
            role_key = (
                "display.role.review"
                if share.role == "review"
                else "display.role.work"
            )
            table.add_row(
                _person_label(person) if index == 0 else "",
                ticket_label(share),
                t(role_key),
                format_hours(share.hours),
            )
    console.print(table)


def _print_skipped(
    console: Console,
    report: PieReport,
    *,
    show_no_estimate: bool,
    show_unassigned: bool,
    show_skipped: bool,
) -> None:
    if not (show_skipped or show_no_estimate or show_unassigned):
        return
    groups = []
    if show_skipped or show_no_estimate:
        groups.append((t("display.skip.no_estimate"), report.skipped_no_estimate))
    if show_skipped or show_unassigned:
        groups.append((t("display.skip.no_assignee"), report.skipped_no_assignee))
    if show_skipped:
        groups.append((t("display.skip.zero_hours"), report.skipped_zero_hours))
    pending = [(label, tickets) for label, tickets in groups if tickets]
    if not pending:
        return
    console.print()
    table = Table(
        title=Text(t("display.skipped_title"), style="bold"),
        show_lines=False,
    )
    table.add_column(t("display.col.reason"), style="yellow")
    table.add_column("Ticket")
    for label, tickets in pending:
        for index, ticket in enumerate(tickets):
            table.add_row(label if index == 0 else "", ticket_label(ticket))
    console.print(table)


def _person_label(person: object) -> str:
    name = str(getattr(person, "name", "") or "").strip()
    if name:
        return name
    return str(getattr(person, "login", ""))
