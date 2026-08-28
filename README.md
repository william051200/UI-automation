# UI-automation

Declarative UI-automation toolkit for Windows desktop apps. Drives mouse, keyboard, screenshots, and UIA-based validation from simple CSV scenarios.

## Install

One PowerShell command on a fresh Windows 10/11 machine:

```powershell
irm https://raw.githubusercontent.com/william051200/UI-automation/main/install.ps1 | iex
```

This installs `uv` + Python + `git` as needed, clones the repo to `%USERPROFILE%\UI-automation`, and installs all pinned dependencies.

## Run a test case

```powershell
cd $HOME\UI-automation
.\run.ps1 test_cases\<test-case>.csv
```

(equivalent to `uv run python run_test.py test_cases\<test-case>.csv`.)

Scenarios are authored as readable CSV files — `run.ps1` loads the `.csv` directly:

```powershell
.\run.ps1 test_cases\<test-case>.csv -q
```

See [CSV test-case format](docs/csv-test-format.md) for the file layout, the in-memory loader, and the `csv-test-formatter` skill.

Replace `<test-case>` with a filename from the [test-case directory](docs/test-cases.md).

Exit codes: `0` pass, `1` assertion failed, `2` runner error.

Add `-q` (or `--quiet`) to suppress per-step echo and successful subcommand stdout; failures, stderr, and the final RESULT line are always shown.

**On any step failure**, before reporting `RESULT: FAIL`, the runner automatically: screenshots the current UI state, screenshots the console/log window if the CSV captured one (a `capture` var whose name contains `cmd`/`console`, e.g. `vars.cmd_hwnd`), and force-closes every window handle the CSV captured (via `close_window.py --force`) so a failed run doesn't leave apps/consoles orphaned for the next run. Each of these is best-effort and never masks the original failure.

## Author a new scenario

Describe your scenario as plain numbered steps and let an AI agent convert it into a runnable CSV test case — you don't need to know which script implements each action or its arguments:

```text
1. Open Notepad from the Start menu.
2. Type "hello from copilot".
3. Save as %TEMP%\out.txt with Ctrl+S.
4. Assert the file exists.
5. Close Notepad.
```

> Convert these steps into `test_cases/notepad_save.csv` and validate it by running `.\run.ps1 test_cases\notepad_save.csv -q`.

See [`docs/authoring-scenarios.md`](docs/authoring-scenarios.md) for the full workflow and more example prompts.

## Run the tests

```powershell
uv run python -m unittest discover -s tests -v
```

37 stdlib `unittest` cases covering the helper scripts and the CSV loader — no extra dev dependencies required.

## Run remotely on a DevBox (self-hosted runner)

Testers can trigger tests on any registered DevBox from the browser — no RDP
needed for the run itself. **Every tester works on their own fork** and
registers runners against it.

**One-time laptop setup:** fork <https://github.com/william051200/UI-automation>,
then enable Actions: your fork → Settings → Actions → General → "Allow all
actions" → Save.

**One-time DevBox setup** (RDP in, admin PowerShell — one line):

```powershell
irm https://raw.githubusercontent.com/<your-handle>/UI-automation/main/scripts/setup-remote-runner.ps1 | iex
```

The bootstrap clones your fork, installs `uv` + deps, prompts once for a
runner-registration token, auto-composes a `<DDMMYYYY>[-<suffix>]-<N>`
label, registers the runner, and pushes the workflow update to your
fork's `main`. See [`docs/REMOTE_RUNNING.md`](docs/REMOTE_RUNNING.md) for
the full walkthrough.

**Day-to-day (browser only):** Open your fork's Actions tab
(`https://github.com/<your-handle>/UI-automation/actions/workflows/run-ui-tests.yml`) →
**Run workflow** → pick a CSV + your DevBox label.

Full guide, including the label convention, per-run cleanup behaviour, and
troubleshooting: [`docs/REMOTE_RUNNING.md`](docs/REMOTE_RUNNING.md).

## Using with Copilot CLI

If you have [GitHub Copilot CLI](https://github.com/github/gh-copilot) (or any other agent that reads `AGENTS.md`) installed, you can drive the toolkit conversationally. The repo's [`AGENTS.md`](AGENTS.md) is auto-loaded and contains the rules the agent must follow when authoring or editing test cases. For the human-facing workflow and example prompts, see [`docs/authoring-scenarios.md`](docs/authoring-scenarios.md).

### Install the Copilot CLI

Don't have it yet? Run the bundled installer. It sets up **both** the standalone agentic `copilot` CLI and the `gh copilot` extension (whichever is missing), then walks you through login:

```powershell
.\install-copilot.ps1
```

Or one-line, straight from GitHub:

```powershell
irm https://raw.githubusercontent.com/william051200/UI-automation/main/install-copilot.ps1 | iex
```

Pass `-NoLogin` to install without the interactive sign-in prompts.

### Token-efficient Copilot usage

Driving the runner through Copilot CLI is convenient but costs LLM tokens per turn. To keep costs low without changing test behavior:

- **Skip the LLM entirely** for routine runs — invoke `.\run.ps1 <spec>` directly. This is the biggest saving (~0 LLM tokens).
- **Pass `-q`** when Copilot does run the scenario; this strips per-step echo from the output the model sees.
- **Scope the prompt** so Copilot doesn't speculatively read source files. Example: *"Run `.\run.ps1 ... -q`. Report only the exit code and any FAIL lines. Do not read `run_test.py` or the CSV spec."*
- **Batch follow-ups** into one prompt — each new turn replays the whole conversation, so 3 small turns cost ~3x one combined turn.

## Documentation

- [File structure](docs/file-structure.md) — what each file and folder in the repo is for.
- [CSV test-case format](docs/csv-test-format.md) — author/run test cases as `.csv`; spec layout, step types, placeholders, capture syntax. The `csv-test-formatter` skill tidies rough CSV into the standard layout.
- [Authoring scenarios with AI](docs/authoring-scenarios.md) — describe plain steps to an agent and get a runnable CSV.
- [Remote DevBox execution](docs/REMOTE_RUNNING.md) — register a DevBox as a self-hosted runner; trigger runs from the browser.
- [`AGENTS.md`](AGENTS.md) — auto-loaded instructions for AI coding agents working in this repo.
- [Reproducibility](docs/reproducibility.md) — how runs stay bit-identical.
- [Troubleshooting](docs/troubleshooting.md) — DPI, multi-monitor, UI language, legacy pip path.

## License

[MIT](LICENSE) © 2026 william051200
