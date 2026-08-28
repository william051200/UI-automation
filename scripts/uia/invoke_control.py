"""Invoke one UIA control selected by name, AutomationId, and control type."""
import argparse
import re
import sys

from pywinauto import Application


def matches(value, target, mode):
    if target is None:
        return True
    value = value or ""
    if mode == "exact":
        return value == target
    if mode == "contains":
        return target.lower() in value.lower()
    return re.search(target, value) is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hwnd", type=lambda value: int(value, 0))
    parser.add_argument("--name")
    parser.add_argument("--auto-id", dest="auto_id")
    parser.add_argument("--control-type", dest="control_type")
    parser.add_argument("--match", choices=["exact", "contains", "regex"], default="exact")
    args = parser.parse_args()

    app = Application(backend="uia").connect(handle=args.hwnd)
    window = app.window(handle=args.hwnd)
    for control in window.descendants():
        info = control.element_info
        if (matches(info.name, args.name, args.match)
                and matches(info.automation_id, args.auto_id, args.match)
                and matches(info.control_type, args.control_type, args.match)):
            try:
                control.invoke()
            except Exception:
                control.click_input()
            print(f"invoked\t{info.name}\t{info.automation_id}\t{info.control_type}")
            return

    print("no match", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
