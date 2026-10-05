from slicingpie.i18n import get_language, set_language, t
from slicingpie.config import ConfigError, parse_config
from pathlib import Path

import pytest


def test_default_language_is_spanish():
    set_language("es")
    assert get_language() == "es"
    assert "Rebanadas por horas" in t("display.table.title")


def test_unknown_language_falls_back_to_spanish():
    assert set_language("fr") == "es"
    assert get_language() == "es"


def test_config_rejects_unsupported_language():
    with pytest.raises(ConfigError, match="language"):
        parse_config(
            {
                "mode": "demo",
                "display": {"language": "en"},
            },
            Path("x.toml"),
        )


def test_config_sets_language_from_display():
    config = parse_config(
        {
            "mode": "demo",
            "display": {"language": "es", "currency_symbol": "$"},
        },
        Path("x.toml"),
    )
    assert config.display.language == "es"
    assert get_language() == "es"
