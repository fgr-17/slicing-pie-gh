from __future__ import annotations

from pathlib import Path

from slicingpie.config import parse_config
from slicingpie.models import Ticket


def sample_config(**pie_overrides):
    raw = {
        "mode": "demo",
        "github": {
            "owner": "acme",
            "owner_type": "auto",
            "project_number": 1,
            "token": "test-token",
        },
        "fields": {
            "status": "Status",
            "done": ["Done", "Listo"],
            "estimate": "Estimate",
        },
        "slicing_pie": {
            "time_multiplier": 2.0,
            "default_hourly_rate": 50.0,
            "hours_per_estimate_unit": 1.0,
            "split_among_assignees": True,
        },
        "rates": {"ana": 75, "carlos": 50, "maria": 65},
        "display": {"currency_symbol": "$", "language": "es"},
    }
    raw["slicing_pie"].update(pie_overrides)
    return parse_config(raw, Path("slicingpie.toml"))


def ticket(
    title: str,
    *,
    assignees: tuple[str, ...] = ("ana",),
    status: str | None = "Done",
    estimate=8,
    number: int | None = 1,
    labels: tuple[str, ...] = (),
    occurred_at: str | None = None,
) -> Ticket:
    return Ticket(
        title,
        number,
        None,
        assignees,
        status,
        estimate,
        "Issue",
        labels=labels,
        occurred_at=occurred_at,
    )
