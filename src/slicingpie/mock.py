from __future__ import annotations

from slicingpie.models import Ticket

DEMO_PROJECT_TITLE = "Lanzamiento v1 (demo)"
DEMO_PROJECT_URL = None


def demo_tickets() -> list[Ticket]:
    """Tickets de ejemplo para probar el informe sin GitHub."""
    return [
        Ticket("Diseñar onboarding", 12, None, ("ana",), "Done", 16, "Issue"),
        Ticket("API de pagos", 18, None, ("ana",), "Done", 8, "Issue"),
        Ticket("Ajustes de copy", 21, None, ("ana",), "Done", 4, "Issue"),
        Ticket("Integrar pasarela", 14, None, ("carlos",), "Done", 12, "Issue"),
        Ticket("Cola de reintentos", 19, None, ("carlos",), "Done", 10, "Issue"),
        Ticket("Pantalla de resumen", 9, None, ("maria",), "Done", 20, "Issue"),
        Ticket("Email de confirmación", 22, None, ("maria",), "Listo", 6, "Issue"),
        Ticket("Revisión conjunta del checkout", 25, None, ("ana", "maria"), "Done", 6, "Issue"),
        Ticket("Sin estimar (omitido)", 30, None, ("carlos",), "Done", None, "Issue"),
        Ticket("Huérfano sin asignado", 31, None, (), "Done", 5, "Issue"),
        Ticket("Estimado en cero", 32, None, ("ana",), "Done", 0, "Issue"),
        Ticket("Aún en progreso", 7, None, ("maria",), "In Progress", 10, "Issue"),
        Ticket("Backlog", 3, None, ("carlos",), "Todo", 8, "Issue"),
    ]
