from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from slicingpie.config import AppConfig
from slicingpie.i18n import t
from slicingpie.models import Ticket

GRAPHQL_META = """
query ProjectMeta($login: String!, $number: Int!) {
  %(root)s(login: $login) {
    projectV2(number: $number) {
      title
      url
      fields(first: 50) {
        nodes {
          __typename
          ... on ProjectV2FieldCommon { name dataType }
          ... on ProjectV2SingleSelectField {
            name
            options { name }
          }
        }
      }
    }
  }
}
"""

GRAPHQL_ITEMS = """
query ProjectItems($login: String!, $number: Int!, $cursor: String) {
  %(root)s(login: $login) {
    projectV2(number: $number) {
      title
      url
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            __typename
            ... on Issue {
              number
              title
              url
              createdAt
              closedAt
              labels(first: 20) { nodes { name } }
              assignees(first: 10) { nodes { login } }
            }
            ... on PullRequest {
              number
              title
              url
              assignees(first: 10) { nodes { login } }
            }
            ... on DraftIssue {
              title
              createdAt
              assignees(first: 10) { nodes { login } }
            }
          }
          fieldValues(first: 50) {
            nodes {
              __typename
              ... on ProjectV2ItemFieldNumberValue {
                number
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field { ... on ProjectV2FieldCommon { name } }
              }
              ... on ProjectV2ItemFieldTextValue {
                text
                field { ... on ProjectV2FieldCommon { name } }
              }
            }
          }
        }
      }
    }
  }
}
"""


GRAPHQL_REPOS = """
query ProjectRepos($login: String!, $number: Int!, $cursor: String) {
  %(root)s(login: $login) {
    projectV2(number: $number) {
      repositories(first: 20, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { nameWithOwner }
      }
    }
  }
}
"""

GRAPHQL_COLLABORATORS = """
query RepoUsers($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    owner { login __typename }
    collaborators(affiliation: ALL, first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { login __typename }
    }
  }
}
"""

GRAPHQL_ASSIGNABLE = """
query RepoAssignable($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    owner { login __typename }
    assignableUsers(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { login __typename }
    }
  }
}
"""


class GitHubError(RuntimeError):
    """Failed call to the GitHub API."""


@dataclass(frozen=True)
class RepositoryUsers:
    repositories: tuple[str, ...]
    logins: tuple[str, ...]


class GitHubProjectClient:
    def __init__(self, config: AppConfig, client: httpx.Client | None = None) -> None:
        self._config = config
        self._owns_client = client is None
        self._http = client or httpx.Client(
            headers={
                "Authorization": f"Bearer {config.github.token}",
                "Accept": "application/vnd.github+json",
                "X-Github-Next-Global-ID": "1",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> GitHubProjectClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch(self) -> tuple[str, str | None, list[Ticket]]:
        root, project = self._resolve_project()
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            data = self._graphql(
                GRAPHQL_ITEMS % {"root": root},
                {
                    "login": self._config.github.owner,
                    "number": self._config.github.project_number,
                    "cursor": cursor,
                },
            )
            project_data = _project_from_payload(data, root)
            connection = project_data["items"]
            items.extend(node for node in connection["nodes"] if node)
            page = connection["pageInfo"]
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
            if not cursor:
                break

        tickets = [
            ticket
            for node in items
            if (ticket := parse_project_item(node, self._config)) is not None
        ]
        return project["title"], project.get("url"), tickets

    def list_repository_users(self) -> RepositoryUsers:
        """Return real users from each repository linked to the Project.

        Prefers collaborators (affiliation ALL). If the token cannot read them,
        falls back to assignable users. Includes a person owner and skips bots.
        """
        root, _project = self._resolve_project(check_fields=False)
        repositories = self._linked_repositories(root)
        if not repositories:
            raise GitHubError(t("github.no_repos"))

        found: dict[str, str] = {}
        for name_with_owner in repositories:
            owner, sep, name = name_with_owner.partition("/")
            if not sep or not owner or not name:
                continue
            for login in self._repository_logins(owner, name):
                found.setdefault(login.casefold(), login)
        logins = tuple(found[key] for key in sorted(found))
        return RepositoryUsers(repositories=tuple(repositories), logins=logins)

    def _resolve_project(self, *, check_fields: bool = True) -> tuple[str, dict[str, Any]]:
        roots = _roots_to_try(self._config.github.owner_type)
        errors: list[str] = []
        for root in roots:
            data = self._graphql(
                GRAPHQL_META % {"root": root},
                {
                    "login": self._config.github.owner,
                    "number": self._config.github.project_number,
                },
                allow_not_found=True,
            )
            container = data.get(root)
            if not container:
                errors.append(
                    t("github.missing_owner", root=root, owner=self._config.github.owner)
                )
                continue
            project = container.get("projectV2")
            if not project:
                errors.append(
                    t(
                        "github.missing_project",
                        root=root,
                        owner=self._config.github.owner,
                        number=self._config.github.project_number,
                    )
                )
                continue
            if check_fields:
                self._assert_fields(project)
            return root, project

        raise GitHubError(t("github.resolve_failed", detail="; ".join(errors)))

    def _linked_repositories(self, root: str) -> list[str]:
        names: list[str] = []
        cursor: str | None = None
        while True:
            data = self._graphql(
                GRAPHQL_REPOS % {"root": root},
                {
                    "login": self._config.github.owner,
                    "number": self._config.github.project_number,
                    "cursor": cursor,
                },
            )
            project = _project_from_payload(data, root)
            connection = project.get("repositories") or {}
            for node in connection.get("nodes") or []:
                name = (node or {}).get("nameWithOwner")
                if name:
                    names.append(str(name))
            page = connection.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
            if not cursor:
                break
        return names

    def _repository_logins(self, owner: str, name: str) -> list[str]:
        try:
            return self._collect_logins(
                GRAPHQL_COLLABORATORS, owner, name, "collaborators"
            )
        except GitHubError as collaborators_error:
            if "401" in str(collaborators_error):
                raise
            try:
                return self._collect_logins(
                    GRAPHQL_ASSIGNABLE, owner, name, "assignableUsers"
                )
            except GitHubError as assignable_error:
                raise GitHubError(
                    t(
                        "github.list_users_failed",
                        owner=owner,
                        name=name,
                        collaborators=collaborators_error,
                        assignable=assignable_error,
                    )
                ) from assignable_error

    def _collect_logins(
        self, query: str, owner: str, name: str, field: str
    ) -> list[str]:
        logins: list[str] = []
        seen: set[str] = set()
        cursor: str | None = None
        include_owner = True
        while True:
            data = self._graphql(
                query,
                {"owner": owner, "name": name, "cursor": cursor},
            )
            repository = data.get("repository")
            if not repository:
                raise GitHubError(
                    t("github.repo_missing", owner=owner, name=name)
                )
            if include_owner:
                _remember_login(logins, seen, _real_login(repository.get("owner")))
                include_owner = False
            connection = repository.get(field) or {}
            for node in connection.get("nodes") or []:
                _remember_login(logins, seen, _real_login(node))
            page = connection.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
            if not cursor:
                break
        return logins

    def _assert_fields(self, project: dict[str, Any]) -> None:
        fields = []
        for node in (project.get("fields") or {}).get("nodes") or []:
            name = node.get("name")
            if name:
                fields.append(name)
        names = {name.casefold() for name in fields}
        missing = []
        for key, expected in (
            ("github.field_status", self._config.fields.status),
            ("github.field_estimate", self._config.fields.estimate),
        ):
            if expected.casefold() not in names:
                missing.append(t(key, name=expected))
        if missing:
            available = ", ".join(fields) if fields else t("github.no_fields")
            raise GitHubError(
                t(
                    "github.missing_fields",
                    fields=" y ".join(missing),
                    available=available,
                )
            )

    def _graphql(
        self,
        query: str,
        variables: dict[str, Any],
        *,
        allow_not_found: bool = False,
    ) -> dict[str, Any]:
        try:
            response = self._http.post(
                self._config.github.api_url,
                json={"query": query, "variables": variables},
            )
        except httpx.HTTPError as exc:
            raise GitHubError(t("github.network", detail=exc)) from exc

        if response.status_code == 401:
            raise GitHubError(t("github.unauthorized"))
        if response.status_code == 403:
            raise GitHubError(t("github.forbidden"))
        if response.status_code >= 400:
            raise GitHubError(
                t(
                    "github.http",
                    status=response.status_code,
                    body=response.text[:300],
                )
            )

        payload = response.json()
        errors = payload.get("errors") or []
        if errors:
            messages = "; ".join(
                str(error.get("message") or error) for error in errors
            )
            if allow_not_found and any(
                "Could not resolve to" in str(error.get("message") or "")
                or "not found" in str(error.get("message") or "").lower()
                for error in errors
            ):
                return payload.get("data") or {}
            raise GitHubError(t("github.graphql", detail=messages))

        data = payload.get("data")
        if not data:
            raise GitHubError(t("github.no_data"))
        return data


def _real_login(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("__typename") not in (None, "User"):
        return None
    login = str(node.get("login") or "").strip()
    if not login or login.casefold().endswith("[bot]"):
        return None
    return login


def _remember_login(logins: list[str], seen: set[str], login: str | None) -> None:
    if not login:
        return
    key = login.casefold()
    if key in seen:
        return
    seen.add(key)
    logins.append(login)


def _roots_to_try(owner_type: str) -> list[str]:
    if owner_type == "organization":
        return ["organization"]
    if owner_type == "user":
        return ["user"]
    return ["organization", "user"]


def _project_from_payload(data: dict[str, Any], root: str) -> dict[str, Any]:
    container = data.get(root) or {}
    project = container.get("projectV2")
    if not project:
        raise GitHubError(t("github.project_gone"))
    return project


def parse_project_item(node: dict[str, Any], config: AppConfig) -> Ticket | None:
    content = node.get("content") or {}
    typename = content.get("__typename")
    if typename not in {"Issue", "DraftIssue"}:
        return None

    status, estimate = _read_status_and_estimate(
        node.get("fieldValues") or {},
        config.fields.status,
        config.fields.estimate,
    )
    return Ticket(
        title=str(content.get("title") or t("github.untitled")),
        number=content.get("number"),
        url=content.get("url"),
        assignees=_assignee_logins(content),
        status=status,
        estimate_raw=estimate,
        item_type=str(typename),
        labels=_label_names(content),
        occurred_at=_ticket_date(content),
    )


def _assignee_logins(content: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        login
        for user in (content.get("assignees") or {}).get("nodes") or []
        if (login := (user or {}).get("login"))
    )


def _label_names(content: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        name
        for label in (content.get("labels") or {}).get("nodes") or []
        if (name := str((label or {}).get("name") or "").strip())
    )


def _read_status_and_estimate(
    field_values: dict[str, Any],
    status_field: str,
    estimate_field: str,
) -> tuple[str | None, float | str | None]:
    status: str | None = None
    estimate: float | str | None = None
    status_name = status_field.casefold()
    estimate_name = estimate_field.casefold()
    for field_value in field_values.get("nodes") or []:
        field = field_value.get("field") or {}
        field_name = str(field.get("name") or "").casefold()
        if not field_name:
            continue
        if field_name == status_name and field_value.get("name"):
            status = str(field_value["name"])
        elif field_name == estimate_name:
            estimate = _estimate_from_field(field_value, estimate)
    return status, estimate


def _estimate_from_field(
    field_value: dict[str, Any], current: float | str | None
) -> float | str | None:
    if field_value.get("number") is not None:
        return field_value["number"]
    if field_value.get("text"):
        return str(field_value["text"])
    return current


def _ticket_date(content: dict[str, Any]) -> str | None:
    for key in ("closedAt", "createdAt"):
        raw = content.get(key)
        if not raw:
            continue
        text = str(raw).strip()
        if len(text) >= 10:
            return text[:10]
    return None

