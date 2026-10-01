import json
from pathlib import Path

from slicingpie.cli import main


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
