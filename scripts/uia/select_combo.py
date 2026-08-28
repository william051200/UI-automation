"""Select an item in a UIA ComboBox by item text (exact / contains / regex).

Uses the UIA SelectionItem/ExpandCollapse patterns rather than mouse clicks, so it
works reliably for editable WPF combo boxes (e.g. the NuGet Version dropdown) whose
centre is an editable text box and would not open on a coordinate click.

Exit 0 on success (prints the selected item text), exit 1 if no item matches.
"""
import argparse, re, sys
from pywinauto import Application

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def matches(value, target, mode):
    if value is None:
        return False
    if mode == "exact":
        return value == target
    if mode == "contains":
        return target.lower() in value.lower()
    if mode == "regex":
        return re.search(target, value) is not None
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("hwnd", type=lambda s: int(s, 0))
    p.add_argument("--auto-id", dest="auto_id", default=None)
    p.add_argument("--name", default=None)
    p.add_argument("--item", required=True, help="item text to select")
    p.add_argument("--match", choices=["exact", "contains", "regex"], default="exact")
    p.add_argument("--timeout-ms", dest="timeout_ms", type=int, default=1000,
                    help="total time budget to keep retrying while items are still populating")
    p.add_argument("--poll-ms", dest="poll_ms", type=int, default=250,
                    help="pause between expand/read attempts")
    a = p.parse_args()

    app = Application(backend="uia").connect(handle=a.hwnd)
    win = app.window(handle=a.hwnd)

    kwargs = {"control_type": "ComboBox"}
    if a.auto_id is not None:
        kwargs["auto_id"] = a.auto_id
    if a.name is not None:
        kwargs["title"] = a.name
    combo = win.child_window(**kwargs)
    try:
        if not combo.exists(timeout=1.0):
            raise RuntimeError("not found")
    except Exception:
        print("ERROR: ComboBox not found", file=sys.stderr)
        sys.exit(1)

    # WPF combos are virtualized: items only materialize while the dropdown is open.
    # Expand, read the ListItem elements, select the match, then collapse so the UI
    # is not left open. Keep retrying (expand can be slow while the host page is
    # still populating, e.g. the New Project wizard enumerating templates) until
    # --timeout-ms elapses.
    import time

    def read_item_elems():
        try:
            items = list(combo.descendants(control_type="ListItem"))
            if items:
                return items
            return list(win.descendants(control_type="ListItem"))
        except Exception:
            return []

    elems = []
    deadline = time.monotonic() + (a.timeout_ms / 1000.0)
    while True:
        try:
            combo.expand()
        except Exception:
            pass
        time.sleep(a.poll_ms / 1000.0)
        elems = [e for e in read_item_elems() if (e.element_info.name or "")]
        if elems or time.monotonic() >= deadline:
            break

    target_elem = next(
        (e for e in elems if matches(e.element_info.name or "", a.item, a.match)), None
    )
    if target_elem is None:
        # Fallback: select by text on the (possibly collapsed) combo.
        try:
            texts = [t for t in combo.item_texts() if t]
        except Exception:
            texts = []
        target = next((t for t in texts if matches(t, a.item, a.match)), None)
        if target is None:
            print(f"no match for item {a.item!r} among {len(elems) or len(texts)} items",
                  file=sys.stderr)
            sys.exit(1)
        combo.select(target)
        try:
            combo.collapse()
        except Exception:
            pass
        print(target)
        return

    target = target_elem.element_info.name or ""
    try:
        target_elem.select()
    except Exception:
        combo.select(target)
    try:
        combo.collapse()
    except Exception:
        pass

    # Confirm the selection committed (NuGet reacts to the combo's selected value).
    for _ in range(8):
        try:
            if (combo.selected_text() or "") == target:
                break
        except Exception:
            pass
        time.sleep(0.1)
    print(target)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(2)
