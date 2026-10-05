from __future__ import annotations

from slicingpie.i18n import t
from slicingpie.models import Ticket

DEMO_PROJECT_TITLE = ""  # resolved at call time via demo_project_title()
DEMO_PROJECT_URL = None


def demo_project_title() -> str:
    return t("demo.project_title")


def demo_tickets() -> list[Ticket]:
    """Sample tickets so the report can be tried without GitHub."""
    return [
        Ticket(t("demo.ticket.onboarding"), 12, None, ("ana",), "Done", 16, "Issue"),
        Ticket(t("demo.ticket.payments"), 18, None, ("ana",), "Done", 8, "Issue"),
        Ticket(t("demo.ticket.copy"), 21, None, ("ana",), "Done", 4, "Issue"),
        Ticket(t("demo.ticket.gateway"), 14, None, ("carlos",), "Done", 12, "Issue"),
        Ticket(t("demo.ticket.retries"), 19, None, ("carlos",), "Done", 10, "Issue"),
        Ticket(t("demo.ticket.summary"), 9, None, ("maria",), "Done", 20, "Issue"),
        Ticket(t("demo.ticket.email"), 22, None, ("maria",), "Listo", 6, "Issue"),
        Ticket(
            t("demo.ticket.review"), 25, None, ("ana", "maria"), "Done", 6, "Issue"
        ),
        Ticket(t("demo.ticket.no_estimate"), 30, None, ("carlos",), "Done", None, "Issue"),
        Ticket(t("demo.ticket.unassigned"), 31, None, (), "Done", 5, "Issue"),
        Ticket(t("demo.ticket.zero"), 32, None, ("ana",), "Done", 0, "Issue"),
        Ticket(t("demo.ticket.wip"), 7, None, ("maria",), "In Progress", 10, "Issue"),
        Ticket(t("demo.ticket.backlog"), 3, None, ("carlos",), "Todo", 8, "Issue"),
    ]
