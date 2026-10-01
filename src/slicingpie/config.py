from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib

DEFAULT_CONFIG_NAMES = ("slicingpie.local.toml", "slicingpie.toml")


class ConfigError(ValueError):
    """Configuración inválida o ausente."""


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
class SlicingPieConfig:
    time_multiplier: float
    default_hourly_rate: float
    hours_per_estimate_unit: float
    split_among_assignees: bool
    rates: dict[str, float]


@dataclass(frozen=True)
class DisplayConfig:
    currency_symbol: str


@dataclass(frozen=True)
class AppConfig:
    mode: str
    github: GitHubConfig
    fields: FieldsConfig
    slicing_pie: SlicingPieConfig
    display: DisplayConfig
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


def load_config(path: Path | None = None) -> AppConfig:
    config_path = find_config_path(path)
    if not config_path.is_file():
        raise ConfigError(
            f"No encuentro el archivo de configuración: {config_path}\n"
            "Copia slicingpie.toml.example a slicingpie.toml y rellena los valores."
        )

    with config_path.open("rb") as handle:
        try:
            raw = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"TOML inválido en {config_path}: {exc}") from exc

    return parse_config(raw, config_path)


def parse_config(raw: dict, path: Path) -> AppConfig:
    mode = str(raw.get("mode", "github")).strip().lower()
    if mode not in {"github", "demo"}:
        raise ConfigError("mode debe ser 'github' o 'demo'.")

    github_raw = raw.get("github") or {}
    fields_raw = raw.get("fields") or {}
    pie_raw = raw.get("slicing_pie") or {}
    display_raw = raw.get("display") or {}
    rates_raw = raw.get("rates") or {}

    token = str(github_raw.get("token") or "").strip()
    env_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if env_token:
        token = env_token

    owner_type = str(github_raw.get("owner_type") or "auto").strip().lower()
    if owner_type not in {"auto", "organization", "user"}:
        raise ConfigError("github.owner_type debe ser auto, organization o user.")

    try:
        project_number = int(github_raw.get("project_number", 1))
    except (TypeError, ValueError) as exc:
        raise ConfigError("github.project_number debe ser un entero.") from exc
    if project_number < 1:
        raise ConfigError("github.project_number debe ser >= 1.")

    done_values = fields_raw.get("done", ["Done"])
    if isinstance(done_values, str):
        done_tuple = (done_values,)
    else:
        done_tuple = tuple(str(value) for value in done_values)
    if not done_tuple:
        raise ConfigError("fields.done no puede estar vacío.")

    try:
        time_multiplier = float(pie_raw.get("time_multiplier", 2.0))
        default_rate = float(pie_raw.get("default_hourly_rate", 50.0))
        hours_per_unit = float(pie_raw.get("hours_per_estimate_unit", 1.0))
    except (TypeError, ValueError) as exc:
        raise ConfigError("Los valores numéricos de [slicing_pie] son inválidos.") from exc

    if time_multiplier <= 0 or default_rate < 0 or hours_per_unit <= 0:
        raise ConfigError(
            "time_multiplier y hours_per_estimate_unit deben ser > 0; "
            "default_hourly_rate debe ser >= 0."
        )

    rates: dict[str, float] = {}
    for login, rate in rates_raw.items():
        try:
            rates[str(login).strip().lower()] = float(rate)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"Tarifa inválida para '{login}'.") from exc

    split = pie_raw.get("split_among_assignees", True)
    if not isinstance(split, bool):
        raise ConfigError("slicing_pie.split_among_assignees debe ser true o false.")

    return AppConfig(
        mode=mode,
        github=GitHubConfig(
            token=token,
            owner=str(github_raw.get("owner") or "").strip(),
            owner_type=owner_type,
            project_number=project_number,
            api_url=str(
                github_raw.get("api_url") or "https://api.github.com/graphql"
            ).strip(),
        ),
        fields=FieldsConfig(
            status=str(fields_raw.get("status") or "Status").strip(),
            done=done_tuple,
            estimate=str(fields_raw.get("estimate") or "Estimate").strip(),
        ),
        slicing_pie=SlicingPieConfig(
            time_multiplier=time_multiplier,
            default_hourly_rate=default_rate,
            hours_per_estimate_unit=hours_per_unit,
            split_among_assignees=split,
            rates=rates,
        ),
        display=DisplayConfig(
            currency_symbol=str(display_raw.get("currency_symbol") or "$"),
        ),
        path=path,
    )


def require_github_settings(config: AppConfig) -> None:
    if not config.github.owner:
        raise ConfigError("Falta github.owner en la configuración.")
    if not config.github.token:
        raise ConfigError(
            "Falta el token de GitHub. Ponlo en github.token o en GITHUB_TOKEN."
        )
