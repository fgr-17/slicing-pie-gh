from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import os
import tomllib

from slicingpie.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, set_language, t

DEFAULT_CONFIG_NAMES = ("slicingpie.local.toml", "slicingpie.toml")
MODEL_FILE_NAME = "mike-moyer-model.toml"


class ConfigError(ValueError):
    """Invalid or missing configuration."""


@dataclass(frozen=True)
class GitHubConfig:
    token: str
    owner: str
    owner_type: str
    project_number: int
    api_url: str


@dataclass(frozen=True)
class FieldsConfig:
    status: str
    done: tuple[str, ...]
    estimate: str


@dataclass(frozen=True)
class PersonConfig:
    login: str
    name: str
    rate: float
    seniority: float

    @property
    def effective_rate(self) -> float:
        return self.rate * self.seniority


@dataclass(frozen=True)
class SlicingPieConfig:
    time_multiplier: float
    default_hourly_rate: float
    hours_per_estimate_unit: float
    split_among_assignees: bool
    users: dict[str, PersonConfig]
    effort_unit: str = "hours"
    hours_per_day: float = 8.0
    days_per_story_point: float = 1.0
    review_percent: float = 0.0


@dataclass(frozen=True)
class DisplayConfig:
    currency_symbol: str
    language: str


@dataclass(frozen=True)
class ExpensesConfig:
    label: str
    currency: str
    cash_multiplier: float


@dataclass(frozen=True)
class AppConfig:
    mode: str
    github: GitHubConfig
    fields: FieldsConfig
    slicing_pie: SlicingPieConfig
    display: DisplayConfig
    expenses: ExpensesConfig
    path: Path = field(compare=False)


def find_config_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    cwd = Path.cwd()
    for name in DEFAULT_CONFIG_NAMES:
        candidate = cwd / name
        if candidate.is_file():
            return candidate
    return cwd / "slicingpie.toml"


def find_model_path() -> Path:
    """Resolve mike-moyer-model.toml (cwd first, then package/repo root)."""
    candidates = [
        Path.cwd() / MODEL_FILE_NAME,
        Path(__file__).resolve().parents[2] / MODEL_FILE_NAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


@dataclass(frozen=True)
class ModelDefaults:
    time_multiplier: float
    cash_multiplier: float


@lru_cache(maxsize=1)
def load_model_defaults() -> ModelDefaults:
    path = find_model_path()
    if not path.is_file():
        raise ConfigError(t("config.missing_model_file", path=path))
    with path.open("rb") as handle:
        try:
            raw = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(
                t("config.invalid_toml", path=path, detail=exc)
            ) from exc
    try:
        time_multiplier = float(raw["time_multiplier"])
        cash_multiplier = float(raw["cash_multiplier"])
    except KeyError as exc:
        raise ConfigError(t("config.bad_model_file", path=path)) from exc
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_model_numbers", path=path)) from exc
    if time_multiplier <= 0 or cash_multiplier <= 0:
        raise ConfigError(t("config.model_multiplier_range"))
    return ModelDefaults(
        time_multiplier=time_multiplier,
        cash_multiplier=cash_multiplier,
    )


def load_config(path: Path | None = None) -> AppConfig:
    config_path = find_config_path(path)
    if not config_path.is_file():
        raise ConfigError(t("config.missing_file", path=config_path))

    with config_path.open("rb") as handle:
        try:
            raw = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(
                t("config.invalid_toml", path=config_path, detail=exc)
            ) from exc

    return parse_config(raw, config_path)


def parse_config(raw: dict, path: Path) -> AppConfig:
    mode = str(raw.get("mode", "github")).strip().lower()
    if mode not in {"github", "demo"}:
        raise ConfigError(t("config.bad_mode"))

    github = _parse_github(raw.get("github") or {})
    fields = _parse_fields(raw.get("fields") or {})
    pie = _parse_slicing_pie(raw.get("slicing_pie") or {}, raw.get("rates") or {}, raw.get("users"))
    display = _parse_display(raw.get("display") or {})
    expenses = _parse_expenses(raw.get("expenses") or {})
    set_language(display.language)

    return AppConfig(
        mode=mode,
        github=github,
        fields=fields,
        slicing_pie=pie,
        display=display,
        expenses=expenses,
        path=path,
    )


def _parse_github(github_raw: dict) -> GitHubConfig:
    token = str(github_raw.get("token") or "").strip()
    env_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if env_token:
        token = env_token

    owner_type = str(github_raw.get("owner_type") or "auto").strip().lower()
    if owner_type not in {"auto", "organization", "user"}:
        raise ConfigError(t("config.bad_owner_type"))

    try:
        project_number = int(github_raw.get("project_number", 1))
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_project_number")) from exc
    if project_number < 1:
        raise ConfigError(t("config.project_number_range"))

    return GitHubConfig(
        token=token,
        owner=str(github_raw.get("owner") or "").strip(),
        owner_type=owner_type,
        project_number=project_number,
        api_url=str(
            github_raw.get("api_url") or "https://api.github.com/graphql"
        ).strip(),
    )


def _parse_fields(fields_raw: dict) -> FieldsConfig:
    done_values = fields_raw.get("done", ["Done"])
    if isinstance(done_values, str):
        done_tuple = (done_values,)
    else:
        done_tuple = tuple(str(value) for value in done_values)
    if not done_tuple:
        raise ConfigError(t("config.empty_done"))
    return FieldsConfig(
        status=str(fields_raw.get("status") or "Status").strip(),
        done=done_tuple,
        estimate=str(fields_raw.get("estimate") or "Estimate").strip(),
    )


EFFORT_UNITS = frozenset({"hours", "days", "story_points"})
_EFFORT_ALIASES = {
    "hour": "hours",
    "hora": "hours",
    "horas": "hours",
    "day": "days",
    "dia": "days",
    "dias": "days",
    "sp": "story_points",
    "point": "story_points",
    "points": "story_points",
    "story_point": "story_points",
    "storypoints": "story_points",
}


def hours_per_effort_unit(
    effort_unit: str, *, hours_per_day: float, days_per_story_point: float
) -> float:
    """Hours represented by one numeric estimate unit."""
    if effort_unit == "hours":
        return 1.0
    if effort_unit == "days":
        return hours_per_day
    return days_per_story_point * hours_per_day


def _parse_slicing_pie(
    pie_raw: dict, rates_raw: object, users_raw: object
) -> SlicingPieConfig:
    model = load_model_defaults()
    effort_unit, hours_per_day, days_per_point, hours_per_unit = _parse_effort(pie_raw)
    try:
        time_multiplier = float(
            pie_raw.get("time_multiplier", model.time_multiplier)
        )
        default_rate = float(pie_raw.get("default_hourly_rate", 50.0))
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_pie_numbers")) from exc

    if time_multiplier <= 0 or default_rate < 0:
        raise ConfigError(t("config.pie_number_range"))

    split = pie_raw.get("split_among_assignees", True)
    if not isinstance(split, bool):
        raise ConfigError(t("config.bad_split"))

    try:
        review_percent = float(pie_raw.get("review_percent", 0.0))
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_review_percent")) from exc
    if review_percent < 0 or review_percent > 100:
        raise ConfigError(t("config.review_percent_range"))

    return SlicingPieConfig(
        time_multiplier=time_multiplier,
        default_hourly_rate=default_rate,
        hours_per_estimate_unit=hours_per_unit,
        split_among_assignees=split,
        users=_parse_users(rates_raw, users_raw),
        effort_unit=effort_unit,
        hours_per_day=hours_per_day,
        days_per_story_point=days_per_point,
        review_percent=review_percent,
    )


def _parse_effort(pie_raw: dict) -> tuple[str, float, float, float]:
    raw_unit = str(pie_raw.get("effort_unit") or "hours").strip().lower()
    effort_unit = _EFFORT_ALIASES.get(raw_unit, raw_unit)
    if effort_unit not in EFFORT_UNITS:
        raise ConfigError(
            t("config.bad_effort_unit", units=", ".join(sorted(EFFORT_UNITS)))
        )
    try:
        hours_per_day = float(pie_raw.get("hours_per_day", 8.0))
        days_per_point = float(pie_raw.get("days_per_story_point", 1.0))
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_effort_numbers")) from exc
    if hours_per_day <= 0 or days_per_point <= 0:
        raise ConfigError(t("config.effort_number_range"))

    # Legacy override: hours_per_estimate_unit still wins when present.
    if "hours_per_estimate_unit" in pie_raw:
        try:
            hours_per_unit = float(pie_raw.get("hours_per_estimate_unit"))
        except (TypeError, ValueError) as exc:
            raise ConfigError(t("config.bad_pie_numbers")) from exc
        if hours_per_unit <= 0:
            raise ConfigError(t("config.pie_number_range"))
        return effort_unit, hours_per_day, days_per_point, hours_per_unit

    hours_per_unit = hours_per_effort_unit(
        effort_unit,
        hours_per_day=hours_per_day,
        days_per_story_point=days_per_point,
    )
    return effort_unit, hours_per_day, days_per_point, hours_per_unit


def _parse_display(display_raw: dict) -> DisplayConfig:
    language = str(display_raw.get("language") or DEFAULT_LANGUAGE).strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        raise ConfigError(
            t(
                "config.bad_language",
                languages=", ".join(sorted(SUPPORTED_LANGUAGES)),
            )
        )
    return DisplayConfig(
        currency_symbol=str(display_raw.get("currency_symbol") or "$"),
        language=language,
    )


def _parse_expenses(expenses_raw: dict) -> ExpensesConfig:
    model = load_model_defaults()
    label = str(expenses_raw.get("label") or "[expensa]").strip()
    if not label:
        raise ConfigError(t("config.empty_expense_label"))
    currency = str(expenses_raw.get("currency") or "USD").strip().upper()
    if not currency:
        raise ConfigError(t("config.empty_expense_currency"))
    try:
        cash_multiplier = float(
            expenses_raw.get("cash_multiplier", model.cash_multiplier)
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_cash_multiplier")) from exc
    if cash_multiplier <= 0:
        raise ConfigError(t("config.cash_multiplier_range"))
    return ExpensesConfig(
        label=label, currency=currency, cash_multiplier=cash_multiplier
    )


def _parse_users(rates_raw: object, users_raw: object) -> dict[str, PersonConfig]:
    users: dict[str, PersonConfig] = {}
    if rates_raw is None:
        rates_raw = {}
    if not isinstance(rates_raw, dict):
        raise ConfigError(t("config.rates_table"))
    for login, rate in rates_raw.items():
        person = _person_from_legacy(str(login), rate)
        users[person.login.lower()] = person

    if users_raw is None:
        return users
    if isinstance(users_raw, list):
        records = [(None, item) for item in users_raw]
    elif isinstance(users_raw, dict):
        records = list(users_raw.items())
    else:
        raise ConfigError(t("config.users_list"))

    for fallback_login, item in records:
        if isinstance(item, dict):
            person = _person_from_record(item, fallback_login)
        else:
            person = _person_from_legacy(str(fallback_login or ""), item)
        users[person.login.lower()] = person
    return users


def _person_from_legacy(login: str, rate: object) -> PersonConfig:
    login = login.strip()
    if not login:
        raise ConfigError(t("config.missing_login"))
    try:
        value = float(rate)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_rate", login=login)) from exc
    if value < 0:
        raise ConfigError(t("config.rate_range", login=login))
    return PersonConfig(login=login, name="", rate=value, seniority=1.0)


def _person_from_record(item: dict, fallback_login: object) -> PersonConfig:
    login = str(item.get("login") or fallback_login or "").strip()
    if not login:
        raise ConfigError(t("config.missing_login_row"))
    name = str(item.get("name") or "").strip()
    if "rate" not in item:
        raise ConfigError(t("config.missing_rate", login=login))
    try:
        rate = float(item.get("rate"))
        seniority = float(item.get("seniority", 1.0))
    except (TypeError, ValueError) as exc:
        raise ConfigError(t("config.bad_rate_seniority", login=login)) from exc
    if rate < 0 or seniority < 0:
        raise ConfigError(t("config.rate_seniority_range", login=login))
    return PersonConfig(login=login, name=name, rate=rate, seniority=seniority)


def require_github_settings(config: AppConfig) -> None:
    if not config.github.owner:
        raise ConfigError(t("config.missing_owner"))
    if not config.github.token:
        raise ConfigError(t("config.missing_token"))
