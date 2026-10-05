from slicingpie.pie import build_pie, parse_estimate_hours
from slicingpie.config import ConfigError, parse_config
from pathlib import Path

import pytest

from helpers import sample_config, ticket


def test_parse_numeric_hours():
    assert parse_estimate_hours(8, 1.0) == 8.0
    assert parse_estimate_hours(2.5, 4.0) == 10.0


def test_parse_text_hours_and_points():
    assert parse_estimate_hours("8h", 4.0) == 8.0
    assert parse_estimate_hours("8 horas", 1.0) == 8.0
    assert parse_estimate_hours("8", 4.0) == 32.0
    assert parse_estimate_hours("8,5", 1.0) == 8.5
    assert parse_estimate_hours("no sé", 1.0) is None
    assert parse_estimate_hours(None, 1.0) is None
    assert parse_estimate_hours(-3, 1.0) is None


def test_demo_pie_matches_slicing_pie_formula():
    from slicingpie.mock import demo_tickets

    report = build_pie(
        demo_tickets(),
        sample_config(),
        project_title="demo",
        project_url=None,
    )
    by_login = {person.login: person for person in report.people}

    assert by_login["ana"].hours == 31
    assert by_login["carlos"].hours == 22
    assert by_login["maria"].hours == 29
    assert by_login["ana"].slices == 31 * 75 * 2
    assert by_login["carlos"].slices == 22 * 50 * 2
    assert by_login["maria"].slices == 29 * 65 * 2
    assert report.total_hours == 82
    assert report.total_slices == 10620
    assert abs(sum(person.percent for person in report.people) - 100) < 1e-9
    assert report.skipped_no_estimate[0].number == 30
    assert report.skipped_no_assignee[0].number == 31
    assert report.skipped_zero_hours[0].number == 32
    assert report.done_count == 14
    assert report.counted_count == 8
    assert report.counted_expenses == 3
    assert report.total_expenses == 330
    assert report.total_expense_slices == 1320


def test_split_and_first_assignee_only():
    tickets = [ticket("Pair", assignees=("ana", "carlos"), estimate=10)]
    split = build_pie(tickets, sample_config(), project_title="t", project_url=None)
    assert {p.login: p.hours for p in split.people} == {
        "ana": 5.0,
        "carlos": 5.0,
        "maria": 0.0,
    }

    first_only = build_pie(
        tickets,
        sample_config(split_among_assignees=False),
        project_title="t",
        project_url=None,
    )
    assert {p.login: p.hours for p in first_only.people} == {
        "ana": 10.0,
        "carlos": 0.0,
        "maria": 0.0,
    }


def test_ignores_tickets_not_done():
    tickets = [
        ticket("WIP", status="In Progress", estimate=40),
        ticket("Listo ES", status="Listo", estimate=3, assignees=("maria",)),
    ]
    report = build_pie(tickets, sample_config(), project_title="t", project_url=None)
    assert report.done_count == 1
    assert report.people[0].login == "maria"
    assert report.people[0].hours == 3


def test_default_rate_flag():
    tickets = [ticket("X", assignees=("nuevo",), estimate=2)]
    report = build_pie(tickets, sample_config(), project_title="t", project_url=None)
    person = report.people[0]
    assert person.used_default_rate is True
    assert person.hourly_rate == 50
    assert person.slices == 2 * 50 * 2


def test_zero_rate_hidden_zero_hours_with_rate_shown():
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {"time_multiplier": 2, "default_hourly_rate": 50},
            "rates": {"ana": 0, "bob": 40, "cara": 10, "ghost": 0},
        },
        Path("x.toml"),
    )
    tickets = [
        ticket("Ana", assignees=("ana",), estimate=8, number=1),
        ticket("Bob", assignees=("bob",), estimate=0, number=2),
        ticket("Dan", assignees=("dan",), estimate=4, number=3),
    ]
    report = build_pie(tickets, config, project_title="t", project_url=None)
    by_login = {person.login: person for person in report.people}

    assert "ana" not in by_login
    assert "ghost" not in by_login
    assert by_login["bob"].hours == 0
    assert by_login["bob"].hourly_rate == 40
    assert by_login["bob"].slices == 0
    assert by_login["cara"].hours == 0
    assert by_login["cara"].slices == 0
    assert by_login["dan"].hours == 4
    assert by_login["dan"].slices == 4 * 50 * 2
    assert report.total_hours == 4
    assert report.total_slices == 400
    assert by_login["dan"].percent == 100


def test_seniority_scales_rate_and_name_is_kept():
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {"time_multiplier": 2, "default_hourly_rate": 50},
            "users": [
                {
                    "login": "ana",
                    "name": "Ana Perez",
                    "rate": 50,
                    "seniority": 2,
                },
                {"login": "nulo", "name": "Nulo", "rate": 80, "seniority": 0},
            ],
        },
        Path("x.toml"),
    )
    report = build_pie(
        [ticket("Ana", assignees=("ana",), estimate=4, number=1)],
        config,
        project_title="t",
        project_url=None,
    )
    assert [person.login for person in report.people] == ["ana"]
    person = report.people[0]
    assert person.name == "Ana Perez"
    assert person.hourly_rate == 50
    assert person.seniority == 2
    assert person.slices == 4 * 50 * 2 * 2
    assert report.total_slices == person.slices


def test_users_reject_negative_seniority():
    with pytest.raises(ConfigError, match="seniority"):
        parse_config(
            {
                "mode": "demo",
                "users": [{"login": "ana", "rate": 10, "seniority": -1}],
            },
            Path("x.toml"),
        )


def test_empty_pie():
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {"default_hourly_rate": 50},
            "rates": {},
        },
        Path("x.toml"),
    )
    report = build_pie([], config, project_title="t", project_url=None)
    assert report.people == ()
    assert report.total_slices == 0


def test_config_rejects_bad_mode():
    with pytest.raises(ConfigError, match="mode"):
        parse_config({"mode": "nope"}, Path("x.toml"))
