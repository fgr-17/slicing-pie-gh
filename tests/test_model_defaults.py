from pathlib import Path

from helpers import sample_config
from slicingpie.config import load_model_defaults, parse_config
from slicingpie.pie import build_pie
from helpers import ticket


def test_model_defaults_from_toml():
    model = load_model_defaults()
    assert model.time_multiplier == 2.0
    assert model.cash_multiplier == 4.0


def test_config_uses_model_defaults_when_omitted():
    config = parse_config(
        {
            "mode": "demo",
            "github": {"owner": "acme", "project_number": 1, "token": "t"},
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {"default_hourly_rate": 50},
            "rates": {"ana": 75},
            "expenses": {"label": "[expensa]", "currency": "USD"},
            "display": {"language": "es"},
        },
        Path("x.toml"),
    )
    assert config.slicing_pie.time_multiplier == 2.0
    assert config.expenses.cash_multiplier == 4.0
    report = build_pie(
        [
            ticket("Work", estimate=1, number=1),
            ticket(
                "Cash",
                estimate=10,
                number=2,
                labels=("[expensa]",),
                occurred_at="2026-01-01",
            ),
        ],
        config,
        project_title="t",
        project_url=None,
    )
    assert report.time_multiplier == 2.0
    assert report.cash_multiplier == 4.0
    assert report.total_expense_slices == 40
