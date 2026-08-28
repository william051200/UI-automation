# File structure

A guided tour of every file and folder in this repo, so you can find your way around quickly.

## Top level

| Path | Purpose |
|---|---|
| `README.md` | Project overview, install command, example invocation, doc index. |
| `AGENTS.md` | Auto-loaded instructions for AI coding agents (Copilot CLI, Codex CLI, Cursor, Aider, Claude Code, …) working in this repo. Follows the [agents.md](https://agents.md/) convention. |
| `LICENSE` | MIT license. |
| `install.ps1` | One-line bootstrap installer for a fresh Windows machine (see [Entry points](#entry-points)). |
| `install-copilot.ps1` | Optional installer for the GitHub Copilot CLI — sets up both the standalone `copilot` CLI and the `gh copilot` extension (whichever is missing) and triggers interactive login. |
| `setup.ps1` | Shared dependency installer. Defaults to the verified offline wheelhouse and supports online `uv sync` when requested. |
| `run.ps1` | Thin shortcut wrapper: `.\run.ps1 <spec> [-q]` → `uv run python run_test.py <spec> [-q]`. Lets you invoke a scenario without going through an LLM. |
| `run_test.py` | CSV test-spec runner (see [Entry points](#entry-points)). |
| `pyproject.toml` | Project metadata + direct dependencies (`pyautogui`, `pywinauto`, `Pillow`, `websocket-client`). Pins Python to `>=3.10,<3.13`. |
| `requirements.txt` | Human-edited top-level requirements list (mirrors `pyproject.toml` deps). |
| `requirements.lock.txt` | Fully resolved, pinned dependency list for `pip` users. |
| `uv.lock` | `uv`-generated lockfile pinning every transitive dependency with content hashes. |
| `ui-auto-wheelhouse.zip` | SHA-256-verified archive of the pinned Windows wheels used by offline setup. |
| `.python-version` | Interpreter version pin used by `uv` to fetch the exact Python build. |
| `.gitignore` | Excludes `.venv/`, `screenshots/`, and other local artifacts from git. |
| `.venv/` | Local virtual environment created by `uv sync` (not committed). |
| `screenshots/` | Per-run screenshot artifacts written under `screenshots/<name>-<timestamp>/` (not committed). |
| `docs/` | Markdown documentation — see [docs/](#docs). |
| `scripts/` | Primitive Python helpers invoked by `run_test.py`, grouped into category subfolders — see [scripts/](#scripts) and [scripts-reference.md](scripts-reference.md). |
| `test_cases/` | Declarative CSV scenarios — see [test_cases/](#test_cases). |
| `tests/` | Stdlib `unittest` coverage for the helper scripts and the CSV loader. Run with `uv run python -m unittest discover -s tests -v`. |

## Entry points

### `install.ps1`
Zero-state bootstrap for a clean Windows 10/11 machine. In order it:

1. Installs `uv` from `astral.sh` if missing.
2. Installs `git` via `winget` if missing.
3. Clones (or `git pull`s) the repo into `%USERPROFILE%\UI-automation`.
4. Calls `setup.ps1` to create the Python environment and install all pinned dependencies.
5. Prints the example command to run the bundled scenario.

Designed to be invoked via `irm https://raw.githubusercontent.com/william051200/UI-automation/main/install.ps1 | iex`.

### `install-copilot.ps1`
Optional, standalone installer for the GitHub Copilot CLI — useful for users whose machines don't have it set up yet. Idempotent; in order it:

1. Installs the standalone agentic `copilot` CLI via `winget install GitHub.Copilot` (falling back to `npm install -g @github/copilot`, installing Node.js LTS first if needed).
2. Installs the GitHub `gh` CLI via `winget` if missing.
3. Installs (or upgrades) the `gh copilot` extension.
4. Triggers interactive login: `gh auth login` if not already authenticated, then launches `copilot` so you can run its `/login` slash command.

Pass `-NoLogin` to skip the sign-in prompts. Invoke locally with `.\install-copilot.ps1` or via `irm https://raw.githubusercontent.com/william051200/UI-automation/main/install-copilot.ps1 | iex`.

### `setup.ps1`
Shared dependency installer for developers and remote-runner onboarding. It verifies that `uv` is on `PATH` and defaults to installing `requirements.lock.txt` from the SHA-256-verified `ui-auto-wheelhouse.zip` without using a package index. Pass `-DependencyMode Online` to use `uv sync`, or `-EnvironmentPath` to target an environment other than the local `.venv`. Use `install.ps1` instead on a fresh machine.

### `run.ps1`
Thin PowerShell wrapper around `uv run python run_test.py`. Takes the spec path as its first argument and forwards any remaining flags (e.g. `-q`). `Set-Location $PSScriptRoot` lets you call it from any working directory, and it propagates the runner's exit code unchanged.

```powershell
.\run.ps1 test_cases\<test-case>.csv
.\run.ps1 test_cases\<test-case>.csv -q
```

### `run_test.py`
The test runner. Given a CSV spec, it:

- Parses the `# CONFIG` and `# STEPS` sections into `inputs`, `artifacts`, `timing`, and `steps` (format documented in [`csv-test-format.md`](csv-test-format.md)).
- Enables per-monitor v2 DPI awareness so virtual-pixel clicks line up with physical-pixel UIA rectangles on HiDPI displays.
- Walks `steps` in order, dispatching each one by invoking the matching `scripts/*.py` as a subprocess (with `args` / `args_expr` substituted from captured variables and inputs).
- Captures stdout from helper scripts and stores fields in `vars.*` for later steps (see `capture:` clauses).
- Evaluates assertions (`assert_console_contains`, `expect_exit`, etc.) and polls where requested.
- Saves screenshots into `artifacts.screenshot_dir`.
- Exits **0** on full pass, **1** on a failed assertion, **2** on runner error (bad spec, missing script, etc.).

Pass `-q` / `--quiet` to suppress per-step headers and successful subcommand stdout — useful when running under an LLM to keep token usage down. Failure output, stderr, and the final `RESULT` line are always shown.

Usage: `uv run python run_test.py test_cases\<scenario>.csv [-q]`.

## `scripts/`

Single-purpose Python CLIs used as primitives by `run_test.py` (and runnable directly for debugging). They are organized into category subfolders:

| Subfolder | Contents |
|---|---|
| `scripts/web/` | Browser automation over the Chrome DevTools Protocol (`cdp_client`, `browser_launch`, `browser_goto`, `dom_get_html`, `dom_interact`, `dom_query`, `dom_eval`). |
| `scripts/input/` | Synthetic mouse/keyboard input at screen coordinates (`click`, `type_text`, `key`, `drag`, `scroll`). |
| `scripts/window/` | Window management — find, focus, maximize, launch, close, poll-wait, and dialog-click (`find_window`, `activate_window`, `maximize_window`, `close_window`, `launch`, `wait_for`, `click_in_dialog`, `find_devenv`). |
| `scripts/uia/` | UI Automation inspection / text reads / combo selection (`find_control`, `read_console`, `read_text`, `uia_tree`, `ui_fingerprint`, `select_combo`). |
| `scripts/files/` | Screenshots, file writes/asserts, clipboard, home dir (`screenshot`, `write_text`, `assert_file_exists`, `clipboard`, `print_home`). |
| `scripts/csvfmt/` | In-memory CSV-spec loader/schema consumed by `run_test.py` (`csv_loader`, `csv_schema`). |
| `scripts/dotnet/` | .NET version-discovery helper for VS/SDK scenarios (`aspnet_majors`). |

See [`scripts-reference.md`](scripts-reference.md) for what every script does, its step `type`, arguments, and exit codes.

| File | Purpose |
|---|---|
| [`file-structure.md`](file-structure.md) | This document — layout of the repo. |
| [`scripts-reference.md`](scripts-reference.md) | What every `scripts/` helper does — step `type`, arguments, exit codes, grouped by category. |
| [`csv-test-format.md`](csv-test-format.md) | Reference for the CSV spec layout — `# CONFIG`/`# STEPS` sections, columns, step types, placeholders, and `capture` rules. |
| [`authoring-scenarios.md`](authoring-scenarios.md) | How to author a test case by describing plain steps to an AI agent (Copilot CLI / other agents), which produces a runnable CSV. |
| [`reproducibility.md`](reproducibility.md) | Why runs stay bit-identical (pinned inputs, UIA targeting, locked deps). |
| [`troubleshooting.md`](troubleshooting.md) | DPI scaling, multi-monitor, UI-language, and legacy pip path issues. |
| [`test-cases.md`](test-cases.md) | Catalog of the scenarios under `test_cases/` — one row per scenario with a short description. |

## `test_cases/`

Holds the declarative scenarios consumed by `run_test.py`. Active scenarios use `<type>-<ID>-<description>.csv`; legacy scenarios are retained under `test_cases/v0/`. See [`test-cases.md`](test-cases.md) for the complete directory.
