from pathlib import Path

from helpers import sample_config, ticket
from slicingpie.config import parse_config
from slicingpie.github_items import parse_project_item
from slicingpie.pie import build_pie


def _config(**pie_overrides):
    raw = {
        "mode": "github",
        "github": {"owner": "acme", "project_number": 2, "token": "t"},
        "fields": {
            "status": "Status",
            "done": ["Done"],
            "estimate": "Estimate",
        },
        "slicing_pie": {"review_percent": 20.0, **pie_overrides},
        "rates": {"ana": 75, "carlos": 50, "maria": 65},
        "display": {"language": "es"},
    }
    return parse_config(raw, Path("x.toml"))


def test_parse_approved_reviewers_from_closing_prs():
    node = {
        "content": {
            "__typename": "Issue",
            "number": 42,
            "title": "Feature",
            "url": "https://github.com/acme/app/issues/42",
            "assignees": {"nodes": [{"login": "ana"}]},
            "closedByPullRequestsReferences": {
                "nodes": [
                    {
                        "number": 7,
                        "url": "https://github.com/acme/app/pull/7",
                        "reviews": {
                            "nodes": [
                                {"author": {"__typename": "User", "login": "maria"}},
                                {
                                    "author": {
                                        "__typename": "Bot",
                                        "login": "copilot[bot]",
                                    }
                                },
                                {"author": {"__typename": "User", "login": "carlos"}},
                                {"author": {"__typename": "User", "login": "maria"}},
                            ]
                        },
                    }
                ]
            },
        },
        "fieldValues": {
            "nodes": [
                {"name": "Done", "field": {"name": "Status"}},
                {"number": 10.0, "field": {"name": "Estimate"}},
            ]
        },
    }
    parsed = parse_project_item(node, _config())
    assert parsed is not None
    assert parsed.reviewers == ("maria", "carlos")


def test_review_hours_carved_from_estimate():
    # 10h ticket, 20% review -> 2h to maria, 8h to ana
    report = build_pie(
        [
            ticket(
                "With review",
                assignees=("ana",),
                estimate=10,
                reviewers=("maria",),
            )
        ],
        sample_config(review_percent=20.0),
        project_title="t",
        project_url=None,
    )
    by_login = {person.login: person for person in report.people}
    assert by_login["ana"].hours == 8.0
    assert by_login["maria"].hours == 2.0
    assert report.total_hours == 10.0
    roles = {
        (share.number, share.role, share.hours)
        for person in report.people
        for share in person.tickets
    }
    assert (1, "work", 8.0) in roles
    assert (1, "review", 2.0) in roles


def test_no_review_credit_without_approver_or_zero_percent():
    tickets = [
        ticket("No PR", assignees=("ana",), estimate=10, reviewers=()),
        ticket(
            "Has reviewer but percent 0",
            assignees=("ana",),
            estimate=10,
            number=2,
            reviewers=("maria",),
        ),
    ]
    report = build_pie(
        tickets,
        sample_config(review_percent=0.0),
        project_title="t",
        project_url=None,
    )
    by_login = {person.login: person for person in report.people}
    assert by_login["ana"].hours == 20.0
    assert by_login["maria"].hours == 0.0


def test_multiple_reviewers_split_review_hours():
    report = build_pie(
        [
            ticket(
                "Two reviewers",
                assignees=("ana",),
                estimate=10,
                reviewers=("maria", "carlos"),
            )
        ],
        sample_config(review_percent=20.0),
        project_title="t",
        project_url=None,
    )
    by_login = {person.login: person for person in report.people}
    assert by_login["ana"].hours == 8.0
    assert by_login["maria"].hours == 1.0
    assert by_login["carlos"].hours == 1.0
