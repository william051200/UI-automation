---
name: csv-test-formatter
description: Convert a rough, hand-authored CSV or Markdown test case into the standard ui-auto CSV layout that runs directly via run.ps1. Use when the user has a messy or freeform CSV or Markdown file describing a UI-automation scenario and wants a runnable standard-format CSV.
---

# CSV test formatter

Convert one rough CSV or Markdown file into one canonical CSV. This skill does not run the UI test.

Follow `AGENTS.md` for authoring behavior. Use `scripts/csvfmt/csv_schema.py` for the exact columns, `test_cases/_template.csv` for the starter layout, and `docs/csv-test-format.md` for syntax details.

## Input and output

- Default input: `test_cases\drafts\<name>.csv` or `test_cases\drafts\<name>.md`.
- Default output: `test_cases\<name>.csv`, using the same base filename regardless of the input extension.
- An explicit user-provided output path overrides the default.
- If the user provides one unambiguous draft path, infer the output path automatically. Ask only when the source or destination is ambiguous.

## Markdown input

Recognize rough Markdown test cases with this structure:

- The first level-1 heading is the test-case name.
- A `Prerequisites` section describes setup requirements and constraints; preserve it in the test description or implement it with existing setup/assertion scripts when executable.
- A `Test steps` section contains the scenario. Ordered-list nesting groups phases and substeps but does not change their order.
- Sentences beginning with actions such as **Create**, **Open**, **Click**, **Select**, **Change**, **Add**, **Save**, **Return**, **Right-click**, **Update**, or **Remove** are executable actions.
- Sentences beginning with **Verify** are assertions and must become executable checks when an existing script supports them.
- A fenced code block belongs to the immediately preceding action or verification. Preserve its contents exactly, including XML, source code, commands, paths, names, and versions.
- A `replacing` / `with` pair of fenced blocks describes one edit: replace the first literal block with the second.
- Markdown formatting such as bold text and inline code conveys literal UI labels, names, values, or paths; remove the formatting markers without changing the content.
- Template to copy: `test_cases/_template.csv`
- Full spec: `docs/csv-test-format.md`
- Column schema (do not deviate): `scripts/csvfmt/csv_schema.py`
- Available step scripts (one per step `type`): the files under `scripts/` (e.g. `scripts/input/key.py`, `scripts/input/type_text.py`, `scripts/input/click.py`, `scripts/window/find_window.py`, `scripts/uia/find_control.py`, `scripts/uia/read_console.py`, `scripts/files/screenshot.py`).

### File layout

Two marker-delimited sections, each with its own header row. Ragged rows are fine.

```
# CONFIG
Section,Key,Value
name,,<test_name>
description,,"<one-line description>"

# STEPS
No,Main step,Trigger,script,args,wait_ms,capture,expect_exit,expected_contains,poll_total_ms,poll_interval_ms,screenshot_pass,screenshot_fail,Expected
```

Do not add an `artifacts,screenshot_dir` row unless the test case needs a custom location — omitting it defaults to the standard `screenshots/{name}-{timestamp}` folder naming.

### `# STEPS` columns (exact order, from csv_schema.py)

| Column | Meaning |
|---|---|
| `No` | Phase number; repeat or leave blank to continue within a phase (readability only). |
| `step no` | Global sequential step counter (1, 2, 3… across every step row). |
| `Main step` | Phase name, on the first row of each phase only (readability only). |
| `Trigger` | Human-readable action → becomes the step `description`. |
| `script` | Path under `scripts/`; required for every real step. A blank-`script` row is skipped. |
| `args` | JSON list, e.g. `["enter"]` or `["{vars.x}", "{vars.y}"]`. |
| `wait_ms` | Literal milliseconds to wait after the step (e.g. `700`). |
| `capture` | JSON object mapping `vars.<name>` → a `$.cols[i]` / `$.rows[j].cols[i]` selector. |
| `expect_exit` | Non-zero to assert the script fails (e.g. `1` for "window gone"). |
| `expected_contains` | Presence makes the step an `assert_console_contains`. |
| `poll_total_ms` / `poll_interval_ms` | Literal milliseconds for the assert's polling. |
| `screenshot_pass` / `screenshot_fail` | JSON list of filename patterns; presence makes the step a `screenshot`. |
| `Expected` | Expected-result note (readability only). |

There are **no `id`, `type`, or `args_mode` columns** — the loader auto-generates the id (`step_1`, …) and infers the type (`screenshot_pass` set → `screenshot`; `expected_contains` set → `assert_console_contains`; otherwise the script basename).

## Reformatting rules

1. **Map the user's intent onto the standard columns.** Infer phases (`No` / `Main step`) and a plain-English `Trigger` for each step from the user's notes. Pick the correct `script` for each action from `scripts/`. Never invent step types or scripts that don't exist — if an action doesn't map to a known script, ask the user instead of guessing.
2. **JSON-encode complex cells.** `args` is a JSON list, `capture` is a JSON object, `screenshot_pass`/`screenshot_fail` are JSON lists. Let the CSV writer handle quoting/escaping (cells with commas/quotes get wrapped in double quotes, inner quotes doubled).
3. **Use literal milliseconds** for `wait_ms`, `poll_total_ms`, `poll_interval_ms` — never a timing-key name.
4. **Screenshots are their own rows.** Use the `{ss}` ordering placeholder in the filename (e.g. `{ss}.png` / `{ss}_FAIL.png`); the loader prepends `{artifacts.screenshot_dir}/`.
5. **Unroll loops with a known count.** There is no `foreach` in CSV — repeat the rows for each iteration. The `{ss}` counter then runs globally `ss_1..ss_N`.
5b. **Use a `# LOOP` block for unknown-count loops.** When repetition continues *until a condition clears* (e.g. "repeat on each vulnerable package until none remain"), don't guess a count — emit a `# LOOP` / `# END LOOP` block. The `# LOOP` row's `script`/`args` is the condition (loop runs while its exit code == `expect_exit`, default `0`); its `capture` re-reads the current target each pass; `max_iter` caps iterations. Rows up to `# END LOOP` are the body. See `docs/csv-test-format.md` ("Conditional loops").
6. **Do NOT randomize any values.** Reproducibility requires identical inputs every run — preserve the exact literals the user provides.
7. **Selectors:** prefer `auto_id` + `name` together in `find_control` args; always pass a captured window hwnd as the control's parent.
8. Keep only `name`, `description`, and `artifacts` in `# CONFIG` (the simplified CSV config). Do not add `inputs`, `timing`, or `expected_results` blocks.
9. **Minimize waits.** Prefer polling assertions (`expected_contains` with `poll_total_ms`/`poll_interval_ms`, or `wait_for`) over long fixed `wait_ms` when there's an observable state to wait on; when a fixed `wait_ms` is needed, use the smallest reliable value plus a small margin — don't pad delays. Keep values identical every run (no randomization).
10. **Keep paths machine-portable.** Never hardcode user/profile paths (e.g. `C:\Users\<you>`) — resolve home via `scripts/files/print_home.py` → `{vars.home}`, locate VS via `scripts/window/find_devenv.py` → `{vars.devenv}`, use `{timestamp}` for artifact dirs, match window titles by regex, and discover machine-varying values at runtime so the case runs on any PC/user.

## Workflow

1. Resolve the source and output paths using the convention above.
2. Read the rough CSV or interpret the Markdown using the rules above. Preserve its prerequisites, actions, expected results, literal values, code blocks, screenshots, hierarchy, and repetition.
3. Read `scripts/csvfmt/csv_schema.py`, `test_cases/_template.csv`, `docs/csv-test-format.md`, and the relevant scripts under `scripts\`. Do not search for or read existing converted test cases unless the user explicitly names one as a reference.
4. Map every action to an existing script. Ask instead of inventing a script or schema capability.
5. Write `# CONFIG` with `name`, `description`, and `artifacts` → `screenshot_dir`.
6. Write `# STEPS` using the exact `STEPS_COLUMNS` order from `csv_schema.py`.
7. Populate a global sequential `step no` for every executable row, including `# LOOP` conditions and loop bodies.
8. JSON-encode `args`, `capture`, `screenshot_pass`, and `screenshot_fail`.
9. Unroll known-count repetition. Use `# LOOP` / `# END LOOP` with `max_iter` only when the count is unknown.
10. Write the output CSV.
11. Validate it:

```powershell
uv run python scripts\csvfmt\csv_loader.py test_cases\<name>.csv
```

12. Fix every validation error before finishing.

## Output rule

When returning CSV in chat, output one complete CSV block without surrounding explanation unless the user asks for it.
