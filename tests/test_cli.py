import json
from pathlib import Path

from slicingpie.cli import main, _detail_scopes
from slicingpie.github_project import GitHubProjectClient, RepositoryUsers
from slicingpie.display import render_report
from slicingpie.pie import build_pie
from helpers import sample_config, ticket


def test_cli_demo_json(capsys, tmp_path: Path):
    config = tmp_path / "slicingpie.toml"
    config.write_text(Path("slicingpie.toml").read_text(encoding="utf-8"), encoding="utf-8")
    code = main(["--config", str(config), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"]["title"].startswith("Lanzamiento")
    logins = [person["login"] for person in payload["people"]]
    assert logins == ["ana", "maria", "carlos"]
    assert payload["totals"]["hours"] == 82
    assert payload["totals"]["slices"] == 10620


def test_cli_skipped_lists_are_opt_in(capsys, tmp_path: Path):
    config = tmp_path / "slicingpie.toml"
    config.write_text(Path("slicingpie.toml").read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["--config", str(config)]) == 0
    plain = capsys.readouterr().out
    assert "#30" not in plain
    assert "#31" not in plain
    assert "Estimado en cero" not in plain
    assert "Tickets Done omitidos" not in plain

    assert main(["--config", str(config), "--show-no-estimate"]) == 0
    estimates = capsys.readouterr().out
    assert "#30" in estimates
    assert "#31" not in estimates
    assert "Estimado en cero" not in estimates

    assert main(["--config", str(config), "--show-unassigned"]) == 0
    unassigned = capsys.readouterr().out
    assert "#31" in unassigned
    assert "#30" not in unassigned

    assert main(["--config", str(config), "--show-skipped"]) == 0
    skipped = capsys.readouterr().out
    assert "#30" in skipped
    assert "#31" in skipped
    assert "Estimado en cero" in skipped


def test_cli_github_missing_token(capsys, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    config = tmp_path / "cfg.toml"
    config.write_text(
        """
mode = "github"

[github]
token = ""
owner = "acme"
project_number = 1
""",
        encoding="utf-8",
    )
    code = main(["--config", str(config)])
    assert code == 1
    err = capsys.readouterr().err
    assert "token" in err.lower()


def test_cli_sync_rates(capsys, tmp_path: Path, monkeypatch):
    config = tmp_path / "slicingpie.local.toml"
    config.write_text(
        """
mode = "github"

[github]
token = "secret"
owner = "acme"
project_number = 2

[slicing_pie]
default_hourly_rate = 50

[[users]]
login = "ana"
name = "Ana"
rate = 80
seniority = 1.2
""",
        encoding="utf-8",
    )

    def fake_list(self):
        return RepositoryUsers(repositories=("acme/app",), logins=("ana", "bob"))

    monkeypatch.setattr(GitHubProjectClient, "list_repository_users", fake_list)
    code = main(["--config", str(config), "--sync-rates"])
    assert code == 0
    text = config.read_text(encoding="utf-8")
    assert "rate = 80" in text
    assert "seniority = 1.2" in text
    assert 'name = "Ana"' in text
    assert 'login = "bob"' in text
    assert "rate = 50" in text
    out = capsys.readouterr().out
    assert "acme/app" in out
    assert "bob" in out
    assert "ana" in out


def test_cli_sync_rates_rejects_demo(capsys, tmp_path: Path):
    config = tmp_path / "slicingpie.toml"
    config.write_text('mode = "demo"\n', encoding="utf-8")
    code = main(["--config", str(config), "--sync-rates"])
    assert code == 1
    assert "github" in capsys.readouterr().err


def test_detail_scopes_normalize():
    assert _detail_scopes(None) == frozenset()
    assert _detail_scopes([]) == frozenset({"expenses", "review"})
    assert _detail_scopes(["review"]) == frozenset({"review"})
    assert _detail_scopes(["expenses", "REVIEW"]) == frozenset({"expenses", "review"})


def test_detail_scopes_reject_unknown():
    try:
        _detail_scopes(["expenses", "cash"])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "cash" in str(exc)


def test_cli_detail_review_shows_table(capsys, tmp_path: Path):
    config = tmp_path / "slicingpie.toml"
    config.write_text(
        Path("slicingpie.toml").read_text(encoding="utf-8").replace(
            'review_percent = 0.0',
            'review_percent = 20.0',
        ),
        encoding="utf-8",
    )
    assert main(["--config", str(config), "--detail", "review"]) == 0
    out = capsys.readouterr().out
    assert "Detalle de horas de revision" in out
    assert "Rebanadas por horas de trabajo" not in out
    assert "Resumen general" not in out


def test_render_review_detail_lists_shares(capsys):
    report = build_pie(
        [
            ticket(
                "Reviewed",
                assignees=("ana",),
                estimate=10,
                reviewers=("maria",),
            )
        ],
        sample_config(review_percent=20.0),
        project_title="t",
        project_url=None,
    )
    render_report(
        report,
        verbose=False,
        currency_symbol="$",
        detail_review=True,
    )
    out = capsys.readouterr().out
    assert "Detalle de horas de revision" in out
    assert "Reviewed" in out or "#1" in out
    assert "Rebanadas por horas de trabajo" not in out
