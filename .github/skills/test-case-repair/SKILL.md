---
name: test-case-repair
description: Run a ui-auto CSV test case, repair each failing step with the smallest safe CSV change, rerun until it passes or is blocked, and write an HTML repair report matching result/repair-report-example.html.
---

# Test case repair

Repair one existing CSV test case automatically. Follow `AGENTS.md` for authoring rules and use `scripts/csvfmt/csv_loader.py` for strict validation.

## Input and output

- Required input: the CSV path.
- Default report path: `result\<csv-name>.html`.
- Create the `result\` directory when it does not exist.
- A user-provided report path overrides the default.
- If no CSV path is provided, ask for it instead of guessing.

## Workflow

1. Run the complete test and record its elapsed time:

```powershell
.\run.ps1 test_cases\<name>.csv -q
```

2. If it passes, create an empty repair report with final result `PASS`.
3. If it fails, record the attempt, failed step, failure, and exact fix.
4. Inspect the failed row, dependent rows, stderr, and relevant artifacts.
5. If an existing script can handle the behavior, make the smallest deterministic CSV change supported by observed evidence.
6. If evidence proves that existing scripts cannot handle the observed behavior, automatically invoke `test-script-developer`. It adds the smallest backward-compatible script capability, its unit test, documentation, and the failed-row CSV change, then returns control to this repair run.
7. Do not weaken assertions, change tester intent, or guess unknown selectors.
8. Validate the edited CSV:

```powershell
uv run python scripts\csvfmt\csv_loader.py test_cases\<name>.csv
```

9. Rerun the complete test.
10. Repeat while failures provide evidence for a safe repair.
11. Stop with `BLOCKED` when progress requires unavailable software, credentials, permissions, user intent, a schema change, or a script behavior that cannot be verified.
12. Always write the HTML report.

## Report

Use `result/repair-report-example.html` as the format. Write standalone UTF-8 HTML and escape inserted text.

The report must show:

- A summary with the test case path, final result (`PASS` or `BLOCKED`), total run attempts, total run time, repairs applied, and final verification outcome.
- One repair-history row per failed attempt with the attempt number, failed step id and `Trigger`, observed failure, supporting evidence, exact CSV change, and the next run's outcome.
- The single blocking reason when the final result is `BLOCKED`.
- Links to relevant screenshots or other artifacts when they exist. Use relative paths so the report remains portable.

Do not add a repair-history row for the final successful run.

`Total run time` is the sum of the elapsed time of every `run.ps1` attempt. Do not include time spent inspecting failures or editing the CSV. Format it as `Hh Mm Ss`, omitting zero-value units.

## Final response

State the final result, repaired CSV path, and report path. If blocked, state the single blocking reason.
