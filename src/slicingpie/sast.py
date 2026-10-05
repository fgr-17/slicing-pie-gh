"""Static analysis report for developers (`python -m slicingpie.sast`)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from slicingpie.sast_gates import SastResults, evaluate_gates, load_thresholds

SRC = Path("src/slicingpie")
ROOT = Path(".")
THRESHOLDS_FILE = ROOT / "sast-thresholds.txt"
RANK_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


_SKIP_NAMES = frozenset({"sast.py", "sast_gates.py", "__pycache__"})


def _source_files() -> list[Path]:
    return sorted(
        path
        for path in SRC.rglob("*.py")
        if path.name not in _SKIP_NAMES
    )


def _source_targets() -> list[str]:
    files = [str(path) for path in _source_files()]
    return files or [str(SRC)]


@dataclass(frozen=True)
class MetricRow:
    name: str
    value: str
    detail: str = ""


def main() -> int:
    console = Console()
    title = Text()
    title.append("SAST", style="bold")
    title.append("  -  static analysis", style="dim")
    console.print(Panel("slicingpie quality snapshot", title=title, border_style="cyan"))

    results = SastResults()
    rows: list[MetricRow] = []
    details: list[tuple[str, str]] = []

    with tempfile.TemporaryDirectory(prefix="slicingpie-sast-") as tmp:
        tmp_path = Path(tmp)
        rows.append(_coverage(console, tmp_path, details, results))
        rows.append(_loc(console, details, results))
        rows.append(_cyclomatic(console, details, results))
        rows.append(_cognitive(console, tmp_path, details, results))
        rows.append(_maintainability(console, details, results))
        rows.append(_duplicates(console, details, results))
        rows.append(_security(console, tmp_path, details, results))
        rows.append(_dead_code(console, details, results))

    summary = Table(title="Summary", show_lines=False, pad_edge=True)
    summary.add_column("Check", style="cyan", no_wrap=True)
    summary.add_column("Value", justify="right", style="bold")
    summary.add_column("Notes", style="dim")
    for row in rows:
        summary.add_row(row.name, row.value, row.detail)
    console.print(summary)

    rules = load_thresholds(THRESHOLDS_FILE)
    gates = evaluate_gates(results, rules)
    if gates:
        console.print()
        gate_table = Table(title="Threshold gates", show_lines=False, pad_edge=True)
        gate_table.add_column("Metric", style="cyan")
        gate_table.add_column("Value", justify="right", style="bold")
        gate_table.add_column("Target", style="dim")
        gate_table.add_column("Status", justify="right")
        fail_count = 0
        warn_count = 0
        for gate in gates:
            style = _status_style(gate.status)
            gate_table.add_row(
                gate.metric_id,
                gate.value,
                gate.target,
                Text(gate.status, style=style),
            )
            if gate.status == "FAIL":
                fail_count += 1
            elif gate.status == "WARN":
                warn_count += 1
        console.print(gate_table)
        console.print()
        summary_line = f"Gates: {fail_count} FAIL, {warn_count} WARN"
        if fail_count:
            console.print(f"[bold red]{summary_line}[/bold red]")
        elif warn_count:
            console.print(f"[bold yellow]{summary_line}[/bold yellow]")
        else:
            console.print(f"[bold green]{summary_line}[/bold green]")

    for heading, body in details:
        if not body.strip():
            continue
        console.print()
        console.print(Text(heading, style="bold"))
        console.print(body, style="dim")

    console.print()
    console.print(
        "[dim]Tools: pytest-cov, radon, complexipy, pylint, bandit, vulture. "
        f"Thresholds: {THRESHOLDS_FILE}[/dim]"
    )
    if any(gate.status == "FAIL" for gate in gates):
        return 1
    return 0


def _status_style(status: str) -> str:
    if status == "OK":
        return "bold green"
    if status == "WARN":
        return "bold yellow"
    if status == "FAIL":
        return "bold red"
    return "dim"


def _coverage(
    console: Console,
    tmp: Path,
    details: list[tuple[str, str]],
    results: SastResults,
) -> MetricRow:
    console.print("[dim]Running coverage...[/dim]")
    report = tmp / "coverage.json"
    completed = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=slicingpie",
            "--cov-report=json:" + str(report),
            "--cov-report=term-missing:skip-covered",
            "-q",
        ],
        cwd=ROOT,
    )
    if not report.is_file():
        results.errors = [completed.stderr or completed.stdout or "no report"]
        details.append(("Coverage", results.errors[0]))
        return MetricRow("Test coverage", "ERR", "pytest-cov failed")

    payload = json.loads(report.read_text(encoding="utf-8"))
    totals = payload.get("totals") or {}
    percent = float(
        totals.get("percent_statements_covered")
        or totals.get("percent_covered")
        or 0.0
    )
    results.coverage_statements = percent
    branch_pct = totals.get("percent_branches_covered")
    if branch_pct is not None:
        results.coverage_branches = float(branch_pct)
    covered = int(totals.get("covered_lines") or 0)
    statements = int(totals.get("num_statements") or 0)
    missing = int(totals.get("missing_lines") or 0)
    branch_note = ""
    if (
        results.coverage_branches is not None
        and abs(results.coverage_branches - percent) >= 0.5
    ):
        branch_note = f", branches {results.coverage_branches:.0f}%"
    files = []
    for path, data in sorted((payload.get("files") or {}).items()):
        file_summary = data.get("summary") or {}
        file_pct = float(
            file_summary.get("percent_statements_covered")
            or file_summary.get("percent_covered")
            or 0.0
        )
        if file_pct < 100:
            short = path.replace("src/", "")
            files.append(f"{short}: {file_pct:.0f}%")
    if files:
        details.append(("Coverage gaps", "\n".join(files[:12])))
    return MetricRow(
        "Test coverage",
        f"{percent:.0f}%",
        f"{covered}/{statements} lines covered, {missing} missing{branch_note}",
    )


def _loc(
    console: Console, details: list[tuple[str, str]], results: SastResults
) -> MetricRow:
    console.print("[dim]Counting LOC (radon raw)...[/dim]")
    payload = _radon_json(["raw", *_source_targets(), "-s", "-j"])
    loc = lloc = sloc = comments = blank = 0
    max_sloc = 0
    for stats in payload.values():
        file_sloc = int(stats.get("sloc") or 0)
        max_sloc = max(max_sloc, file_sloc)
        loc += int(stats.get("loc") or 0)
        lloc += int(stats.get("lloc") or 0)
        sloc += file_sloc
        comments += int(stats.get("comments") or 0) + int(
            stats.get("single_comments") or 0
        )
        blank += int(stats.get("blank") or 0)
    results.loc_total = loc
    results.max_sloc_per_file = max_sloc
    details.append(
        (
            "LOC breakdown",
            f"LOC {loc}  |  SLOC {sloc}  |  LLOC {lloc}  |  comments {comments}  |  blank {blank}",
        )
    )
    return MetricRow("LOC", str(loc), f"SLOC {sloc}, logical {lloc}")


def _cyclomatic(
    console: Console, details: list[tuple[str, str]], results: SastResults
) -> MetricRow:
    console.print("[dim]Cyclomatic complexity (radon cc)...[/dim]")
    payload = _radon_json(["cc", *_source_targets(), "-a", "-s", "-j"])
    blocks: list[tuple[str, int, str]] = []
    total = 0
    count = 0
    worst_rank = "A"
    max_complexity = 0
    for path, entries in payload.items():
        for entry in entries:
            if entry.get("type") == "class":
                continue
            complexity = int(entry.get("complexity") or 0)
            rank = str(entry.get("rank") or "?").upper()
            name = str(entry.get("name") or "?")
            total += complexity
            count += 1
            if complexity > max_complexity:
                max_complexity = complexity
            if RANK_ORDER.get(rank, 0) > RANK_ORDER.get(worst_rank, 0):
                worst_rank = rank
            blocks.append((f"{Path(path).name}:{name}", complexity, rank))
    blocks.sort(key=lambda item: (-item[1], item[0]))
    average = (total / count) if count else 0.0
    results.cyclomatic_avg = average
    results.cyclomatic_max = max_complexity
    results.cyclomatic_worst_rank = worst_rank
    worst = ", ".join(
        f"{name} ({rank}{complexity})" for name, complexity, rank in blocks[:5]
    )
    details.append(
        (
            "Highest cyclomatic",
            "\n".join(
                f"{name}: {rank}{complexity}"
                for name, complexity, rank in blocks[:8]
            ),
        )
    )
    return MetricRow(
        "Cyclomatic complexity",
        f"avg {average:.1f}",
        f"{count} blocks; top: {worst}" if worst else f"{count} blocks",
    )


def _cognitive(
    console: Console,
    tmp: Path,
    details: list[tuple[str, str]],
    results: SastResults,
) -> MetricRow:
    console.print("[dim]Cognitive complexity (complexipy)...[/dim]")
    report = tmp / "cognitive.json"
    completed = _run(
        [
            "complexipy",
            *_source_targets(),
            "--ignore-complexity",
            "--output-format",
            "json",
            "--output",
            str(report),
            "-q",
            "--color",
            "no",
        ],
        cwd=ROOT,
    )
    if not report.is_file():
        details.append(
            ("Cognitive complexity", completed.stderr or completed.stdout or "no report")
        )
        return MetricRow("Cognitive complexity", "ERR", "complexipy failed")

    entries = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        return MetricRow("Cognitive complexity", "0", "no functions")

    complexities = [int(item.get("complexity") or 0) for item in entries]
    average = sum(complexities) / len(complexities)
    results.cognitive_avg = average
    results.cognitive_max = max(complexities)
    ranked = sorted(
        entries,
        key=lambda item: (-int(item.get("complexity") or 0), item.get("path", "")),
    )
    lines = []
    for item in ranked[:8]:
        lines.append(
            f"{Path(str(item.get('path') or '')).name}:{item.get('function_name')}: "
            f"{item.get('complexity')}"
        )
    details.append(("Highest cognitive", "\n".join(lines)))
    top = ranked[0]
    return MetricRow(
        "Cognitive complexity",
        f"avg {average:.1f}",
        (
            f"{len(entries)} functions; max "
            f"{top.get('function_name')}={top.get('complexity')}"
        ),
    )


def _maintainability(
    console: Console, details: list[tuple[str, str]], results: SastResults
) -> MetricRow:
    console.print("[dim]Maintainability index (radon mi)...[/dim]")
    payload = _radon_json(["mi", *_source_targets(), "-s", "-j"])
    scores = []
    ranks: dict[str, int] = {}
    min_mi = 100.0
    for path, data in payload.items():
        mi = float(data.get("mi") or 0.0)
        rank = str(data.get("rank") or "?")
        min_mi = min(min_mi, mi)
        scores.append((Path(path).name, mi, rank))
        ranks[rank] = ranks.get(rank, 0) + 1
    scores.sort(key=lambda item: item[1])
    average = sum(item[1] for item in scores) / len(scores) if scores else 0.0
    results.maintainability_min = min_mi if scores else 0.0
    results.maintainability_avg = average
    details.append(
        (
            "Maintainability (lowest first)",
            "\n".join(f"{name}: {rank} {mi:.1f}" for name, mi, rank in scores[:8]),
        )
    )
    rank_summary = ", ".join(f"{rank}:{count}" for rank, count in sorted(ranks.items()))
    return MetricRow(
        "Maintainability index",
        f"avg {average:.1f}",
        rank_summary or "n/a",
    )


def _duplicates(
    console: Console, details: list[tuple[str, str]], results: SastResults
) -> MetricRow:
    console.print("[dim]Duplicate code (pylint)...[/dim]")
    completed = _run(
        [
            "pylint",
            *_source_targets(),
            "--disable=all",
            "--enable=duplicate-code",
            "--exit-zero",
            "-f",
            "json",
        ],
        cwd=ROOT,
        env={**os.environ, "NO_COLOR": "1"},
    )
    raw = (completed.stdout or "").strip()
    try:
        messages = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        details.append(("Duplicate code", raw or completed.stderr or "parse error"))
        return MetricRow("Duplicate code", "ERR", "pylint failed")

    if not isinstance(messages, list):
        messages = []
    similar = [msg for msg in messages if msg.get("symbol") == "duplicate-code"]
    results.duplicate_blocks = len(similar)
    if similar:
        lines = []
        for msg in similar[:8]:
            lines.append(f"{msg.get('path')}:{msg.get('line')}: {msg.get('message')}")
        details.append(("Duplicate code", "\n".join(lines)))
    return MetricRow(
        "Duplicate code",
        str(len(similar)),
        "similar blocks (pylint)" if similar else "none found",
    )


def _security(
    console: Console,
    tmp: Path,
    details: list[tuple[str, str]],
    results: SastResults,
) -> MetricRow:
    console.print("[dim]Security (bandit)...[/dim]")
    report = tmp / "bandit.json"
    completed = _run(
        [
            "bandit",
            "-r",
            str(SRC),
            "--exclude",
            f"{SRC / 'sast.py'},{SRC / 'sast_gates.py'}",
            "-f",
            "json",
            "-o",
            str(report),
            "-q",
        ],
        cwd=ROOT,
    )
    if not report.is_file():
        details.append(("Security", completed.stderr or completed.stdout or "no report"))
        return MetricRow("Security (bandit)", "ERR", "bandit failed")

    payload = json.loads(report.read_text(encoding="utf-8"))
    totals = (payload.get("metrics") or {}).get("_totals") or {}
    high = int(totals.get("SEVERITY.HIGH") or 0)
    medium = int(totals.get("SEVERITY.MEDIUM") or 0)
    low = int(totals.get("SEVERITY.LOW") or 0)
    results.bandit_high = high
    results.bandit_medium = medium
    results.bandit_low = low
    findings = payload.get("results") or []
    if findings:
        lines = []
        for item in findings[:8]:
            lines.append(
                f"{item.get('filename')}:{item.get('line_number')}: "
                f"{item.get('test_id')} {item.get('issue_text')}"
            )
        details.append(("Bandit findings", "\n".join(lines)))
    return MetricRow(
        "Security (bandit)",
        f"H{high}/M{medium}/L{low}",
        f"{len(findings)} findings",
    )


def _dead_code(
    console: Console, details: list[tuple[str, str]], results: SastResults
) -> MetricRow:
    console.print("[dim]Dead code (vulture)...[/dim]")
    completed = _run(
        ["vulture", *_source_targets(), "--min-confidence", "80"],
        cwd=ROOT,
    )
    lines = [
        line.strip()
        for line in (completed.stdout or "").splitlines()
        if line.strip()
    ]
    results.vulture_hits = len(lines)
    if lines:
        details.append(("Dead code suspects", "\n".join(lines[:12])))
    return MetricRow(
        "Dead code (vulture)",
        str(len(lines)),
        "suspects at >=80% confidence" if lines else "none at >=80% confidence",
    )


def _radon_json(args: list[str]) -> dict:
    completed = _run(["radon", *args], cwd=ROOT)
    raw = (completed.stdout or "").strip()
    if not raw:
        return {}
    return json.loads(raw)


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
