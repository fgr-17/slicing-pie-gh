from __future__ import annotations

import json

from slicingpie.models import PieReport, Ticket


def report_to_json(report: PieReport) -> str:
    payload = {
        "project": {"title": report.project_title, "url": report.project_url},
        "formula": {
            "slices": "hours * hourly_rate * seniority * time_multiplier",
            "expense_slices": "amount * cash_multiplier",
            "time_multiplier": report.time_multiplier,
            "cash_multiplier": report.cash_multiplier,
            "default_hourly_rate": report.default_hourly_rate,
            "effort_unit": report.effort_unit,
            "hours_per_day": report.hours_per_day,
            "days_per_story_point": report.days_per_story_point,
            "hours_per_estimate_unit": report.hours_per_estimate_unit,
            "review_percent": report.review_percent,
        },
        "expenses_config": {
            "label": report.expense_label,
            "currency": report.expense_currency,
            "cash_multiplier": report.cash_multiplier,
        },
        "totals": {
            "hours": report.total_hours,
            "slices": report.total_slices,
            "expenses": report.total_expenses,
            "expense_slices": report.total_expense_slices,
            "contribution": report.total_contribution,
            "done": report.done_count,
            "counted": report.counted_count,
            "counted_expenses": report.counted_expenses,
        },
        "people": [
            {
                "login": person.login,
                "name": person.name,
                "hours": person.hours,
                "hourly_rate": person.hourly_rate,
                "seniority": person.seniority,
                "slices": person.slices,
                "percent": person.percent,
                "used_default_rate": person.used_default_rate,
                "tickets": [
                    {
                        "title": share.title,
                        "number": share.number,
                        "url": share.url,
                        "hours": share.hours,
                        "assignees": list(share.assignees),
                        "role": share.role,
                        "reviewers": list(share.reviewers),
                    }
                    for share in person.tickets
                ],
            }
            for person in report.people
        ],
        "expenses": [
            {
                "login": row.login,
                "name": row.name,
                "amount": row.amount,
                "slices": row.slices,
                "percent": row.percent,
                "items": [
                    {
                        "title": item.title,
                        "number": item.number,
                        "url": item.url,
                        "amount": item.amount,
                        "occurred_at": item.occurred_at,
                        "assignees": list(item.assignees),
                    }
                    for item in row.items
                ],
            }
            for row in report.expenses
        ],
        "summary": [
            {
                "login": row.login,
                "name": row.name,
                "work_slices": row.work_slices,
                "expenses": row.expenses,
                "total": row.total,
                "percent": row.percent,
            }
            for row in report.summary
        ],
        "skipped": {
            "no_estimate": [_ticket_json(ticket) for ticket in report.skipped_no_estimate],
            "no_assignee": [_ticket_json(ticket) for ticket in report.skipped_no_assignee],
            "zero_hours": [_ticket_json(ticket) for ticket in report.skipped_zero_hours],
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _ticket_json(ticket: Ticket) -> dict:
    return {
        "title": ticket.title,
        "number": ticket.number,
        "url": ticket.url,
        "assignees": list(ticket.assignees),
        "status": ticket.status,
        "estimate": ticket.estimate_raw,
        "labels": list(ticket.labels),
        "occurred_at": ticket.occurred_at,
    }
