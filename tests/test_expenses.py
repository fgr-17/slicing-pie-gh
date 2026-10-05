from pathlib import Path

from helpers import sample_config, ticket
from slicingpie.config import parse_config
from slicingpie.pie import (
    build_pie,
    is_expense_ticket,
    parse_expense_amount,
)


def test_parse_expense_amount():
    assert parse_expense_amount(120) == 120.0
    assert parse_expense_amount("80,5") == 80.5
    assert parse_expense_amount("$200") == 200.0
    assert parse_expense_amount("50 USD") == 50.0
    assert parse_expense_amount(None) is None
    assert parse_expense_amount("8h") is None
    assert parse_expense_amount(-1) is None


def test_expense_tickets_are_not_work_hours():
    tickets = [
        ticket("Work", assignees=("ana",), estimate=10, number=1),
        ticket(
            "AWS",
            assignees=("ana",),
            estimate=200,
            number=2,
            labels=("[expensa]",),
            occurred_at="2026-01-10",
        ),
        ticket(
            "Domain",
            assignees=("carlos",),
            estimate=50,
            number=3,
            labels=("[Expensa]",),
            occurred_at="2026-02-05",
        ),
    ]
    report = build_pie(tickets, sample_config(), project_title="t", project_url=None)
    by_login = {person.login: person for person in report.people}
    assert by_login["ana"].hours == 10
    assert "carlos" in by_login
    assert by_login["carlos"].hours == 0
    assert report.counted_count == 1
    assert report.counted_expenses == 2
    assert report.total_expenses == 250
    assert report.cash_multiplier == 4.0
    assert report.total_expense_slices == 1000
    expenses = {row.login: row for row in report.expenses}
    assert expenses["ana"].amount == 200
    assert expenses["ana"].slices == 800
    assert expenses["carlos"].amount == 50
    assert expenses["carlos"].slices == 200
    assert expenses["ana"].items[0].occurred_at == "2026-01-10"


def test_expense_label_and_currency_from_config():
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {"time_multiplier": 2, "default_hourly_rate": 50},
            "rates": {"ana": 75},
            "expenses": {"label": "cash", "currency": "eur", "cash_multiplier": 4},
            "display": {"language": "es"},
        },
        Path("x.toml"),
    )
    assert config.expenses.label == "cash"
    assert config.expenses.currency == "EUR"
    assert config.expenses.cash_multiplier == 4.0
    ticket_row = ticket("Pay", labels=("cash",), estimate=40)
    assert is_expense_ticket(ticket_row, config.expenses.label)
    report = build_pie(
        [ticket_row], config, project_title="t", project_url=None
    )
    assert report.expense_currency == "EUR"
    assert report.total_expenses == 40
    assert report.total_expense_slices == 160
    assert report.counted_count == 0
    assert report.people[0].hours == 0


def test_summary_combines_work_and_expenses():
    tickets = [
        ticket("Work", assignees=("ana",), estimate=2, number=1),
        ticket(
            "Ads",
            assignees=("ana",),
            estimate=100,
            number=2,
            labels=("[expensa]",),
            occurred_at="2026-03-01",
        ),
    ]
    report = build_pie(tickets, sample_config(), project_title="t", project_url=None)
    # ana work slices = 2 * 75 * 2 = 300; expense slices = 100 * 4 = 400; total = 700
    summary = {row.login: row for row in report.summary}
    assert summary["ana"].work_slices == 300
    assert summary["ana"].expenses == 400
    assert summary["ana"].total == 700
    assert report.total_contribution == 700


def test_demo_includes_expenses():
    from slicingpie.mock import demo_tickets

    report = build_pie(
        demo_tickets(),
        sample_config(),
        project_title="demo",
        project_url=None,
    )
    assert report.total_hours == 82
    assert report.total_expenses == 330
    assert report.total_expense_slices == 1320
    assert report.counted_expenses == 3
    assert report.done_count == 14
    assert report.counted_count == 8
    months = {
        item.occurred_at[:7]
        for row in report.expenses
        for item in row.items
        if item.occurred_at
    }
    assert months == {"2026-01", "2026-02"}
