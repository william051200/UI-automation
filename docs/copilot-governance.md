# Copilot governance

Each rule should have one owner. Other files should link to that owner instead of copying it.

| Owner | Responsibility |
|---|---|
| `scripts/csvfmt/csv_schema.py` | Executable CSV markers and column order |
| `scripts/csvfmt/csv_loader.py` | Strict structural validation and CSV-to-runner conversion |
| `test_cases/_template.csv` | Canonical starter example |
| `AGENTS.md` | Mandatory repository-wide authoring behavior |
| `.github/copilot-instructions.md` | Route Copilot to the correct rules and skills |
| `.github/skills/*/SKILL.md` | Procedures for one specific task |
| `docs/csv-test-format.md` | Human-readable CSV syntax |
| `docs/copilot-workflow.md` | Human-readable authoring workflow |
| `README.md` | Installation, basic commands, and short entry-point prompts |

## Conflict rule

Executable behavior must match `csv_schema.py` and `csv_loader.py`. Authoring behavior must match `AGENTS.md`. Fix stale examples or explanations instead of adding another precedence list.

## Change checklist

- Schema changes update `csv_schema.py`, strict loader validation, tests, the template, and CSV format documentation.
- Authoring-rule changes update `AGENTS.md`; skills and docs should reference it.
- Skill changes remain limited to one workflow.
- Generated CSV must pass `uv run python scripts\csvfmt\csv_loader.py <file.csv>`.
- Live execution results must be reported separately from structural validation.
