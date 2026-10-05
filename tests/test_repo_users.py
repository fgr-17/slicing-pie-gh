import json
from pathlib import Path

import httpx

from slicingpie.config import parse_config
from slicingpie.github_project import GitHubProjectClient


def _config():
    return parse_config(
        {
            "mode": "github",
            "github": {
                "owner": "acme",
                "owner_type": "user",
                "project_number": 2,
                "token": "t",
            },
            "fields": {"status": "Status", "done": ["Done"], "estimate": "Estimate"},
            "slicing_pie": {},
            "rates": {},
        },
        Path("x.toml"),
    )


def _response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


def test_lists_collaborators_and_skips_bots():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        query = body["query"]
        if "query ProjectMeta" in query:
            return _response(
                {"data": {"user": {"projectV2": {"title": "Pie", "url": "https://example"}}}}
            )
        if "query ProjectRepos" in query:
            return _response(
                {
                    "data": {
                        "user": {
                            "projectV2": {
                                "repositories": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [{"nameWithOwner": "acme/app"}],
                                }
                            }
                        }
                    }
                }
            )
        if "query RepoUsers" in query:
            if body["variables"]["cursor"] == "c2":
                return _response(
                    {
                        "data": {
                            "repository": {
                                "owner": {"login": "acme", "__typename": "User"},
                                "collaborators": {
                                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    "nodes": [{"login": "Zoe", "__typename": "User"}],
                                },
                            }
                        }
                    }
                )
            return _response(
                {
                    "data": {
                        "repository": {
                            "owner": {"login": "acme", "__typename": "User"},
                            "collaborators": {
                                "pageInfo": {"hasNextPage": True, "endCursor": "c2"},
                                "nodes": [
                                    {"login": "bob", "__typename": "User"},
                                    {"login": "dependabot[bot]", "__typename": "Bot"},
                                ],
                            },
                        }
                    }
                }
            )
        raise AssertionError(query[:80])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        users = GitHubProjectClient(_config(), client=http).list_repository_users()

    assert users.repositories == ("acme/app",)
    assert users.logins == ("acme", "bob", "Zoe")


def test_falls_back_to_assignable_users():
    def handler(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        if "query ProjectMeta" in query:
            return _response({"data": {"user": {"projectV2": {"title": "Pie"}}}})
        if "query ProjectRepos" in query:
            return _response(
                {
                    "data": {
                        "user": {
                            "projectV2": {
                                "repositories": {
                                    "pageInfo": {"hasNextPage": False},
                                    "nodes": [
                                        {"nameWithOwner": "acme/app"},
                                        {"nameWithOwner": "other/lib"},
                                    ],
                                }
                            }
                        }
                    }
                }
            )
        if "query RepoUsers" in query:
            return _response(
                {
                    "data": {"repository": None},
                    "errors": [{"message": "Must have push access to view repository collaborators."}],
                }
            )
        assert "query RepoAssignable" in query
        return _response(
            {
                "data": {
                    "repository": {
                        "owner": {"login": "acme-org", "__typename": "Organization"},
                        "assignableUsers": {
                            "pageInfo": {"hasNextPage": False},
                            "nodes": [{"login": "lua", "__typename": "User"}],
                        },
                    }
                }
            }
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        users = GitHubProjectClient(_config(), client=http).list_repository_users()

    assert users.repositories == ("acme/app", "other/lib")
    assert users.logins == ("lua",)
