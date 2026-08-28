# Authoring a new scenario with AI

The simplest way to build a test case is to **describe it as plain numbered steps and let an AI agent turn it into a runnable CSV**. You don't need to know which script implements each action or what arguments it takes — the agent works that out for you.

This works with [GitHub Copilot CLI](https://github.com/github/gh-copilot) or any other agent that auto-loads [`AGENTS.md`](../AGENTS.md) (Codex CLI, Cursor, Aider, Claude Code, …). The authoring **rules** live in `AGENTS.md` and load automatically — you only drive the conversation.

## Prerequisites

- Repo installed per the [README](../README.md) (`uv`, Python, deps).
- An AI agent installed and authenticated. The quickest path is the bundled installer, which sets up both the standalone `copilot` CLI and the `gh copilot` extension and walks you through login:
  ```powershell
  .\install-copilot.ps1
  ```
- The target Windows app reachable from the Start menu (or with a known launch path).

## The flow

1. **Write your scenario as plain numbered steps** — one action per line, in the order a human would perform them. Mention the app to open, what to type/click, what to assert, and when to screenshot.
2. **Ask the agent to convert and validate** — point it at a filename under `test_cases/` and let it produce the CSV and run it.
3. **Let it run** — the agent saves the CSV and executes `.\run.ps1 test_cases\<name>.csv -q` (no LLM in the run loop). The rules in `AGENTS.md` keep the output reproducible.
4. **On failure, paste the failing step id + stderr back** and ask for a targeted fix. Don't let it re-emit the whole file unless the structure itself is wrong.

You never hand-write `script` paths, `args`, or UIA selectors — the agent picks them (it discovers selectors via Inspect.exe / the `auto_id + name` pattern) and fills in the CSV columns. For the CSV layout itself, see [csv-test-format.md](csv-test-format.md).

## Worked example

The screenshots below walk through the flow end to end, using a Visual Studio "console app" scenario.

**1. Define the test as plain numbered steps:**

![Scenario written as plain numbered steps in a spreadsheet](../test_cases/sample/1-define-test.png)

**2. Prompt the agent to convert and run it:**

![Copilot CLI reading the steps and running the test case](../test_cases/sample/2-prompt-ai-to-proceed.png)

**3. Review the result — the agent reports `RESULT: PASS`:**

![Copilot CLI summarizing the passing run and what the test does](../test_cases/sample/3-ai-review-result.png)

A smaller Notepad example: give the agent steps like this:

```text
1. Open Notepad from the Start menu.
2. Type "hello from copilot".
3. Save the file as %TEMP%\copilot_test.txt with Ctrl+S.
4. Assert the file exists.
5. Close Notepad by clicking the Close button.
```

Then prompt:

> Convert these steps into a CSV test case at `test_cases/notepad_save.csv` and validate it by running `.\run.ps1 test_cases\notepad_save.csv -q`. Report only the exit code and any FAIL lines.

The agent writes `test_cases/notepad_save.csv`, runs it, and reports the result.

## More example prompts

**Run an existing scenario** (no authoring):
> Run `.\run.ps1 test_cases\<test-case>.csv -q` and report only the exit code and any FAIL lines.

**Variant of an existing scenario:**
> Use `test_cases\_template.csv` to create `test_cases\<test-case>.csv` for the requested scenario, then validate it.

**Repeat-until (unknown count):**
> In `test_cases/<name>.csv`, keep clicking the next "Vulnerable" row until none remain, using a `# LOOP` block. Loops are unrolled otherwise.

**Targeted fix:**
> Step `step_7` fails with `expected_contains not found within 3000 ms`. The text appears but with a leading `PS>` prompt. Update only that step's `expected_contains` — don't touch other steps.

## How the agent knows the rules

`AGENTS.md` is auto-loaded on session start and tells the agent the CSV layout, the reproducibility constraints (no randomness), and the selector conventions. Everything under `docs/`, `scripts/`, and `test_cases/` is read on demand. For Copilot-only tweaks, add `.github/copilot-instructions.md`.

## Token-efficient usage

See the [*Token-efficient Copilot usage*](../README.md#token-efficient-copilot-usage) section in the README — the biggest saving is invoking `.\run.ps1 <spec>` directly for routine runs (no LLM tokens).

## See also

- [csv-test-format.md](csv-test-format.md) — full CSV column and section reference, step types, placeholders, and capture syntax.
- [scripts-reference.md](scripts-reference.md) — catalog of every step script under `scripts/`.
- [`AGENTS.md`](../AGENTS.md) — rules the agent follows (auto-loaded).
- [troubleshooting.md](troubleshooting.md) — DPI, multi-monitor, UI-language gotchas.
- [reproducibility.md](reproducibility.md) — why runs must stay bit-identical.

## Running tests

Unit tests for the loader and runner live in `tests/`:

```powershell
uv run python -m unittest discover -s tests -v
```
