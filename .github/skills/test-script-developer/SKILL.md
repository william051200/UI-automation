---
name: test-script-developer
description: Develop the smallest backward-compatible Python step script when a test-case repair has evidence that existing scripts cannot handle the observed UI behavior. Add its unit test, document it, update only the failed CSV step, and return to the repair run.
---

# Test script developer

Add one missing runtime capability for one evidence-backed failed CSV step. This skill is normally invoked automatically by `test-case-repair`; it does not replace CSV conversion or ordinary CSV repair.

Follow `AGENTS.md`. Preserve existing script arguments, defaults, stdout shape, and exit codes so previous test cases continue to work.

## Required context

- The CSV path and failed step id.
- The failed row's `Trigger`, `script`, and `args`.
- The observed stderr, screenshots, UI tree, or other evidence showing the capability gap.

If the evidence does not prove a script capability gap, return control to `test-case-repair` without changing code.

## Decision order

Stop at the first option that handles the observed behavior:

1. Use another existing script and update only the failed CSV row.
2. Add an optional argument to the current script only when its default preserves all existing behavior.
3. Add one new script under the matching `scripts\` category when the behavior is materially different or compatibility cannot be guaranteed.

Do not duplicate an existing capability, create a framework, add a dependency, or change the CSV schema.

## Script contract

- Use `argparse` and accept only the arguments needed by the failed step.
- Keep the operation deterministic and machine-portable.
- Print stable, concise stdout; use tab-separated fields when the CSV must capture values.
- Exit `0` on success, `1` for an expected not-found or assertion failure, and `2` for invalid usage or an unexpected execution failure.
- Surface errors on stderr. Do not silently succeed or weaken the test's assertion.
- Keep one responsibility per script.

## Workflow

1. Read the failed row, its dependent rows, evidence, the current script, and nearby scripts in the same category.
2. Apply the decision order above.
3. Add or update the script with the smallest compatible change.
4. Add `tests\test_<script-name>.py` using stdlib `unittest`. Mock UI, mouse, process, and filesystem boundaries; do not require a live application.
5. Test the new behavior and its expected failure. If an existing script changed, also test its previous default behavior.
6. Run the focused unit test:

```powershell
uv run python -m unittest tests.test_<script-name> -v
```

7. Run all unit tests to protect previous scripts:

```powershell
uv run python -m unittest discover -s tests -v
```

8. Document the script or new optional argument in `docs\scripts-reference.md`.
9. Update only the failed CSV row to use the implemented script and arguments.
10. Validate the CSV:

```powershell
uv run python scripts\csvfmt\csv_loader.py test_cases\<name>.csv
```

11. Return control to `test-case-repair`, which reruns the complete test and continues repairing later failures.

## Stop conditions

Return `BLOCKED` without guessing when the change requires a CSV schema extension, unavailable software, credentials, permissions, unknown user intent, or behavior that cannot be verified.

## Result returned to test-case-repair

Report the script path, unit-test path, failed CSV step changed, focused/full unit-test results, and CSV validation result. The repair skill records these details in the HTML repair report before continuing the run.
