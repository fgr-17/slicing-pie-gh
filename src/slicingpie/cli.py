from __future__ import annotations

import argparse
import sys
from pathlib import Path

from slicingpie.config import ConfigError, load_config, require_github_settings
from slicingpie.display import render_report, report_to_json
from slicingpie.github_project import GitHubError, GitHubProjectClient
from slicingpie.mock import DEMO_PROJECT_TITLE, DEMO_PROJECT_URL, demo_tickets
from slicingpie.pie import build_pie


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slicingpie",
        description=(
            "Lee tickets Done de un GitHub Project y muestra el Slicing Pie "
            "según horas de trabajo (asignado × estimado)."
        ),
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Archivo TOML (por defecto slicingpie.local.toml o slicingpie.toml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Lista cada ticket contado por persona",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime JSON en lugar de la tabla",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if config.mode == "demo":
            title, url, tickets = DEMO_PROJECT_TITLE, DEMO_PROJECT_URL, demo_tickets()
        else:
            require_github_settings(config)
            with GitHubProjectClient(config) as client:
                title, url, tickets = client.fetch()
        report = build_pie(tickets, config, project_title=title, project_url=url)
    except ConfigError as exc:
        print(f"error de config: {exc}", file=sys.stderr)
        return 1
    except GitHubError as exc:
        print(f"error de GitHub: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("cancelado", file=sys.stderr)
        return 130

    if args.json:
        print(report_to_json(report))
    else:
        render_report(
            report,
            verbose=args.verbose,
            currency_symbol=config.display.currency_symbol,
        )
        print()
        print(f"config: {config.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
