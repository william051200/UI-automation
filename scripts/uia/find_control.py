"""Find UIA controls inside a window subtree by name / auto_id / control_type / class."""
import argparse, re, sys, time
from pywinauto import Application

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def matches(value, target, mode):
    if target is None:
        return True
    if value is None:
        return False
    if mode == "exact":
        return value == target
    if mode == "contains":
        return target.lower() in value.lower()
    if mode == "regex":
        return re.search(target, value) is not None
    return False

def positive_int(s):
    value = int(s, 0)
    if value < 1:
        raise argparse.ArgumentTypeError("must be a 1-based integer")
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("hwnd", type=lambda s: int(s, 0))
    p.add_argument("--name", default=None)
    p.add_argument("--name-exclude", dest="name_exclude", default=None,
                   help="skip controls whose name contains this substring (case-insensitive). "
                        "Useful to ignore transient placeholders such as "
                        "NuGet.PackageManagement.UI.LoadingStatusIndicator.")
    p.add_argument("--auto-id", dest="auto_id", default=None)
    p.add_argument("--control-type", dest="control_type", default=None)
    p.add_argument("--class", dest="cls", default=None)
    p.add_argument("--ancestor-name", dest="ancestor_name", default=None,
                   help="keep only controls with an ancestor whose name matches using --match")
    p.add_argument("--match", choices=["exact", "contains", "regex"], default="exact")
    p.add_argument("--backend", choices=["uia", "win32"], default="uia")
    p.add_argument("--parent-hwnd", dest="parent_hwnd", type=lambda s: int(s, 0), default=None,
                   help="scope search to descendants of this hwnd within the connected app")
    output_group = p.add_mutually_exclusive_group()
    output_group.add_argument("--all", action="store_true", help="print all matches, not just first")
    output_group.add_argument("--nth", type=positive_int,
                              help="print only the Nth match after filtering (1-based)")
    p.add_argument("--name-fallback", dest="name_fallback", action="store_true",
                   help="if filtering by auto_id yields zero matches, retry without the auto_id filter "
                        "(keeping --name / --control-type / --class). Requires --name to be set.")
    p.add_argument("--visible", action="store_true",
                   help="skip zero-area controls (offscreen/collapsed items with an empty "
                        "rectangle), keeping only controls that are actually rendered/clickable.")
    p.add_argument("--scroll-into-view", dest="scroll_into_view", action="store_true",
                   help="ask the matching UIA item to scroll into view before reading its rectangle")
    p.add_argument("--timeout-ms", dest="timeout_ms", type=int, default=0,
                   help="if > 0, re-scan until a match is found or this many milliseconds elapse "
                        "(handles controls that render slightly after a click/type). Default 0 = "
                        "single one-shot scan (unchanged behavior; negative assertions stay fast).")
    p.add_argument("--poll-ms", dest="poll_ms", type=int, default=300,
                   help="poll interval in ms when --timeout-ms > 0 (default 300).")
    a = p.parse_args()

    if a.name_fallback and not a.name:
        print("ERROR: --name-fallback requires --name", file=sys.stderr); sys.exit(2)

    app = Application(backend=a.backend).connect(handle=a.hwnd)
    win = app.window(handle=a.hwnd)
    scope = win
    if a.parent_hwnd is not None:
        scope = app.window(handle=a.parent_hwnd, top_level_only=False)
        try:
            if not scope.exists(timeout=0.5):
                raise RuntimeError("not found")
        except Exception:
            print(f"ERROR: parent hwnd {a.parent_hwnd} could not be resolved in app tree", file=sys.stderr)
            sys.exit(1)

    def scan(filter_auto_id):
        results = []
        for c in scope.descendants():
            try:
                if a.backend == "uia":
                    info = c.element_info
                    name = info.name or ""
                    auto_id = info.automation_id or ""
                    ctype = info.control_type or ""
                    cls = info.class_name or ""
                else:
                    name = c.window_text() or ""
                    auto_id = ""
                    ctype = c.friendly_class_name() or ""
                    cls = c.class_name() or ""
                if not (matches(name, a.name, a.match)
                        and matches(auto_id, filter_auto_id, a.match)
                        and matches(ctype, a.control_type, a.match)
                        and matches(cls, a.cls, a.match)):
                    continue
                if a.ancestor_name is not None:
                    ancestor = c.parent()
                    ancestor_found = False
                    while ancestor is not None:
                        if matches(ancestor.element_info.name or "", a.ancestor_name, a.match):
                            ancestor_found = True
                            break
                        ancestor = ancestor.parent()
                    if not ancestor_found:
                        continue
                if a.name_exclude and a.name_exclude.lower() in (name or "").lower():
                    continue
                if a.scroll_into_view:
                    c.iface_scroll_item.ScrollIntoView()
                    time.sleep(0.1)
                r = c.rectangle()
                if a.visible and (r.right <= r.left or r.bottom <= r.top):
                    continue
                cx = (r.left + r.right) // 2
                cy = (r.top + r.bottom) // 2
                results.append((name, auto_id, ctype, r.left, r.top, r.right, r.bottom, cx, cy))
            except Exception:
                continue
        return results

    def select_rows():
        found = scan(a.auto_id)
        if not found and a.name_fallback and a.auto_id:
            print(f"NOTE: no match for auto_id={a.auto_id!r}; falling back to name-only filter", file=sys.stderr)
            found = scan(None)

        # descendants() can vary by backend/run; sort by geometry and identity for stable candidate lists.
        found.sort(key=lambda f: (f[4], f[3], f[2], f[0], f[1]))

        if a.nth is not None:
            if a.nth > len(found):
                return []
            return found[a.nth - 1:a.nth]
        return found if a.all else found[:1]

    deadline = time.time() + a.timeout_ms / 1000.0
    interval = max(a.poll_ms, 0) / 1000.0
    while True:
        rows = select_rows()
        if rows or a.timeout_ms <= 0 or time.time() >= deadline:
            break
        time.sleep(interval)

    if not rows:
        print("no match", file=sys.stderr); sys.exit(1)
    print("name\tauto_id\tcontrol_type\tleft\ttop\tright\tbottom\tcenter_x\tcenter_y")
    for f in rows:
        print("\t".join(str(x) for x in f))

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(2)
