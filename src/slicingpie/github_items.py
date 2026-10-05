from __future__ import annotations

from typing import Any

from slicingpie.config import AppConfig
from slicingpie.i18n import t
from slicingpie.models import Ticket


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
        reviewers=_reviewer_logins(content),
    )


def real_login(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    if node.get("__typename") not in (None, "User"):
        return None
    login = str(node.get("login") or "").strip()
    if not login or login.casefold().endswith("[bot]"):
        return None
    return login


def _assignee_logins(content: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        login
        for user in (content.get("assignees") or {}).get("nodes") or []
        if (login := (user or {}).get("login"))
    )


def _reviewer_logins(content: dict[str, Any]) -> tuple[str, ...]:
    """APPROVED reviewers on closing PRs (unique, order preserved)."""
    seen: set[str] = set()
    reviewers: list[str] = []
    for pull in (content.get("closedByPullRequestsReferences") or {}).get("nodes") or []:
        if not isinstance(pull, dict):
            continue
        for review in (pull.get("reviews") or {}).get("nodes") or []:
            login = real_login((review or {}).get("author"))
            if not login:
                continue
            key = login.casefold()
            if key in seen:
                continue
            seen.add(key)
            reviewers.append(login)
    return tuple(reviewers)


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
