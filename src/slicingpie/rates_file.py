from __future__ import annotations

from pathlib import Path
import re


def format_rate(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def upsert_default_rates(
    path: Path, logins: tuple[str, ...] | list[str], default_rate: float
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Append missing logins as [[users]] blocks with the default rate.

    Leaves existing rate, seniority, and name alone. Returns (added, kept).
    """
    original = path.read_text(encoding="utf-8")
    updated, added, kept = merge_rates_text(original, logins, default_rate)
    if updated != original:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)
    return added, kept


def merge_rates_text(
    text: str, logins: tuple[str, ...] | list[str], default_rate: float
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    newline = "\r\n" if "\r\n" in text else "\n"
    ends_with_newline = text.endswith("\n") or text == ""
    lines = text.splitlines()

    wanted = _unique_logins(logins)
    existing, insert_at = _existing_logins(lines)
    added, kept = _partition_logins(wanted, existing)
    if not added:
        return text, added, kept

    new_lines = _blocks_for(added, default_rate)
    updated_lines = _insert_blocks(lines, new_lines, insert_at)
    body = newline.join(updated_lines)
    if ends_with_newline:
        body += newline
    return body, added, kept


def _unique_logins(logins: tuple[str, ...] | list[str]) -> list[str]:
    wanted: list[str] = []
    seen: set[str] = set()
    for login in logins:
        key = login.strip()
        if not key:
            continue
        folded = key.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        wanted.append(key)
    wanted.sort(key=str.casefold)
    return wanted


def _partition_logins(
    wanted: list[str], existing: dict[str, str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    added_list: list[str] = []
    kept_list: list[str] = []
    for login in wanted:
        previous = existing.get(login.casefold())
        if previous is None:
            added_list.append(login)
        else:
            kept_list.append(previous)
    return tuple(added_list), tuple(kept_list)


def _blocks_for(logins: tuple[str, ...], default_rate: float) -> list[str]:
    new_lines: list[str] = []
    for login in logins:
        if new_lines:
            new_lines.append("")
        new_lines.extend(_user_block(login, default_rate))
    return new_lines


def _insert_blocks(
    lines: list[str], new_lines: list[str], insert_at: int | None
) -> list[str]:
    if insert_at is None:
        updated_lines = list(lines)
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.extend(new_lines)
        return updated_lines

    at = insert_at
    while at > 0 and lines[at - 1].strip() == "":
        at -= 1
    block = new_lines
    if at > 0 and lines[at - 1].strip():
        block = ["", *new_lines]
    updated_lines = lines[:at] + block + lines[at:]
    if insert_at < len(lines):
        follow = at + len(block)
        if follow >= len(updated_lines) or updated_lines[follow].strip():
            updated_lines.insert(follow, "")
    return updated_lines


def _existing_logins(lines: list[str]) -> tuple[dict[str, str], int | None]:
    existing: dict[str, str] = {}
    insert_at: int | None = None
    index = 0
    while index < len(lines):
        header = lines[index].split("#", 1)[0].strip()
        if header == "[[users]]":
            end = _next_section(lines, index)
            login = _block_login(lines[index + 1 : end])
            if login:
                existing.setdefault(login.casefold(), login)
            insert_at = end
            index = end
            continue
        if header == "[rates]":
            end = _next_section(lines, index)
            for line in lines[index + 1 : end]:
                key = _rate_key(line)
                if key:
                    existing.setdefault(key.casefold(), key)
            if insert_at is None:
                insert_at = end
            index = end
            continue
        index += 1
    return existing, insert_at


def _user_block(login: str, rate: float) -> list[str]:
    return [
        "[[users]]",
        f"login = {_toml_string(login)}",
        'name = ""',
        f"rate = {format_rate(rate)}",
        "seniority = 1",
    ]


def _block_login(lines: list[str]) -> str | None:
    pattern = re.compile(
        r"""^login\s*=\s*(?:"([^"]*)"|'([^']*)'|([A-Za-z0-9_-]+))\s*(?:#.*)?$"""
    )
    for line in lines:
        match = pattern.match(line.strip())
        if not match:
            continue
        return next(group for group in match.groups() if group is not None)
    return None


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _next_section(lines: list[str], header_idx: int) -> int:
    for index in range(header_idx + 1, len(lines)):
        stripped = lines[index].split("#", 1)[0].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return index
    return len(lines)


def _rate_key(line: str) -> str | None:
    code = line.split("#", 1)[0].strip()
    if not code or "=" not in code:
        return None
    raw_key, _value = code.split("=", 1)
    raw_key = raw_key.strip()
    if len(raw_key) >= 2 and raw_key[0] == raw_key[-1] and raw_key[0] in {'"', "'"}:
        return raw_key[1:-1]
    if re.fullmatch(r"[A-Za-z0-9_-]+", raw_key):
        return raw_key
    return None
