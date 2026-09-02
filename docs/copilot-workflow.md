# Copilot authoring workflow

Testers describe what the UI test should do. Copilot converts that intent into the repository's executable CSV format.

## Standard conversion prompt

Save the raw CSV under `test_cases\drafts\`, then replace `<name>` with the file's base name:

```text
Use the csv-test-formatter skill.
Source file: test_cases\drafts\<name>.csv
```

Copilot infers the output as `test_cases\<name>.csv`. To use another destination, add:

```text
Output file: <OUTPUT_FILE>
```

## Convert a rough test case

1. Save the rough CSV as `test_cases\drafts\<name>.csv`.
2. Ask Copilot to use the `csv-test-formatter` skill and provide the source path.
3. Copilot automatically writes `test_cases\<name>.csv` using the same base filename. You may provide another output path when needed.
4. Copilot maps each action to an existing script and writes the canonical CSV.
5. Copilot runs strict structural validation with:

```powershell
uv run python scripts\csvfmt\csv_loader.py test_cases\<name>.csv
```

6. Validation confirms the format, required fields, step numbering, script paths, JSON fields, numeric values, and loops. It does not prove that live UI selectors work.

## Run the generated test

```powershell
.\run.ps1 test_cases\<name>.csv -q
```

The runner executes each script, substitutes captured variables, polls assertions, and writes requested screenshots.

## Repair a failing test

Ask Copilot to use the `test-case-repair` skill. Copilot runs the test, repairs one evidence-backed failure at a time, validates the CSV after each edit, reruns the complete test, and writes an HTML repair report.

When evidence proves that existing scripts cannot handle the observed behavior, repair automatically invokes `test-script-developer`. That skill adds the smallest backward-compatible script capability, its unit test and documentation, updates only the failed CSV row, and returns control to the same repair run.

The repair stops with `BLOCKED` instead of guessing when it needs unavailable software, credentials, permissions, unknown user intent, a schema change, or behavior that cannot be verified.

## Responsibility

`AGENTS.md` contains mandatory authoring rules. `docs/csv-test-format.md` explains CSV syntax. The skills contain the conversion and repair procedures.
