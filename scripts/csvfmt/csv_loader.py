"""Load a combined CSV test case into a runnable spec dict (in memory).

`run_test.py` calls :func:`load` directly for ``.csv`` specs, so a CSV runs
straight from disk. The returned dict is the runnable spec structure
``run_test.py`` consumes.

Run a CSV test case via the runner:

    .\\run.ps1 test_cases\\powershell_echo_loop.csv -q

For debugging you can print the parsed spec as JSON:

    python scripts/csvfmt/csv_loader.py <file.csv>
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import csv_schema as S  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REQUIRED_CONFIG = {"name": None, "description": None, "artifacts": "screenshot_dir"}
JSON_LIST_COLUMNS = ("args", "screenshot_pass", "screenshot_fail")
NONNEGATIVE_INT_COLUMNS = ("wait_ms", "poll_total_ms", "poll_interval_ms")


def _split_sections(rows):
    """Return (config_rows, steps_rows) split on the section markers."""
    config_rows, steps_rows = [], []
    target = None
    for row in rows:
        if not row or all(S.blank(c) for c in row):
            continue
        if S.is_marker(row, S.CONFIG_MARKER):
            target = config_rows
            continue
        if S.is_marker(row, S.STEPS_MARKER):
            target = steps_rows
            continue
        if target is not None:
            target.append(row)
    return config_rows, steps_rows


def _require_header(rows, expected, section):
    if not rows:
        raise ValueError(f"{section} section is empty")
    header = [str(cell).strip() for cell in rows[0]]
    if header != expected:
        raise ValueError(
            f"{section} header must be: {','.join(expected)}")


def _parse_json(cell, column, row_number, expected_type):
    if S.blank(cell):
        return
    try:
        value = json.loads(cell)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"row {row_number}: {column} is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, expected_type):
        name = "list" if expected_type is list else "object"
        raise ValueError(f"row {row_number}: {column} must be a JSON {name}")
    if column == "capture":
        for dst, selector in value.items():
            if not str(dst).startswith("vars."):
                raise ValueError(
                    f"row {row_number}: capture destination must start with vars.")
            if not isinstance(selector, str) or not (
                    selector.startswith("$.cols[") or
                    selector.startswith("$.rows[")):
                raise ValueError(
                    f"row {row_number}: invalid capture selector {selector!r}")


def _validate_script(script, row_number):
    normalized = str(script).replace("/", os.sep).replace("\\", os.sep)
    if os.path.isabs(normalized) or normalized.split(os.sep)[0] != "scripts":
        raise ValueError(
            f"row {row_number}: script must be a repository-relative path under scripts")
    path = os.path.abspath(os.path.join(REPO_ROOT, normalized))
    scripts_root = os.path.join(REPO_ROOT, "scripts")
    if os.path.commonpath((path, scripts_root)) != scripts_root:
        raise ValueError(f"row {row_number}: script escapes the scripts directory")
    if not os.path.isfile(path):
        raise ValueError(f"row {row_number}: script does not exist: {script}")


def _validate_config(config_rows):
    _require_header(config_rows, S.CONFIG_COLUMNS, S.CONFIG_MARKER)
    found = {}
    for row_number, raw in enumerate(config_rows[1:], start=3):
        section = str(_cell(raw, 0) or "").strip()
        key = str(_cell(raw, 1) or "").strip()
        value = _cell(raw, 2)
        if section not in REQUIRED_CONFIG:
            raise ValueError(f"row {row_number}: unsupported config section {section!r}")
        expected_key = REQUIRED_CONFIG[section]
        if key != (expected_key or ""):
            raise ValueError(
                f"row {row_number}: {section} key must be {expected_key or 'blank'}")
        if section in found:
            raise ValueError(f"row {row_number}: duplicate config section {section!r}")
        if S.blank(value):
            raise ValueError(f"row {row_number}: {section} value is required")
        found[section] = value
    missing = set(REQUIRED_CONFIG) - set(found)
    if missing:
        raise ValueError(f"missing config section(s): {', '.join(sorted(missing))}")


def _validate_steps(steps_rows):
    _require_header(steps_rows, S.STEPS_COLUMNS, S.STEPS_MARKER)
    header = S.STEPS_COLUMNS
    expected_step = 1
    in_loop = False
    loop_has_body = False

    for row_number, raw in enumerate(steps_rows[1:], start=2):
        cells = {header[i]: _cell(raw, i) for i in range(len(header))}
        marker = str(_cell(raw, 0) or "").strip().upper()
        if marker == S.LOOP_END_MARKER:
            if not in_loop:
                raise ValueError(f"steps row {row_number}: unmatched # END LOOP")
            if not loop_has_body:
                raise ValueError(f"steps row {row_number}: loop body is empty")
            in_loop = False
            continue

        is_loop = marker == S.LOOP_START_MARKER
        if is_loop:
            if in_loop:
                raise ValueError(f"steps row {row_number}: nested loops are not supported")
            in_loop = True
            loop_has_body = False
        elif in_loop:
            loop_has_body = True

        if S.blank(cells["script"]):
            raise ValueError(f"steps row {row_number}: script is required")
        if S.blank(cells["Trigger"]):
            raise ValueError(f"steps row {row_number}: Trigger is required")
        if str(cells["step no"] or "").strip() != str(expected_step):
            raise ValueError(
                f"steps row {row_number}: step no must be {expected_step}")
        expected_step += 1
        _validate_script(cells["script"], row_number)

        for column in JSON_LIST_COLUMNS:
            _parse_json(cells[column], column, row_number, list)
        _parse_json(cells["capture"], "capture", row_number, dict)

        for column in NONNEGATIVE_INT_COLUMNS:
            if not S.blank(cells[column]):
                value = str(cells[column]).strip()
                if not value.isdigit():
                    raise ValueError(
                        f"steps row {row_number}: {column} must be a non-negative integer")
        if not S.blank(cells["expect_exit"]):
            try:
                int(cells["expect_exit"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"steps row {row_number}: expect_exit must be an integer") from exc
        if not S.blank(cells["max_iter"]):
            value = str(cells["max_iter"]).strip()
            if not is_loop:
                raise ValueError(
                    f"steps row {row_number}: max_iter is only valid on # LOOP rows")
            if not value.isdigit() or int(value) < 1:
                raise ValueError(
                    f"steps row {row_number}: max_iter must be a positive integer")

    if in_loop:
        raise ValueError("missing # END LOOP")
    if expected_step == 1:
        raise ValueError("test case has no executable steps")


def validate(csv_path):
    """Validate a newly authored CSV against the canonical repository contract."""
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    markers = [str(row[0]).strip().upper() for row in rows if row]
    if markers.count(S.CONFIG_MARKER) != 1 or markers.count(S.STEPS_MARKER) != 1:
        raise ValueError("CSV must contain exactly one # CONFIG and one # STEPS marker")
    if markers.index(S.CONFIG_MARKER) > markers.index(S.STEPS_MARKER):
        raise ValueError("# CONFIG must appear before # STEPS")
    config_rows, steps_rows = _split_sections(rows)
    _validate_config(config_rows)
    _validate_steps(steps_rows)


def _cell(row, i):
    return row[i] if i < len(row) else None


def _int(value):
    s = str(value).strip()
    return int(s) if s.lstrip("-").isdigit() else value


def _infer_type(cells, script):
    """Type is no longer a column; derive it from the row.

    - a screenshot pattern  -> screenshot
    - an expected_contains   -> assert_console_contains
    - otherwise the script's basename (key, click, type_text, find_window, ...)
    """
    if not S.blank(cells.get("screenshot_pass")) or \
            not S.blank(cells.get("screenshot_fail")):
        return "screenshot"
    if not S.blank(cells.get("expected_contains")):
        return "assert_console_contains"
    if script:
        return os.path.splitext(os.path.basename(script))[0]
    return "run"


def _row_to_step(cells, step_id, screenshot_dir):
    def g(name):
        return cells.get(name)

    script = None if S.blank(g("script")) else g("script")
    step = {"id": step_id, "type": _infer_type(cells, script)}
    if not S.blank(g("Trigger")):
        step["description"] = g("Trigger")
    if script is not None:
        step["script"] = script

    if not S.blank(g("args")):
        step["args"] = S.loads_list(g("args"))

    if not S.blank(g("wait_ms")):
        step["wait_after"] = _int(g("wait_ms"))
    if not S.blank(g("capture")):
        step["capture"] = S.loads_obj(g("capture"))
    if not S.blank(g("expect_exit")):
        step["expect_exit"] = int(g("expect_exit"))
    if not S.blank(g("expected_contains")):
        step["expected_contains_expr"] = g("expected_contains")
    if not S.blank(g("poll_total_ms")):
        step["poll_total_ms"] = _int(g("poll_total_ms"))
    if not S.blank(g("poll_interval_ms")):
        step["poll_interval_ms"] = _int(g("poll_interval_ms"))
    if not S.blank(g("screenshot_pass")):
        step["args_expr_on_pass"] = _shot_paths(g("screenshot_pass"), screenshot_dir)
    if not S.blank(g("screenshot_fail")):
        step["args_expr_on_fail"] = _shot_paths(g("screenshot_fail"), screenshot_dir)
    return step


def _shot_paths(cell, screenshot_dir):
    """Prepend the configured screenshot dir to each filename pattern."""
    names = S.loads_list(cell)
    if not screenshot_dir:
        return names
    return [f"{screenshot_dir}/{n}" for n in names]


def _build_while(cells, loop_id, body):
    """Build a `while` step from a `# LOOP` condition row plus its body steps."""
    def g(name):
        return cells.get(name)

    condition = {"script": g("script")}
    if not S.blank(g("args")):
        condition["args"] = S.loads_list(g("args"))
    if not S.blank(g("capture")):
        condition["capture"] = S.loads_obj(g("capture"))
    if not S.blank(g("expect_exit")):
        condition["expect_exit"] = int(g("expect_exit"))

    step = {"id": loop_id, "type": "while", "condition": condition, "body": body}
    if not S.blank(g("max_iter")):
        step["max_iterations"] = int(g("max_iter"))
    return step


def _build_steps(steps_rows, screenshot_dir):
    """Each row with a `script` is one step (flat list, in order).

    `# LOOP` / `# END LOOP` marker rows (in the `No` column) delimit a
    conditional while-loop: the `# LOOP` row carries the loop condition and the
    rows up to the *matching* `# END LOOP` form the loop body (a nested step
    list). `# LOOP` blocks may themselves be nested (e.g. a version-discovery
    loop wrapping a scenario that already contains its own inner loops) --
    nesting depth is tracked so the correct `# END LOOP` is matched.

    The readable `No` / `Main step` / `Expected` columns are authoring
    annotations and are ignored here. Step ids are auto-generated.
    """
    if not steps_rows:
        return []
    header = [str(h).strip() for h in steps_rows[0]]

    def cells_for(raw):
        return {header[i]: _cell(raw, i) for i in range(len(header))}

    def marker(raw):
        return raw[0].strip().upper() if raw and raw[0] else ""

    body_rows = steps_rows[1:]
    counter = [0]  # mutable step-id counter shared across recursive calls

    def parse(start, end):
        """Parse body_rows[start:end], returning (steps, ). Handles nesting."""
        steps = []
        idx = start
        while idx < end:
            raw = body_rows[idx]
            if marker(raw) == S.LOOP_START_MARKER:
                counter[0] += 1
                loop_id = f"step_{counter[0]}"
                cond_cells = cells_for(raw)
                # Find the matching `# END LOOP`, accounting for nested loops.
                depth = 1
                scan = idx + 1
                while scan < end and depth > 0:
                    mk = marker(body_rows[scan])
                    if mk == S.LOOP_START_MARKER:
                        depth += 1
                    elif mk == S.LOOP_END_MARKER:
                        depth -= 1
                        if depth == 0:
                            break
                    scan += 1
                inner = parse(idx + 1, scan)
                steps.append(_build_while(cond_cells, loop_id, inner))
                idx = scan + 1  # skip past the matching `# END LOOP` row
                continue
            cells = cells_for(raw)
            if not S.blank(cells.get("script")):
                counter[0] += 1
                steps.append(_row_to_step(cells, f"step_{counter[0]}", screenshot_dir))
            idx += 1
        return steps

    return parse(0, len(body_rows))


def _coerce(value):
    """CSV stores everything as text; restore ints for numeric cells."""
    if isinstance(value, str):
        s = value.strip()
        if s and (s.isdigit() or (s[0] == "-" and s[1:].isdigit())):
            return int(s)
    return value


def _build_config(config_rows):
    spec = {}
    inputs = {}
    expected = []
    # skip the Section/Key/Value header row if present
    start = 1 if config_rows and config_rows[0] and \
        config_rows[0][0].strip().lower() == "section" else 0
    for raw in config_rows[start:]:
        section = raw[0] if len(raw) > 0 else None
        key = raw[1] if len(raw) > 1 else None
        value = raw[2] if len(raw) > 2 else None
        if S.blank(section):
            continue
        section = section.strip()
        if section == "name":
            spec["name"] = value
        elif section == "description":
            spec["description"] = value
        elif section == "inputs":
            inputs.setdefault(key, []).append(value)
        elif section in S.CONFIG_MAP_SECTIONS:
            spec.setdefault(section, {})[key] = _coerce(value)
        elif section == "expected_results":
            expected.append(value)
    if inputs:
        spec["inputs"] = {
            k: (v if len(v) > 1 else v[0]) for k, v in inputs.items()
        }
    if expected:
        spec["expected_results"] = expected
    return spec


def load(csv_path, strict=False):
    """Parse a standard-format CSV test case into a runnable spec dict."""
    if strict:
        validate(csv_path)
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    config_rows, steps_rows = _split_sections(rows)
    spec = _build_config(config_rows)
    spec["steps"] = _build_steps(steps_rows, "{artifacts.screenshot_dir}")
    ordered = {k: spec[k] for k in S.SPEC_KEY_ORDER if k in spec}
    for k, v in spec.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


# Backwards-compatible alias.
convert = load


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv")
    a = ap.parse_args()
    spec = load(a.csv, strict=True)
    json.dump(spec, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
