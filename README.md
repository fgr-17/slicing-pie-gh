# Slicing Pie - GitHub hours

Python CLI that reads issues from a **GitHub Project**, takes **Done** tickets
with an assignee and estimate, and prints the **Slicing Pie** of work hours
and unreimbursed cash expenses.

Mike Moyer model multipliers (time / cash):
[mike-moyer-model.toml](mike-moyer-model.toml).

Hours come from the Project estimate field. When a ticket has several
assignees, hours are split evenly (configurable).

## Requirements

- Docker
- make

## Quick start (demo, no GitHub)

```bash
make run
```

That uses `slicingpie.toml` in `demo` mode and prints a sample pie. Also:

```bash
make run
make run details
make run verbose
make run json
make help
```

## Real data from a GitHub Project

1. Copy `slicingpie.toml.example` to `slicingpie.local.toml` (this file is gitignored).
2. Set `mode = "github"`, the Project owner, and its number.
3. Create a token:
   - Classic: scopes `repo` and `project` (or `read:project`).
   - Fine-grained: **Issues: Read** and **Projects: Read**.
4. Export the token (preferred over putting it in the file):

```bash
export GITHUB_TOKEN=ghp_...
make run
```

If `slicingpie.local.toml` exists, `make run` uses it. Otherwise it runs the demo.

The Project number is in the URL:

```text
https://github.com/orgs/MY-ORG/projects/12     -> owner = MY-ORG, project_number = 12
https://github.com/users/MY-USER/projects/3    -> owner_type = user, project_number = 3
```

Field names (`Status`, `Estimate`, Done values) must match the Project. Matching
is case-insensitive.

## Repo user rates

```bash
make sync-rates
```

Reads collaborators from each repository linked to the Project (all: direct and
outside) and adds a `[[users]]` block with `default_hourly_rate` and seniority
`1`. If the login already exists, rate, seniority, and name are left alone.

A GitHub Project cannot store app settings. Fields (Status, Estimate, numbers,
text) are per ticket, not a global config or a per-person rate. Project
description is free text. Rates live in the local TOML, which is not versioned.

## Config file

All settings live in a local TOML. The CLI looks for, in order:

1. `--config path`
2. `slicingpie.local.toml` in the current directory
3. `slicingpie.toml`

| Section | Controls |
| --- | --- |
| `mode` | `demo` or `github` |
| `[github]` | token, owner, owner type, Project number |
| `[fields]` | status field name, Done values, estimate field |
| `[slicing_pie]` | effort unit, `review_percent`, default rate, split; optional `time_multiplier` |
| `[[users]]` | per person: `login`, `name`, `rate`, and `seniority` |
| `[display]` | currency symbol and `language` (only `es` for now) |
| `[expenses]` | expense label, currency; optional `cash_multiplier` override |

Model multipliers: [mike-moyer-model.toml](mike-moyer-model.toml).
Full example: [slicingpie.toml.example](slicingpie.toml.example).

Effort on the Project estimate field is converted to **hours** (required by
Slicing Pie) using `effort_unit`:

| `effort_unit` | Hours formula |
| --- | --- |
| `hours` | estimate x 1 |
| `days` | estimate x `hours_per_day` |
| `story_points` | estimate x `days_per_story_point` x `hours_per_day` |

The Project estimate field is a number only; the unit is always
`effort_unit` from the TOML. Legacy `hours_per_estimate_unit` still works as
a direct hours factor when set.

Review hours: if a Done issue was closed by a PR with an **APPROVED**
review, each distinct approver is a reviewer. Set `review_percent` (0-100) to
credit that share of the estimate as work hours to reviewers; assignees keep
the rest. `0` disables review credit.

Done tickets with the configured expense label are cash (not work hours). The
report shows an expenses table (amount + slices) and a general summary
(`work slices + expense slices`). Detail tables:

- `make run detail` / `make run details`: all detail tables (expenses + review)
- `make run detail expenses`: expense rows only
- `make run detail review`: review hours only
- `make run detail expenses review`: both (same as bare detail)

Done tickets **without estimate**, **without assignee**, or with **0 hours**
(or 0 expense amount) do not enter the pie. The header still counts them as
skipped. Lists them with `--show-skipped` (all), or
`--show-no-estimate` / `--show-unassigned` for one reason.

The report shows `name`; if empty, the login. Effective rate `0` hides the
person from the work table. If the effective rate is greater than zero and
hours are **0**, the person is still shown.

`[rates]` with `login = rate` still works: seniority `1` and no name.
`[[users]]` overrides that entry when the login is repeated.

CLI output language comes from `display.language` (default `es`). Code and docs
are English; only terminal strings are translated.

## Development

```bash
make test
make sast
make run ARGS="--verbose"
```

`make sast` prints test coverage, LOC, cyclomatic and cognitive complexity,
maintainability index, duplicate code, Bandit security findings, and Vulture
dead-code suspects. It then evaluates [sast-thresholds.txt](sast-thresholds.txt)
and shows a **Threshold gates** table (OK / WARN / FAIL). The command exits
with code **1** if any gate is FAIL (WARN does not fail the run).
