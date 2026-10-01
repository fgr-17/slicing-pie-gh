from __future__ import annotations

from typing import Any

import httpx

from slicingpie.config import AppConfig
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


class GitHubError(RuntimeError):
    """Fallo al hablar con la API de GitHub."""


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

    def _resolve_project(self) -> tuple[str, dict[str, Any]]:
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
                errors.append(f"no existe el {root} '{self._config.github.owner}'")
                continue
            project = container.get("projectV2")
            if not project:
                errors.append(
                    f"{root} '{self._config.github.owner}' no tiene el Project "
                    f"#{self._config.github.project_number}"
                )
                continue
            self._assert_fields(project)
            return root, project

        raise GitHubError("No pude resolver el Project: " + "; ".join(errors))

    def _assert_fields(self, project: dict[str, Any]) -> None:
        fields = []
        for node in (project.get("fields") or {}).get("nodes") or []:
            name = node.get("name")
            if name:
                fields.append(name)
        names = {name.casefold() for name in fields}
        missing = []
        for label, expected in (
            ("estado", self._config.fields.status),
            ("estimado", self._config.fields.estimate),
        ):
            if expected.casefold() not in names:
                missing.append(f"{label} '{expected}'")
        if missing:
            available = ", ".join(fields) if fields else "(ninguno)"
            raise GitHubError(
                "El Project no tiene los campos "
                + " y ".join(missing)
                + f". Campos disponibles: {available}."
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
            raise GitHubError(f"Error de red al llamar a GitHub: {exc}") from exc

        if response.status_code == 401:
            raise GitHubError("Token de GitHub rechazado (401). Revisa GITHUB_TOKEN.")
        if response.status_code == 403:
            raise GitHubError(
                "GitHub denegó el acceso (403). El token necesita lectura de Projects e Issues."
            )
        if response.status_code >= 400:
            raise GitHubError(
                f"GitHub respondió HTTP {response.status_code}: {response.text[:300]}"
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
            raise GitHubError(f"GraphQL de GitHub: {messages}")

        data = payload.get("data")
        if not data:
            raise GitHubError("GitHub no devolvió datos del Project.")
        return data


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
        raise GitHubError("El Project desapareció a mitad de la paginación.")
    return project


def parse_project_item(node: dict[str, Any], config: AppConfig) -> Ticket | None:
    content = node.get("content") or {}
    typename = content.get("__typename")
    if typename not in {"Issue", "DraftIssue"}:
        return None

    assignees = tuple(
        login
        for user in (content.get("assignees") or {}).get("nodes") or []
        if (login := (user or {}).get("login"))
    )

    status: str | None = None
    estimate: float | str | None = None
    status_name = config.fields.status.casefold()
    estimate_name = config.fields.estimate.casefold()

    for field_value in (node.get("fieldValues") or {}).get("nodes") or []:
        field = field_value.get("field") or {}
        field_name = str(field.get("name") or "").casefold()
        if not field_name:
            continue
        if field_name == status_name and field_value.get("name"):
            status = str(field_value["name"])
        elif field_name == estimate_name:
            if field_value.get("number") is not None:
                estimate = field_value["number"]
            elif field_value.get("text"):
                estimate = str(field_value["text"])

    return Ticket(
        title=str(content.get("title") or "(sin título)"),
        number=content.get("number"),
        url=content.get("url"),
        assignees=assignees,
        status=status,
        estimate_raw=estimate,
        item_type=str(typename),
    )
