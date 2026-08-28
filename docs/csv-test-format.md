# CSV test-case format

Test cases are plain-text **CSV** — the version-control-friendly, **hand-authored source of truth**. `run.ps1` loads a `.csv` spec directly into the runner (in memory) and runs it.

```powershell
# Run a CSV test case directly
.\run.ps1 test_cases\<test-case>.csv -q
```

The layout favors **readability**: steps are grouped into numbered phases — plain-English descriptions on the left, run values in the middle, an `Expected` note on the right. Loops are **unrolled** (one row set per iteration); there is no `foreach`.

Two ways to get a standard-format CSV:

- Copy `test_cases/_template.csv` and fill it in by hand.
- Hand a rough/freeform CSV to the **`csv-test-formatter` skill** (under `.github/skills/`), which reformats it for you.

## File layout

One `.csv` per test, with two marker-delimited sections. A marker is a row whose first cell is `# CONFIG` or `# STEPS` (case-insensitive); each section has its own header row and may have a different column count (ragged rows are fine).

```
# CONFIG
Section,Key,Value
name,,sample_test
description,,"Describe the UI-automation scenario."

# STEPS
No,Main step,Trigger,script,args,wait_ms,capture,expect_exit,expected_contains,poll_total_ms,poll_interval_ms,screenshot_pass,screenshot_fail,Expected
1,Launch powershell,Open Start menu via Win key.,scripts/input/key.py,"[""win""]",700,,,,,,,,
1,,Type 'powershell' into the Start menu.,scripts/input/type_text.py,"[""powershell""]",1200,,,,,,,,
```

### `# CONFIG` section

Three columns: `Section | Key | Value`. Only what the runner needs:

| Section | Notes |
|---|---|
| `name` | one row; `Value` holds the test name |
| `description` | one row |
| `artifacts` | optional; `screenshot_dir` overrides the default folder name (see below). Omit this row to use the default. |

No `inputs`, `timing`, or `expected_results` block — those values live on the step rows; the runner tolerates their absence.

**Screenshot folder naming:** by default the runner writes screenshots to `screenshots/{name}-{timestamp}` (e.g. `screenshots/sample_test-20260812_014452Z`), where `{name}` is the CONFIG `name` value and `{timestamp}` is the UTC run start time — this makes it obvious which test case a folder belongs to. To use a custom folder for a specific test case, add `artifacts,screenshot_dir,<your/custom/path>` to `# CONFIG` (placeholders like `{name}`/`{timestamp}` still work there).

### `# STEPS` section

One row per runnable step, in execution order. A row with a blank `script` is skipped.

Readable columns (authoring-facing, **ignored on import**):

| Column | Meaning |
|---|---|
| **No** | Phase number. Repeated or blank to continue within a phase. |
| **step no** | Global sequential step counter (1, 2, 3… across every step row). |
| **Main step** | Phase name, on the first row of each phase only. |
| **Trigger** | Human-readable action — becomes the step's `description`. |
| **Expected** | Expected-result note. Documentation only. |

Runnable columns:

| Column | Spec key | Notes |
|---|---|---|
| `script` | `script` | required for every real step |
| `args` | `args` (JSON list) | always rendered — `{vars...}`, `{timestamp}`, `{a + b}` arithmetic all work |
| `wait_ms` | `wait_after` | **literal milliseconds** (e.g. `700`) |
| `capture` | `capture` | JSON object mapping `vars.x` → a `$.cols[i]` / `$.rows[j].cols[i]` selector |
| `expect_exit` | `expect_exit` | set non-zero to assert the script fails |
| `expected_contains` | `expected_contains_expr` | presence makes the step an `assert_console_contains` |
| `poll_total_ms` / `poll_interval_ms` | same keys | **literal milliseconds** for the assert's polling |
| `screenshot_pass` / `screenshot_fail` | `args_expr_on_pass` / `args_expr_on_fail` | JSON list of filename patterns; the loader prepends `{artifacts.screenshot_dir}/` |
| `max_iter` | `max_iterations` | **`# LOOP` rows only** — safety cap on a `while` loop (see below) |

**No `id`, `type`, or `args_mode` columns** — the loader derives them:

- **`id`**: auto-generated (`step_1`, `step_2`, …); used only in log/failure messages.
- **`type`**: inferred — `screenshot_pass` set → `screenshot`; `expected_contains` set → `assert_console_contains`; otherwise the **script basename** (e.g. `key`, `click`, `find_control`).
- **`args`**: always rendered (`{placeholder}` substitution applied to every args string), so there is no `plain`/`expr` distinction.

Screenshots are their own step rows; use the `{ss}` ordering placeholder in the filename (e.g. `{ss}.png`). With loops unrolled, `{ss}` counts globally `ss_1..ss_N`.

## Conditional loops (`# LOOP` / `# END LOOP`)

Prefer unrolling. When the repetition count is **not known ahead of time** — e.g. "keep remediating vulnerable packages until none remain" — use a `# LOOP` block; it maps to a runner `while` step.

```
# STEPS
No,Main step,Trigger,script,args,wait_ms,capture,expect_exit,expected_contains,poll_total_ms,poll_interval_ms,screenshot_pass,screenshot_fail,max_iter,Expected
# LOOP,Drain list,While a Vulnerable row exists capture its coords.,scripts/uia/find_control.py,"[""{vars.hwnd}"", ""--name"", ""Vulnerable"", ""--control-type"", ""ListItem""]",,"{""vars.row_x"": ""$.rows[1].cols[7]"", ""vars.row_y"": ""$.rows[1].cols[8]""}",0,,,,,,10,Loop while a vulnerable row exists.
2,,Click the captured row.,scripts/input/click.py,"[""{vars.row_x}"", ""{vars.row_y}""]",200,,,,,,,,,
2,,Press enter to update it.,scripts/input/key.py,"[""enter""]",200,,,,,,,,,
# END LOOP,,,,,,,,,,,,,,
```

Rules:

- The `# LOOP` row opens the block; the matching `# END LOOP` closes it. Rows in between are the loop **body**.
- The `# LOOP` row is the **condition**: its `script` + `args` run before every pass. The loop **continues while the condition's exit code equals `expect_exit`** (default `0`) and stops otherwise. With `find_control` (exit `0` = found, `1` = not found), it runs while a matching control still exists.
- The `# LOOP` row may carry a `capture` mapping (applied to the condition's stdout each pass) so the body can act on the current target's coordinates.
- `max_iter` (on the `# LOOP` row) caps iterations against an infinite loop. If omitted, `run_test.WHILE_MAX_ITERATIONS` applies.
- `{ss}` does **not** reset per iteration — loop screenshots keep counting up (`ss_7`, `ss_8`, ...).

## Loader and skill

| Component | Purpose |
|---|---|
| `scripts\csvfmt\csv_loader.py` | Parses a CSV into the runner's spec dict. Run `uv run python scripts\csvfmt\csv_loader.py <file.csv>` to print the parsed spec as JSON for debugging. |
| `scripts\csvfmt\csv_schema.py` | Shared section markers and column layout. |
| `.github\skills\csv-test-formatter\SKILL.md` | Skill that reformats a rough CSV into this layout. |
| `test_cases\_template.csv` | Skeleton to copy when authoring by hand. |

## Caveats

- `No`, `Main step`, and `Expected` are CSV-only annotations — they never reach the parsed spec.
- Complex cell values (`args`, `capture`, screenshot patterns) are stored as JSON so they stay lossless; the `csv` module quotes/escapes them safely.
- `wait_ms` / `poll_*_ms` are raw integer milliseconds.
- Keep waits minimal: prefer polling assertions (`expected_contains` + `poll_total_ms`/`poll_interval_ms`, or `wait_for`) over long fixed `wait_ms`, and when a fixed wait is needed use the smallest reliable value plus a small safety margin rather than padding.
