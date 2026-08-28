# AGENTS.md

Instructions for AI coding agents (GitHub Copilot CLI, Codex CLI, Cursor, Aider, Claude Code, etc.) working in this repository.

This file follows the [agents.md](https://agents.md/) convention and is loaded automatically by supporting agents.

## What this repo is

`ui-auto` is a declarative UI-automation toolkit for Windows desktop apps. Test cases are CSV files in `test_cases/`, executed by `run_test.py` (entry point: `.\run.ps1 <spec>`). Each step in a spec maps to a script under `scripts/`.

## Authoritative references (read on demand, not eagerly)

- `README.md` — install, run, top-level usage.
- `docs/csv-test-format.md` — CSV spec layout (`# CONFIG`/`# STEPS` sections, columns, step types, placeholders, capture syntax); the runner loads CSV directly via the in-memory loader in `scripts/csvfmt/`, and the `csv-test-formatter` skill (`.github/skills/`) reformats rough CSV into the standard layout.
- `docs/authoring-scenarios.md` — how to author a test case by describing plain steps to an AI agent (Copilot CLI, etc.).
- `docs/file-structure.md` — what every file/folder is for.
- `docs/reproducibility.md` — why runs must be bit-identical.
- `docs/troubleshooting.md` — DPI, multi-monitor, UI language gotchas.
- `test_cases/_template.csv` — canonical test-case layout.
- `scripts/*.py` — one script per step `type`.

## Hard rules when authoring or editing a test case

1. A test case is ONE `.csv` with two marker-delimited sections: `# CONFIG` (Section/Key/Value rows: `name`, `description`, optionally `artifacts` → `screenshot_dir` to override the default folder name) and `# STEPS` (one row per step). Do not invent new config keys.
2. **Do NOT randomize values.** Reproducibility requires identical values every run.
3. Every real step row needs a `script` and a `Trigger` (becomes the step `description`). Set delays via the `wait_ms` column in **literal milliseconds**. Always populate the `step no` column with a sequential global counter (1, 2, 3… across every step row, including loop bodies) — don't leave it blank.
4. **Selectors:** prefer `auto_id` + `name` together. `scripts/uia/find_control.py` tries AutomationId first, falls back to name. Always pass `parent=` a captured window hwnd.
5. **Capture** window/control handles with the `capture` column as JSON (e.g. `{"vars.<name>": "$.cols[1]"}`) on `find_window` / `find_control` steps; reference them as `{vars.<name>}` in later steps.
6. Artifact paths use `{timestamp}` (substituted at run start, UTC) and `{name}` (the CONFIG `name` value). Default screenshot dir: `screenshots/{name}-{timestamp}` — don't add an `artifacts,screenshot_dir` row unless a test case genuinely needs a custom location; leaving it out keeps the standard `<name>-<timestamp>` folder naming so screenshots are easy to trace back to their test case. For ordered screenshot names use the `{ss}` placeholder in `screenshot_pass` / `screenshot_fail` filenames (renders `ss_1`, `ss_2`, ...; continuous across the whole run including loops, so it never restarts — optionally add `{n}` for the iteration index, e.g. `{ss}_{n}_name.png`).
7. For console assertions set the `expected_contains` column (with `poll_total_ms` / `poll_interval_ms` in literal milliseconds).
8. For file assertions use `assert_file` (supports `--negate`, `--contains`, `--delete`).
9. Do **not** invent new step types. If something doesn't fit, ask before extending the schema.
10. When emitting a new test case, output ONE complete CSV in a single fenced block; no surrounding prose unless the user asks for an explanation.
11. **Minimize waits.** When a step has an observable completion state, use a polling assertion (`expected_contains` with `poll_total_ms`/`poll_interval_ms`, or `wait_for`), especially for asynchronous operations such as app/window launch, build/compile, project scaffolding, or other heavy IDE work. To tolerate slower machines, raise `poll_total_ms` rather than adding `wait_ms`; polling exits early when the condition is met, while a fixed wait always consumes its full duration. Keep `poll_interval_ms` responsive (typically 200-500ms). Use fixed `wait_ms` only when no completion state can be observed, setting it from the observed worst-case duration plus a modest safety margin. Adjust only steps with evidence of timing risk—never blanket-pad waits, randomize values, or vary them between runs.
12. **Keep paths machine-portable.** Never hardcode a user/profile path (e.g. `C:\Users\<you>`) — resolve the home dir via `scripts/files/print_home.py`, capture `{vars.home}`, and build absolute paths from it. Locate Visual Studio via `scripts/window/find_devenv.py` → `{vars.devenv}` rather than a literal install path. Use `{timestamp}` for artifact dirs, match window titles by regex (not user-specific text), and discover machine-varying values (SDK/runtime versions, drive letters) at runtime instead of baking them in, so a case authored on one PC/user runs unchanged on another.

## Iterating on failures

When the user pastes back a failing step id + stderr, respond with the **smallest diff** that fixes that step only. Do not re-emit the whole file unless the structure itself is wrong.

## Running tests and the runner

See the [README](README.md) for install, run, and exit-code semantics. Quick reference:

- Run a scenario: `.\run.ps1 test_cases\<name>.csv -q`
- Unit tests: `uv run python -m unittest discover -s tests -v`

## Environment

Windows 10/11, PowerShell, Python via `uv` with pins in `requirements.lock.txt` / `uv.lock`. Use Windows-style backslash paths. Don't bump pins as part of unrelated changes.

## Style and scope

- Make surgical changes. Don't touch unrelated code or randomize anything that affects reproducibility.
- Don't commit secrets or generated `screenshots/{name}-{timestamp}/` artifacts.
- Don't add new linters, formatters, or test frameworks without being asked.

## Documentation style (Markdown)

- **Do NOT hard-wrap prose.** Write one paragraph per line; let the editor soft-wrap. Do not insert manual line breaks to fit an ~80/100-column limit — they create noisy diffs.
- **This applies to every Markdown file in the repo**, not just `docs/` — including `README.md`, `AGENTS.md`, and skill docs under `.github/skills/**/SKILL.md`.
- Separate paragraphs with a single blank line, not by wrapping a paragraph across multiple lines.
- **Exceptions (these stay as-is — the "certain scenarios"):** fenced code blocks (```` ``` ````), tables, headings, and list/blockquote markup. Never reflow content inside code fences, and keep each table row and list item on its own line.
- If a long list item needs a continuation, keep it as part of that item; don't split a sentence into separate hard-wrapped lines.
