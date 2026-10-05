from pathlib import Path

from helpers import sample_config, ticket
from slicingpie.config import hours_per_effort_unit, parse_config
from slicingpie.pie import build_pie, parse_estimate_hours


def test_hours_per_effort_unit_factors():
    assert hours_per_effort_unit("hours", hours_per_day=8, days_per_story_point=1) == 1.0
    assert hours_per_effort_unit("days", hours_per_day=2, days_per_story_point=1) == 2.0
    assert (
        hours_per_effort_unit("story_points", hours_per_day=8, days_per_story_point=0.5)
        == 4.0
    )


def test_parse_estimate_is_numeric_only():
    assert parse_estimate_hours(2, 2.0) == 4.0
    assert parse_estimate_hours("2", 2.0) == 4.0
    assert parse_estimate_hours("8h", 4.0) is None
    assert parse_estimate_hours("2d", 1.0) is None
    assert parse_estimate_hours("3sp", 1.0) is None


def test_config_days_effort_unit():
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {
                "effort_unit": "days",
                "hours_per_day": 2.0,
                "default_hourly_rate": 50,
            },
            "rates": {"ana": 75},
            "display": {"language": "es"},
        },
        Path("x.toml"),
    )
    assert config.slicing_pie.effort_unit == "days"
    assert config.slicing_pie.hours_per_estimate_unit == 2.0
    report = build_pie(
        [ticket("Day", assignees=("ana",), estimate=3, number=1)],
        config,
        project_title="t",
        project_url=None,
    )
    # 3 days * 2 h/day = 6 hours
    assert report.people[0].hours == 6.0
    assert report.effort_unit == "days"


def test_config_story_points_via_days():
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {
                "effort_unit": "story_points",
                "days_per_story_point": 0.5,
                "hours_per_day": 8.0,
                "default_hourly_rate": 50,
            },
            "rates": {"ana": 75},
            "display": {"language": "es"},
        },
        Path("x.toml"),
    )
    assert config.slicing_pie.hours_per_estimate_unit == 4.0
    report = build_pie(
        [ticket("SP", assignees=("ana",), estimate=2, number=1)],
        config,
        project_title="t",
        project_url=None,
    )
    # 2 SP * 0.5 day/SP * 8 h/day = 8 hours
    assert report.people[0].hours == 8.0


def test_legacy_hours_per_estimate_unit_still_works():
    config = sample_config()
    # helpers still default to hours; override via parse
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {
                "hours_per_estimate_unit": 4.0,
                "default_hourly_rate": 50,
            },
            "rates": {"ana": 75},
            "display": {"language": "es"},
        },
        Path("x.toml"),
    )
    assert config.slicing_pie.hours_per_estimate_unit == 4.0
    assert parse_estimate_hours(2, config.slicing_pie.hours_per_estimate_unit) == 8.0
