# UI Automation Repository Instructions

Follow `AGENTS.md` for repository-wide authoring rules.

For CSV conversion, use `.github/skills/csv-test-formatter/SKILL.md`.

For failing CSV repair, use `.github/skills/test-case-repair/SKILL.md`.

When repair evidence proves that existing scripts cannot handle an observed behavior, use `.github/skills/test-script-developer/SKILL.md`.

The executable CSV contract is `scripts/csvfmt/csv_schema.py`. The canonical starter example is `test_cases/_template.csv`. Validate generated CSV with:

```powershell
uv run python scripts\csvfmt\csv_loader.py test_cases\<name>.csv
```
