"""Expand a cascading toolbar menu (e.g. the Debug Target split-button) and read
or verify which leaf item in a named submenu is currently checked.

Some VS toolbar controls (the "Debug Target" split-button showing "Windows
Machine") expose a checked-item submenu (e.g. "Framework (net10.0-windows...)")
whose leaf MenuItems are only realised in the UIA tree while the submenu is
open. No existing script can open such a nested menu and read the checked
leaf, so this one is scoped narrowly to that behaviour:

  1. Find --root-name (control-type --root-type, default SplitButton) under
     <hwnd> and expand it (ExpandCollapsePattern).
  2. Find the submenu MenuItem whose name matches --submenu (default
     "contains") and expand it too, revealing its leaf MenuItems.
  3. Read each leaf's checked state via the legacy MSAA STATE_SYSTEM_CHECKED
     bit (0x10) -- WPF menu items expose exclusive "checked" selection this
     way rather than through the UIA SelectionItem pattern.

Modes:
  list            Print each leaf item, tab-separated with its checked flag
                  (1 or 0), one per line.
  verify-checked  Exit 0 iff exactly one leaf is checked and its name equals
                  --expect; otherwise print the actual checked name (or
                  "none") to stderr and exit 1.

By default the menu is closed (Escape) before exiting so the UI is left in a
clean state; pass --keep-open to skip that.

Exit codes: 0 success, 1 not found / verification mismatch, 2 usage error.
"""
import argparse
import re
import sys
import time

from pywinauto import Application
from pywinauto.keyboard import send_keys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

STATE_SYSTEM_CHECKED = 0x10


def matches(value, target, mode):
    value = value or ""
    if mode == "exact":
        return value == target
    if mode == "contains":
        return target.lower() in value.lower()
    return re.search(target, value) is not None


def is_checked(elem):
    try:
        state = elem.legacy_properties().get("State", 0)
        return bool(state & STATE_SYSTEM_CHECKED)
    except Exception:
        return False


def find_root(win, name, control_type, timeout_ms):
    deadline = time.monotonic() + timeout_ms / 1000.0
    ctrl = win.child_window(title=name, control_type=control_type)
    while True:
        try:
            if ctrl.exists(timeout=0.3):
                return ctrl
        except Exception:
            pass
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.2)


def find_submenu(win, name, match, timeout_ms):
    deadline = time.monotonic() + timeout_ms / 1000.0
    while True:
        for m in win.descendants(control_type="MenuItem"):
            if matches(m.element_info.name, name, match):
                return m
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.2)


def collect_leaves(win, submenu_elem, timeout_ms):
    """Leaf items materialise as siblings in win's tree once the submenu is
    open, not always as descendants of submenu_elem itself (WPF popups can
    render outside the logical subtree pywinauto walks)."""
    sub_rect = submenu_elem.rectangle()
    deadline = time.monotonic() + timeout_ms / 1000.0
    while True:
        leaves = []
        for m in win.descendants(control_type="MenuItem"):
            if m == submenu_elem:
                continue
            try:
                r = m.rectangle()
            except Exception:
                continue
            # Leaf items of an expanded submenu render to the right of it.
            if r.left >= sub_rect.right and abs(r.top - sub_rect.top) < 400:
                name = m.element_info.name or ""
                if name:
                    leaves.append((name, m))
        if leaves or time.monotonic() >= deadline:
            return leaves
        time.sleep(0.2)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("hwnd", type=lambda s: int(s, 0))
    p.add_argument("--root-name", dest="root_name", required=True)
    p.add_argument("--root-type", dest="root_type", default="SplitButton")
    p.add_argument("--submenu", required=True,
                   help="submenu MenuItem name to match (e.g. 'Framework')")
    p.add_argument("--match", choices=["exact", "contains", "regex"], default="contains",
                   help="match mode for --submenu (default: contains)")
    p.add_argument("--timeout-ms", dest="timeout_ms", type=int, default=5000)
    p.add_argument("--keep-open", dest="keep_open", action="store_true",
                   help="leave the menu open instead of pressing Escape to close it")

    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("list")
    vc = sub.add_parser("verify-checked")
    vc.add_argument("--expect", required=True, help="expected checked leaf item name")

    a = p.parse_args()

    app = Application(backend="uia").connect(handle=a.hwnd)
    win = app.window(handle=a.hwnd)

    root = find_root(win, a.root_name, a.root_type, a.timeout_ms)
    if root is None:
        print(f"ERROR: root control not found (name={a.root_name!r} type={a.root_type!r})",
              file=sys.stderr)
        sys.exit(1)
    try:
        root.expand()
    except Exception as e:
        print(f"ERROR: failed to expand root control: {e}", file=sys.stderr)
        sys.exit(1)

    submenu = find_submenu(win, a.submenu, a.match, a.timeout_ms)
    if submenu is None:
        print(f"ERROR: submenu not found (name~={a.submenu!r})", file=sys.stderr)
        if not a.keep_open:
            try:
                send_keys("{ESC}{ESC}")
            except Exception:
                pass
        sys.exit(1)
    try:
        submenu.expand()
    except Exception:
        try:
            submenu.click_input()
        except Exception:
            pass

    leaves = collect_leaves(win, submenu, a.timeout_ms)

    result = 0
    if a.mode == "list":
        if not leaves:
            print("no leaf items found", file=sys.stderr)
            result = 1
        else:
            for name, elem in leaves:
                print(f"{name}\t{1 if is_checked(elem) else 0}")
    else:  # verify-checked
        checked = [name for name, elem in leaves if is_checked(elem)]
        if len(checked) != 1 or checked[0] != a.expect:
            actual = checked[0] if len(checked) == 1 else ("none" if not checked else "multiple")
            print(f"ERROR: expected checked item {a.expect!r}, actual {actual!r} "
                  f"(candidates: {[n for n, _ in leaves]})", file=sys.stderr)
            result = 1
        else:
            print(a.expect)

    if not a.keep_open:
        try:
            send_keys("{ESC}{ESC}")
        except Exception:
            pass

    sys.exit(result)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(2)
