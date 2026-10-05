"""Tests for sast-thresholds parsing and gate evaluation."""

from pathlib import Path

from slicingpie.sast_gates import (
    SastResults,
    ThresholdRule,
    evaluate_gates,
    load_thresholds,
)


def test_load_thresholds_skips_comments_and_header_rows(tmp_path: Path) -> None:
    path = tmp_path / "sast-thresholds.txt"
    path.write_text(
        "# comment\n"
        "test_coverage_statements | >= 80% | < 80% | < 70% | note\n"
        "not-a-metric | x | y | z\n"
        "loc_total | info | - | - | track\n",
        encoding="utf-8",
    )
    rules = load_thresholds(path)
    assert [rule.metric_id for rule in rules] == [
        "test_coverage_statements",
        "loc_total",
    ]
    assert rules[0].target == ">= 80%"


def test_coverage_statements_fail_warn_ok() -> None:
    rule = ThresholdRule("test_coverage_statements", ">= 80%", "< 80%", "< 70%", "")
    low = SastResults(coverage_statements=65.0)
    mid = SastResults(coverage_statements=75.0)
    ok = SastResults(coverage_statements=85.0)
    assert evaluate_gates(low, [rule])[0].status == "FAIL"
    assert evaluate_gates(mid, [rule])[0].status == "WARN"
    assert evaluate_gates(ok, [rule])[0].status == "OK"


def test_loc_total_skipped() -> None:
    rule = ThresholdRule("loc_total", "info", "-", "-", "")
    results = SastResults(loc_total=9999)
    assert evaluate_gates(results, [rule])[0].status == "SKIP"


def test_bandit_low_warn_before_fail() -> None:
    rule = ThresholdRule("bandit_low", "0", "> 3", "> 5", "")
    assert evaluate_gates(SastResults(bandit_low=0), [rule])[0].status == "OK"
    assert evaluate_gates(SastResults(bandit_low=4), [rule])[0].status == "WARN"
    assert evaluate_gates(SastResults(bandit_low=6), [rule])[0].status == "FAIL"
