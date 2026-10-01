from slicingpie.config import parse_config
from slicingpie.github_project import parse_project_item
from pathlib import Path


def _config():
    return parse_config(
        {
            "mode": "github",
            "github": {"owner": "acme", "project_number": 2, "token": "t"},
            "fields": {
                "status": "Status",
                "done": ["Done"],
                "estimate": "Estimate",
            },
            "slicing_pie": {},
            "rates": {},
        },
        Path("x.toml"),
    )


def test_parse_issue_with_number_estimate():
    node = {
        "content": {
            "__typename": "Issue",
            "number": 42,
            "title": "Cerrar checkout",
            "url": "https://github.com/acme/app/issues/42",
            "assignees": {"nodes": [{"login": "ana"}]},
        },
        "fieldValues": {
            "nodes": [
                {
                    "name": "Done",
                    "field": {"name": "Status"},
                },
                {
                    "number": 8.0,
                    "field": {"name": "Estimate"},
                },
            ]
        },
    }
    ticket = parse_project_item(node, _config())
    assert ticket is not None
    assert ticket.number == 42
    assert ticket.assignees == ("ana",)
    assert ticket.status == "Done"
    assert ticket.estimate_raw == 8.0


def test_parse_text_estimate_and_skip_pull_request():
    config = _config()
    issue = {
        "content": {
            "__typename": "Issue",
            "number": 7,
            "title": "Texto",
            "url": None,
            "assignees": {"nodes": [{"login": "carlos"}, {"login": "maria"}]},
        },
        "fieldValues": {
            "nodes": [
                {"name": "Done", "field": {"name": "status"}},
                {"text": "6h", "field": {"name": "estimate"}},
            ]
        },
    }
    ticket = parse_project_item(issue, config)
    assert ticket is not None
    assert ticket.estimate_raw == "6h"
    assert ticket.assignees == ("carlos", "maria")

    pr = {
        "content": {"__typename": "PullRequest", "number": 1, "title": "PR"},
        "fieldValues": {"nodes": []},
    }
    assert parse_project_item(pr, config) is None
