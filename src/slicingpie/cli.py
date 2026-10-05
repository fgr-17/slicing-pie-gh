from __future__ import annotations

import argparse
import sys
from pathlib import Path

from slicingpie.config import AppConfig, ConfigError, load_config, require_github_settings
from slicingpie.display import clear_screen, render_report, report_to_json, waiting
from slicingpie.github_project import GitHubError, GitHubProjectClient
from slicingpie.i18n import set_language, t
from slicingpie.mock import DEMO_PROJECT_URL, demo_project_title, demo_tickets
from slicingpie.pie import build_pie
from slicingpie.rates_file import format_rate, upsert_default_rates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="slicingpie",
        description=t("cli.description"),
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help=t("cli.help.config"),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=t("cli.help.verbose"),
    )
    parser.add_argument(
        "--show-no-estimate",
        action="store_true",
        help=t("cli.help.show_no_estimate"),
    )
    parser.add_argument(
        "--show-unassigned",
        action="store_true",
        help=t("cli.help.show_unassigned"),
    )
    parser.add_argument(
        "--show-skipped",
        action="store_true",
        help=t("cli.help.show_skipped"),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=t("cli.help.json"),
    )
    parser.add_argument(
        "--detail",
        "--details",
        nargs="*",
        metavar="SCOPE",
        default=None,
        help=t("cli.help.detail"),
    )
    parser.add_argument(
        "--sync-rates",
        action="store_true",
        help=t("cli.help.sync_rates"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        detail_scopes = _detail_scopes(args.detail)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        config = load_config(args.config)
        set_language(config.display.language)
        if args.sync_rates:
            return _sync_rates(config)
        with waiting(_wait_message(config.mode)):
            if config.mode == "demo":
                title, url, tickets = (
                    demo_project_title(),
                    DEMO_PROJECT_URL,
                    demo_tickets(),
                )
            else:
                require_github_settings(config)
                with GitHubProjectClient(config) as client:
                    title, url, tickets = client.fetch()
            report = build_pie(
                tickets, config, project_title=title, project_url=url
            )
    except ConfigError as exc:
        print(t("cli.config_error", detail=exc), file=sys.stderr)
        return 1
    except GitHubError as exc:
        print(t("cli.github_error", detail=exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(t("cli.cancelled"), file=sys.stderr)
        return 130

    if args.json:
        print(report_to_json(report))
    else:
        clear_screen()
        render_report(
            report,
            verbose=args.verbose,
            currency_symbol=config.display.currency_symbol,
            show_no_estimate=args.show_no_estimate,
            show_unassigned=args.show_unassigned,
            show_skipped=args.show_skipped,
            detail_expenses="expenses" in detail_scopes,
            detail_review="review" in detail_scopes,
        )
        print()
        print(t("cli.config_path", path=config.path))
    return 0


def _detail_scopes(raw: list[str] | None) -> frozenset[str]:
    """Normalize --detail scopes. None = off; [] = all detail tables."""
    if raw is None:
        return frozenset()
    scopes = {item.strip().casefold() for item in raw if item.strip()}
    if not scopes:
        return frozenset({"expenses", "review"})
    allowed = {"expenses", "review"}
    unknown = sorted(scopes - allowed)
    if unknown:
        raise ValueError(t("cli.bad_detail_scope", scopes=", ".join(unknown)))
    return frozenset(scopes)


def _wait_message(mode: str) -> str:
    if mode == "github":
        return t("cli.wait.github")
    return t("cli.wait.demo")


def _sync_rates(config: AppConfig) -> int:
    if config.mode != "github":
        print(t("cli.sync_rates.mode"), file=sys.stderr)
        return 1
    require_github_settings(config)
    with waiting(t("cli.wait.sync_rates")):
        with GitHubProjectClient(config) as client:
            users = client.list_repository_users()
    if not users.logins:
        print(t("cli.sync_rates.no_users"), file=sys.stderr)
        return 2

    added, kept = upsert_default_rates(
        config.path,
        users.logins,
        config.slicing_pie.default_hourly_rate,
    )
    rate = format_rate(config.slicing_pie.default_hourly_rate)
    symbol = config.display.currency_symbol
    print(t("cli.sync_rates.users_of", repos=", ".join(users.repositories)))
    print(t("cli.sync_rates.rates_in", path=config.path))
    if added:
        print(
            t(
                "cli.sync_rates.added",
                symbol=symbol,
                rate=rate,
                logins=", ".join(added),
            )
        )
    else:
        print(t("cli.sync_rates.added_none"))
    if kept:
        print(t("cli.sync_rates.kept", logins=", ".join(kept)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
