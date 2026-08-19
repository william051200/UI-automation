"""Shared schema for the CSV test-case loader.

A test case is a single combined CSV with two marker-delimited sections:

    # CONFIG
    Section,Key,Value
    ...

    # STEPS
    No,Main step,Trigger,script,...
    ...

This module keeps the section markers and column layout in one place.
"""
import json

CONFIG_MARKER = "# CONFIG"
STEPS_MARKER = "# STEPS"

# Loop-block markers, used *inside* the # STEPS section to delimit a conditional
# while-loop. The `# LOOP` row carries the loop condition (its `script` / `args`
# / `capture` / `expect_exit` / `max_iter` columns); the rows up to the matching
# `# END LOOP` row form the loop body. See docs/csv-test-format.md.
LOOP_START_MARKER = "# LOOP"
LOOP_END_MARKER = "# END LOOP"

# Steps section columns, in order. Readable columns first (authoring-facing),
# then the technical columns needed to reconstruct a runnable spec.
# `id` and `type` are NOT columns: the converter auto-generates the id and
# infers the type. `args` is always rendered, so there is no args_mode.
STEPS_COLUMNS = [
    "No",                 # phase number (readability only; ignored on import)
    "step no",            # global sequential step counter (readability only; ignored on import)
    "Main step",          # phase name, first row of each phase (readability only)
    "Trigger",            # human-readable action == step description
    "script",
    "args",               # JSON list (rendered at runtime)
    "wait_ms",            # literal milliseconds -> wait_after
    "capture",            # JSON object (capture mapping)
    "expect_exit",
    "expected_contains",  # assert_console_contains -> expected_contains_expr
    "poll_total_ms",      # literal milliseconds
    "poll_interval_ms",   # literal milliseconds
    "screenshot_pass",    # screenshot filename pattern -> args_expr_on_pass (JSON list)
    "screenshot_fail",    # screenshot filename pattern -> args_expr_on_fail (JSON list)
    "max_iter",           # # LOOP condition row only: max while-loop iterations (safety cap)
    "Expected",           # expected-result note (readability only; ignored on import)
]

# Config section columns.
CONFIG_COLUMNS = ["Section", "Key", "Value"]

# Top-level spec key order preserved in the loaded spec dict.
SPEC_KEY_ORDER = [
    "name", "description", "inputs", "artifacts", "timing", "retry",
    "steps", "expected_results",
]

# Config sections that are flat key/value maps.
CONFIG_MAP_SECTIONS = ["artifacts", "timing", "retry"]


def dumps(value):
    """Serialize a list/dict cell value to compact JSON; None -> ''."""
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def loads_list(cell):
    """Parse a JSON list cell back to a Python list; blank -> None."""
    if blank(cell):
        return None
    return json.loads(cell)


def loads_obj(cell):
    """Parse a JSON object cell back to a Python dict; blank -> None."""
    if blank(cell):
        return None
    return json.loads(cell)


def blank(cell):
    """True when a cell is None or whitespace-only."""
    return cell is None or str(cell).strip() == ""


def is_marker(row, marker):
    """True when a CSV row is the given section marker line."""
    return bool(row) and row[0].strip().upper() == marker.upper()
