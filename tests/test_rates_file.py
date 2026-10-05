from slicingpie.rates_file import merge_rates_text, upsert_default_rates


SAMPLE = """\
mode = "github"

[github]
token = "secret"
owner = "acme"

[slicing_pie]
default_hourly_rate = 50.0

[rates]
# login de GitHub = tarifa horaria de mercado
# ana = 75
Ana = 80

[display]
currency_symbol = "$"
"""

USERS = """\
mode = "github"

[[users]]
login = "Ana"
name = "Ana Perez"
rate = 80
seniority = 1.5

[display]
currency_symbol = "$"
"""


def test_merge_adds_missing_and_keeps_edited_rates():
    updated, added, kept = merge_rates_text(
        SAMPLE, ["bob", "Ana", "dependabot-friend"], 50.0
    )
    assert added == ("bob", "dependabot-friend")
    assert kept == ("Ana",)
    assert 'token = "secret"' in updated
    assert "Ana = 80" in updated
    assert "# ana = 75" in updated
    assert 'login = "bob"' in updated
    assert 'login = "dependabot-friend"' in updated
    assert "rate = 50" in updated
    assert "seniority = 1" in updated
    assert updated.index('login = "bob"') < updated.index("[display]")
    assert "\n\n[display]" in updated


def test_merge_keeps_name_rate_and_seniority():
    updated, added, kept = merge_rates_text(USERS, ["Ana", "bob"], 50)
    assert added == ("bob",)
    assert kept == ("Ana",)
    assert 'name = "Ana Perez"' in updated
    assert "rate = 80" in updated
    assert "seniority = 1.5" in updated
    assert 'login = "bob"' in updated
    assert updated.index("seniority = 1.5") < updated.index('login = "bob"')


def test_merge_is_idempotent_when_nothing_is_new():
    updated, added, kept = merge_rates_text(SAMPLE, ["Ana"], 50)
    assert updated == SAMPLE
    assert added == ()
    assert kept == ("Ana",)


def test_merge_appends_section_when_missing():
    text = 'mode = "github"\n'
    updated, added, kept = merge_rates_text(text, ["zoe"], 12.5)
    assert added == ("zoe",)
    assert kept == ()
    assert 'login = "zoe"' in updated
    assert updated.rstrip().endswith("seniority = 1")
    assert "[[users]]" in updated


def test_upsert_writes_file(tmp_path):
    path = tmp_path / "slicingpie.local.toml"
    path.write_text(SAMPLE, encoding="utf-8")
    added, kept = upsert_default_rates(path, ["bob", "Ana"], 50)
    assert added == ("bob",)
    assert kept == ("Ana",)
    text = path.read_text(encoding="utf-8")
    assert 'login = "bob"' in text
    assert "Ana = 80" in text
    assert not path.with_suffix(".toml.tmp").exists()
