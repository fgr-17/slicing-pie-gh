"""Parse sast-thresholds.txt and evaluate gate status."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RANK_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


@dataclass(frozen=True)
class ThresholdRule:
    metric_id: str
    target: str
    warn: str
    fail: str
    notes: str = ""


@dataclass
class SastResults:
    coverage_statements: float | None = None
    coverage_branches: float | None = None
    loc_total: int = 0
    max_sloc_per_file: int = 0
    cyclomatic_avg: float = 0.0
    cyclomatic_worst_rank: str = "A"
    cyclomatic_max: int = 0
    cognitive_avg: float = 0.0
    cognitive_max: int = 0
    maintainability_min: float = 100.0
    maintainability_avg: float = 0.0
    duplicate_blocks: int = 0
    bandit_high: int = 0
    bandit_medium: int = 0
    bandit_low: int = 0
    vulture_hits: int = 0
    errors: list[str] | None = None


def load_thresholds(path: Path) -> list[ThresholdRule]:
    if not path.is_file():
        return []
    rules: list[ThresholdRule] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "|" not in stripped:
            continue
        parts = [part.strip() for part in stripped.split("|")]
        if len(parts) < 4:
            continue
        metric_id = parts[0]
        if not re.fullmatch(r"[a-z0-9_]+", metric_id):
            continue
        notes = parts[4] if len(parts) > 4 else ""
        rules.append(
            ThresholdRule(
                metric_id=metric_id,
                target=parts[1],
                warn=parts[2],
                fail=parts[3],
                notes=notes,
            )
        )
    return rules


@dataclass(frozen=True)
class GateResult:
    metric_id: str
    value: str
    target: str
    status: str  # OK, WARN, FAIL, SKIP, ERR


def evaluate_gates(
    results: SastResults, rules: list[ThresholdRule]
) -> list[GateResult]:
    gates: list[GateResult] = []
    for rule in rules:
        gates.append(_evaluate_rule(results, rule))
    return gates


def _evaluate_rule(results: SastResults, rule: ThresholdRule) -> GateResult:
    if rule.target.strip().lower() == "info" or rule.warn.strip() == "-":
        value = _metric_value(results, rule.metric_id)
        return GateResult(rule.metric_id, value, rule.target, "SKIP")

    if results.errors and rule.metric_id.startswith("test_coverage"):
        return GateResult(rule.metric_id, "ERR", rule.target, "ERR")

    status, display = _status_for(rule, results)
    return GateResult(rule.metric_id, display, rule.target, status)


def _metric_value(results: SastResults, metric_id: str) -> str:
    mapping = {
        "test_coverage_statements": lambda: _pct(results.coverage_statements),
        "test_coverage_branches": lambda: _pct(results.coverage_branches),
        "loc_total": lambda: str(results.loc_total),
        "loc_sloc_per_file": lambda: str(results.max_sloc_per_file),
        "cyclomatic_avg": lambda: f"{results.cyclomatic_avg:.1f}",
        "cyclomatic_max_function": lambda: (
            f"{results.cyclomatic_worst_rank}{results.cyclomatic_max}"
        ),
        "cognitive_avg": lambda: f"{results.cognitive_avg:.1f}",
        "cognitive_max_function": lambda: str(results.cognitive_max),
        "maintainability_min_file": lambda: f"{results.maintainability_min:.1f}",
        "maintainability_avg": lambda: f"{results.maintainability_avg:.1f}",
        "duplicate_code_blocks": lambda: str(results.duplicate_blocks),
        "bandit_high": lambda: str(results.bandit_high),
        "bandit_medium": lambda: str(results.bandit_medium),
        "bandit_low": lambda: str(results.bandit_low),
        "vulture_confidence_80": lambda: str(results.vulture_hits),
    }
    if metric_id not in mapping:
        return "n/a"
    return mapping[metric_id]()


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f}%"


def _status_for(rule: ThresholdRule, results: SastResults) -> tuple[str, str]:
    metric_id = rule.metric_id
    if metric_id == "test_coverage_statements":
        return _higher_better(
            results.coverage_statements,
            rule,
            display=_pct(results.coverage_statements),
        )
    if metric_id == "test_coverage_branches":
        return _higher_better(
            results.coverage_branches,
            rule,
            display=_pct(results.coverage_branches),
        )
    if metric_id == "loc_sloc_per_file":
        return _lower_better(
            float(results.max_sloc_per_file),
            rule,
            display=str(results.max_sloc_per_file),
        )
    if metric_id == "cyclomatic_avg":
        return _lower_better(
            results.cyclomatic_avg,
            rule,
            display=f"{results.cyclomatic_avg:.1f}",
        )
    if metric_id == "cyclomatic_max_function":
        return _cyclomatic_max(results, rule)
    if metric_id == "cognitive_avg":
        return _lower_better(
            results.cognitive_avg,
            rule,
            display=f"{results.cognitive_avg:.1f}",
        )
    if metric_id == "cognitive_max_function":
        return _lower_better(
            float(results.cognitive_max),
            rule,
            display=str(results.cognitive_max),
        )
    if metric_id == "maintainability_min_file":
        return _maintainability_min(results.maintainability_min, rule)
    if metric_id == "maintainability_avg":
        return _maintainability_avg(results.maintainability_avg, rule)
    if metric_id in {
        "duplicate_code_blocks",
        "bandit_high",
        "bandit_medium",
        "bandit_low",
        "vulture_confidence_80",
    }:
        value = {
            "duplicate_code_blocks": results.duplicate_blocks,
            "bandit_high": results.bandit_high,
            "bandit_medium": results.bandit_medium,
            "bandit_low": results.bandit_low,
            "vulture_confidence_80": results.vulture_hits,
        }[metric_id]
        return _count_gate(float(value), rule, display=str(value))
    return ("SKIP", _metric_value(results, metric_id))


def _parse_number(text: str) -> float | None:
    cleaned = text.strip().replace("%", "")
    match = re.search(r"([\d.]+)", cleaned)
    if not match:
        return None
    return float(match.group(1))


def _parse_compare(text: str) -> tuple[str, float] | tuple[str, str] | None:
    stripped = text.strip()
    if stripped in {"", "-"}:
        return None
    rank = re.fullmatch(r"rank\s+([A-F])", stripped, re.IGNORECASE)
    if rank:
        return ("rank", rank.group(1).upper())
    range_match = re.fullmatch(r"([\d.]+)\s*-\s*([\d.]+)", stripped)
    if range_match:
        return (
            "range",
            f"{range_match.group(1)}-{range_match.group(2)}",
        )
    for op in (">=", "<=", ">", "<", "=="):
        if stripped.startswith(op):
            return (op, _parse_number(stripped[len(op) :]) or 0.0)
    return None


def _higher_better(
    value: float | None,
    rule: ThresholdRule,
    *,
    display: str,
) -> tuple[str, str]:
    if value is None:
        return ("SKIP", display)
    fail = _parse_compare(rule.fail)
    warn = _parse_compare(rule.warn)
    target = _parse_compare(rule.target)
    if fail and fail[0] == "<" and value < fail[1]:
        return ("FAIL", display)
    if warn and warn[0] == "<" and value < warn[1]:
        return ("WARN", display)
    if target and target[0] == ">=" and value >= target[1]:
        return ("OK", display)
    if target and target[0] == ">=":
        return ("WARN", display)
    return ("OK", display)


def _lower_better(
    value: float,
    rule: ThresholdRule,
    *,
    display: str,
) -> tuple[str, str]:
    fail = _parse_compare(rule.fail)
    warn = _parse_compare(rule.warn)
    target = _parse_compare(rule.target)
    if fail and fail[0] == ">" and value > fail[1]:
        return ("FAIL", display)
    if warn and warn[0] == ">" and value > warn[1]:
        return ("WARN", display)
    if target and target[0] == "<=" and value <= target[1]:
        return ("OK", display)
    if target and target[0] == "<=":
        return ("WARN", display)
    return ("OK", display)


def _count_gate(
    value: float,
    rule: ThresholdRule,
    *,
    display: str,
) -> tuple[str, str]:
    fail = _parse_compare(rule.fail)
    warn = _parse_compare(rule.warn)
    if fail and fail[0] in {">=", ">"}:
        limit = fail[1]
        if fail[0] == ">" and value > limit:
            return ("FAIL", display)
        if fail[0] == ">=" and value >= limit:
            return ("FAIL", display)
    if warn and warn[0] in {">=", ">"}:
        limit = warn[1]
        if warn[0] == ">=" and value >= limit:
            if fail and fail[0] == ">=" and value >= fail[1]:
                pass
            else:
                return ("WARN", display)
        if warn[0] == ">" and value > limit:
            if not (fail and fail[0] == ">" and value > fail[1]):
                return ("WARN", display)
    if value == 0:
        return ("OK", display)
    return ("WARN", display)


def _cyclomatic_max(
    results: SastResults, rule: ThresholdRule
) -> tuple[str, str]:
    display = f"{results.cyclomatic_worst_rank}{results.cyclomatic_max}"
    rank = results.cyclomatic_worst_rank.upper()
    rank_level = RANK_ORDER.get(rank, 0)
    fail = _parse_compare(rule.fail)
    warn = _parse_compare(rule.warn)
    if fail and fail[0] == "rank":
        fail_level = RANK_ORDER.get(fail[1], 99)
        if rank_level >= fail_level:
            return ("FAIL", display)
    if warn and warn[0] == "rank":
        warn_level = RANK_ORDER.get(warn[1], 99)
        if rank_level >= warn_level:
            return ("WARN", display)
    target = _parse_compare(rule.target)
    if target and target[0] == "<=" and results.cyclomatic_max <= target[1]:
        return ("OK", display)
    return ("WARN", display)


def _maintainability_avg(value: float, rule: ThresholdRule) -> tuple[str, str]:
    display = f"{value:.1f}"
    if value < 35:
        return ("FAIL", display)
    if 35 <= value <= 44:
        return ("WARN", display)
    if value >= 45:
        return ("OK", display)
    return ("WARN", display)


def _maintainability_min(value: float, rule: ThresholdRule) -> tuple[str, str]:
    display = f"{value:.1f}"
    fail = _parse_compare(rule.fail)
    warn = _parse_compare(rule.warn)
    if fail and fail[0] == "<" and value < fail[1]:
        return ("FAIL", display)
    if warn and warn[0] == "range":
        low, high = (float(part) for part in warn[1].split("-"))
        if low <= value <= high:
            return ("WARN", display)
    target = _parse_compare(rule.target)
    if target and target[0] == ">=" and value >= target[1]:
        return ("OK", display)
    return ("WARN", display)
