"""CLI message catalogs.

User-facing terminal text lives here so the language can change later.
Only Spanish (`es`) is shipped for now.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "es"
SUPPORTED_LANGUAGES = frozenset({"es"})

_MESSAGES: dict[str, dict[str, str]] = {
    "es": {
        "cli.description": (
            "Lee tickets Done de un GitHub Project y muestra el Slicing Pie "
            "segun horas de trabajo (asignado x estimado)."
        ),
        "cli.help.config": (
            "Archivo TOML (por defecto slicingpie.local.toml o slicingpie.toml)"
        ),
        "cli.help.verbose": "Lista cada ticket contado por persona",
        "cli.help.show_no_estimate": "Lista los tickets Done sin estimado",
        "cli.help.show_unassigned": "Lista los tickets Done sin asignado",
        "cli.help.show_skipped": (
            "Lista todos los tickets Done omitidos "
            "(sin estimado, sin asignado, monto/horas en cero)"
        ),
        "cli.help.json": "Imprime JSON en lugar de la tabla",
        "cli.help.detail": (
            "Lista cada gasto por persona, organizado por mes y fecha"
        ),
        "cli.help.sync_rates": (
            "Agrega cada usuario del repo como un bloque [[users]], "
            "con la tarifa por defecto. No pisa rate, seniority ni name."
        ),
        "cli.config_error": "error de config: {detail}",
        "cli.github_error": "error de GitHub: {detail}",
        "cli.cancelled": "cancelado",
        "cli.config_path": "config: {path}",
        "cli.wait.github": "Consultando GitHub...",
        "cli.wait.demo": "Armando pie...",
        "cli.wait.sync_rates": "Listando usuarios del repo...",
        "cli.sync_rates.mode": (
            'error de config: --sync-rates solo funciona con mode = "github".'
        ),
        "cli.sync_rates.no_users": (
            "error de GitHub: los repos del Project no tienen usuarios."
        ),
        "cli.sync_rates.users_of": "Usuarios de {repos}",
        "cli.sync_rates.rates_in": "Tarifas en {path}",
        "cli.sync_rates.added": "  nuevas ({symbol}{rate}/h): {logins}",
        "cli.sync_rates.added_none": "  nuevas: ninguna",
        "cli.sync_rates.kept": "  sin cambios: {logins}",
        "display.counted": "contados: {count}",
        "display.counted_expenses": "gastos: {count}",
        "display.skipped": "omitidos: {count}",
        "display.subtitle_hours": "  -  horas de trabajo",
        "display.formula": (
            "\nRebanadas = horas x tarifa x seniority x {multiplier} "
            "(tiempo no pagado)"
        ),
        "display.expense_hint": (
            "\nGastos: label '{label}' -> estimado en {currency} "
            "x {multiplier} (cash)"
        ),
        "display.empty": (
            "\n[yellow]No hay tickets Done con asignado y estimado "
            "para armar el pie.[/yellow]"
        ),
        "display.table.title": "Rebanadas por horas de trabajo",
        "display.table.caption": (
            "Rebanadas = horas x tarifa x seniority x {multiplier}  ->  % pie"
        ),
        "display.expenses.title": "Gastos ({currency}, label {label})",
        "display.expenses.caption": (
            "Rebanadas = monto x {multiplier}  ->  % pie de gastos"
        ),
        "display.expenses.detail_title": "Detalle de gastos por fecha",
        "display.expenses.detail_caption": (
            "Monto en moneda; rebanadas en resumen = monto x {multiplier}"
        ),
        "display.summary.title": "Resumen general",
        "display.summary.caption": (
            "Total = trabajo (x{time_multiplier}) + gastos (x{cash_multiplier})  "
            "->  % pie"
        ),
        "display.col.person": "Persona",
        "display.col.hours": "Horas",
        "display.col.rate": "Tarifa",
        "display.col.seniority": "Seniority",
        "display.col.slices": "Rebanadas",
        "display.col.work_slices": "Trabajo",
        "display.col.amount": "Monto",
        "display.col.expenses": "Gastos",
        "display.col.total": "Total",
        "display.col.percent": "% pie",
        "display.col.month": "Mes",
        "display.col.date": "Fecha",
        "display.col.no_date": "(sin fecha)",
        "display.default_rate_hint": (
            "[dim]* tarifa por defecto ({rate}/h). "
            "Anadela en [[users]] o corre slicingpie --sync-rates.[/dim]"
        ),
        "display.distribution": "Distribucion final",
        "display.distribution.caption": (
            "% pie = rebanadas de la persona / total del resumen"
        ),
        "display.col.bar": "Barra",
        "display.tickets_title": "Tickets contados por persona",
        "display.skipped_title": "Tickets Done omitidos",
        "display.col.reason": "Motivo",
        "display.skip.no_estimate": "sin estimado",
        "display.skip.no_assignee": "sin asignado",
        "display.skip.zero_hours": "con 0 horas",
        "config.empty_expense_label": "expenses.label no puede estar vacio.",
        "config.empty_expense_currency": "expenses.currency no puede estar vacio.",
        "config.bad_cash_multiplier": (
            "expenses.cash_multiplier debe ser un numero."
        ),
        "config.cash_multiplier_range": (
            "expenses.cash_multiplier debe ser > 0."
        ),
        "config.missing_model_file": (
            "No encuentro el modelo Mike Moyer: {path}\n"
            "Debe existir mike-moyer-model.toml en el directorio de trabajo."
        ),
        "config.bad_model_file": (
            "mike-moyer-model.toml ({path}) debe definir "
            "time_multiplier y cash_multiplier."
        ),
        "config.bad_model_numbers": (
            "time_multiplier y cash_multiplier en {path} deben ser numeros."
        ),
        "config.model_multiplier_range": (
            "time_multiplier y cash_multiplier del modelo deben ser > 0."
        ),
        "config.missing_file": (
            "No encuentro el archivo de configuracion: {path}\n"
            "Copia slicingpie.toml.example a slicingpie.toml y rellena los valores."
        ),
        "config.invalid_toml": "TOML invalido en {path}: {detail}",
        "config.bad_mode": "mode debe ser 'github' o 'demo'.",
        "config.bad_owner_type": (
            "github.owner_type debe ser auto, organization o user."
        ),
        "config.bad_project_number": "github.project_number debe ser un entero.",
        "config.project_number_range": "github.project_number debe ser >= 1.",
        "config.empty_done": "fields.done no puede estar vacio.",
        "config.bad_pie_numbers": (
            "Los valores numericos de [slicing_pie] son invalidos."
        ),
        "config.pie_number_range": (
            "time_multiplier y hours_per_estimate_unit deben ser > 0; "
            "default_hourly_rate debe ser >= 0."
        ),
        "config.bad_split": (
            "slicing_pie.split_among_assignees debe ser true o false."
        ),
        "config.bad_language": "display.language debe ser uno de: {languages}.",
        "config.rates_table": "[rates] debe ser una tabla login = tarifa.",
        "config.users_list": "users debe ser una lista de usuarios.",
        "config.missing_login": "Falta el login de un usuario.",
        "config.bad_rate": "Tarifa invalida para '{login}'.",
        "config.rate_range": "La tarifa de '{login}' debe ser >= 0.",
        "config.missing_login_row": "Falta login en un usuario.",
        "config.missing_rate": "Falta rate para '{login}'.",
        "config.bad_rate_seniority": "rate o seniority invalidos para '{login}'.",
        "config.rate_seniority_range": (
            "rate y seniority de '{login}' deben ser >= 0."
        ),
        "config.missing_owner": "Falta github.owner en la configuracion.",
        "config.missing_token": (
            "Falta el "
            + "token de GitHub. Ponlo en github.token o en GITHUB_TOKEN."
        ),
        "github.no_repos": (
            "El Project no tiene repositorios vinculados. "
            "Vincula el repo en el Project y vuelve a correr --sync-rates."
        ),
        "github.missing_owner": "no existe el {root} '{owner}'",
        "github.missing_project": (
            "{root} '{owner}' no tiene el Project #{number}"
        ),
        "github.resolve_failed": "No pude resolver el Project: {detail}",
        "github.list_users_failed": (
            "No pude listar usuarios de {owner}/{name}. "
            "Colaboradores: {collaborators}. Asignables: {assignable}."
        ),
        "github.repo_missing": "No encuentro el repositorio {owner}/{name}.",
        "github.missing_fields": (
            "El Project no tiene los campos {fields}. "
            "Campos disponibles: {available}."
        ),
        "github.field_status": "estado '{name}'",
        "github.field_estimate": "estimado '{name}'",
        "github.no_fields": "(ninguno)",
        "github.network": "Error de red al llamar a GitHub: {detail}",
        "github.unauthorized": (
            "Token de GitHub rechazado (401). Revisa GITHUB_TOKEN."
        ),
        "github.forbidden": (
            "GitHub denego el acceso (403). "
            "El token necesita lectura de Projects e Issues."
        ),
        "github.http": "GitHub respondio HTTP {status}: {body}",
        "github.graphql": "GraphQL de GitHub: {detail}",
        "github.no_data": "GitHub no devolvio datos del Project.",
        "github.project_gone": "El Project desaparecio a mitad de la paginacion.",
        "github.untitled": "(sin titulo)",
        "demo.project_title": "Lanzamiento v1 (demo)",
        "demo.ticket.onboarding": "Disenar onboarding",
        "demo.ticket.payments": "API de pagos",
        "demo.ticket.copy": "Ajustes de copy",
        "demo.ticket.gateway": "Integrar pasarela",
        "demo.ticket.retries": "Cola de reintentos",
        "demo.ticket.summary": "Pantalla de resumen",
        "demo.ticket.email": "Email de confirmacion",
        "demo.ticket.review": "Revision conjunta del checkout",
        "demo.ticket.no_estimate": "Sin estimar (omitido)",
        "demo.ticket.unassigned": "Huerfano sin asignado",
        "demo.ticket.zero": "Estimado en cero",
        "demo.ticket.wip": "Aun en progreso",
        "demo.ticket.backlog": "Backlog",
        "demo.ticket.aws": "Factura AWS",
        "demo.ticket.domain": "Dominio .com",
        "demo.ticket.ads": "Ads de lanzamiento",
    }
}

_language = DEFAULT_LANGUAGE


def set_language(language: str) -> str:
    """Select the active language. Unknown values fall back to Spanish."""
    global _language
    normalized = language.strip().lower() or DEFAULT_LANGUAGE
    if normalized not in SUPPORTED_LANGUAGES:
        normalized = DEFAULT_LANGUAGE
    _language = normalized
    return _language


def get_language() -> str:
    return _language


def t(key: str, **kwargs: object) -> str:
    catalog = _MESSAGES.get(_language) or _MESSAGES[DEFAULT_LANGUAGE]
    try:
        template = catalog[key]
    except KeyError as exc:
        raise KeyError(f"missing message key: {key}") from exc
    if kwargs:
        return template.format(**kwargs)
    return template
