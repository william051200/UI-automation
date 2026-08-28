"""UIA helper for the Visual Studio ``Framework`` ComboBox on the Additional Information page.

The rough test case for ``3-e2esanity-template-test`` needs a handful of
operations against that combo that no existing script covers:

  list <hwnd>                Expand the combo, print each item's name on its
                             own stdout line, then collapse it.

  latest <hwnd>              Expand, read items, pick the highest ``.NET
                             <major>.<minor>`` label (ties broken by preferring
                             ``(Long Term Support)`` over ``(Standard Term
                             Support)``, and ``Preview`` only when
                             ``--prefer-preview`` is set). Prints the winning
                             label on stdout.

  select-latest <hwnd>       Same as ``latest``, but also selects it and prints
                             the selected label.  Honors ``--prefer-preview``.

  verify-default-is-latest <hwnd>
                             Read the combo's currently-selected label and the
                             computed latest label. Exit 0 iff they match.
                             With ``--kill-pid <pid>`` a mismatch also kills
                             that process (used to close Visual Studio when
                             the sanity check fails).

  verify-default-equals <hwnd> --expected "<label>"
                             Exit 0 iff the combo's current default label
                             matches ``--expected`` exactly. Same
                             ``--kill-pid`` semantics as above.

All modes take the same combo selectors:

  --auto-id X   optional AutomationId
  --name Y      optional Name (default: ``Framework``)

Combo lookup is scoped to descendants of the given ``<hwnd>`` and uses the
UIA ExpandCollapse/Selection patterns, matching ``select_combo.py``'s approach.

Version parsing is deliberately conservative: only labels shaped like
``.NET <int>.<int>`` (optionally followed by any parenthesised suffix) are
considered candidates. Anything else is ignored.

Exit codes:
  0 success (mode-specific meaning; see above)
  1 verification failed / no matching item found
  2 usage error or unexpected failure
"""
import argparse
import os
import re
import signal
import subprocess
import sys
import time

from pywinauto import Application

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


DOTNET_RE = re.compile(r"^\s*\.NET\s+(\d+)\.(\d+)\b(.*)$")


def kill_pid(pid):
    if not pid:
        return
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid), "/T"],
                       capture_output=True, text=True)
    except Exception:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except Exception:
            pass


def connect_combo(hwnd, auto_id, name):
    app = Application(backend="uia").connect(handle=hwnd)
    win = app.window(handle=hwnd)
    kwargs = {"control_type": "ComboBox"}
    if auto_id:
        kwargs["auto_id"] = auto_id
    if name:
        import re as _re
        kwargs["title_re"] = f".*{_re.escape(name)}.*"
    combo = win.child_window(**kwargs)
    if not combo.exists(timeout=5.0):
        raise RuntimeError(f"ComboBox not found (auto_id={auto_id!r} name={name!r})")
    return combo


def read_selected(combo):
    for _ in range(4):
        try:
            v = combo.selected_text()
            if v:
                return v.strip()
        except Exception:
            pass
        try:
            v = combo.window_text()
            if v:
                return v.strip()
        except Exception:
            pass
        time.sleep(0.15)
    return ""


def list_items(combo):
    items = []
    for attempt in range(2):
        try:
            combo.expand()
        except Exception:
            pass
        time.sleep(0.4)
        try:
            for e in combo.descendants(control_type="ListItem"):
                n = (e.element_info.name or "").strip()
                if n:
                    items.append((n, e))
        except Exception:
            items = []
        if items:
            break
    return items


def _rank(name):
    m = DOTNET_RE.match(name)
    if not m:
        return None
    major, minor, tail = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    lts = "long term support" in tail
    preview = "preview" in tail or "rc" in tail
    return (major, minor, lts, preview)


def pick_latest(items, prefer_preview):
    """items is a list of (name, elem). Returns (name, elem) or (None, None)."""
    ranked = [(name, elem, _rank(name)) for name, elem in items]
    ranked = [x for x in ranked if x[2] is not None]
    if not ranked:
        return None, None
    max_mm = max(r[2][:2] for r in ranked)
    at_max = [x for x in ranked if x[2][:2] == max_mm]
    if prefer_preview:
        previews = [x for x in at_max if x[2][3]]
        if previews:
            previews_sorted = sorted(previews, key=lambda x: (0 if x[2][2] else 1, x[0]))
            return previews_sorted[0][0], previews_sorted[0][1]
    non_preview = [x for x in at_max if not x[2][3]]
    pool = non_preview or at_max
    lts_first = sorted(pool, key=lambda x: (0 if x[2][2] else 1, x[0]))
    return lts_first[0][0], lts_first[0][1]


def cmd_list(args):
    combo = connect_combo(args.hwnd, args.auto_id, args.name)
    items = list_items(combo)
    try:
        combo.collapse()
    except Exception:
        pass
    for name, _ in items:
        print(name)


def cmd_latest(args):
    combo = connect_combo(args.hwnd, args.auto_id, args.name)
    items = list_items(combo)
    latest_name, _ = pick_latest(items, args.prefer_preview)
    try:
        combo.collapse()
    except Exception:
        pass
    if not latest_name:
        print("ERROR: no .NET x.x items found", file=sys.stderr)
        sys.exit(1)
    print(latest_name)


def cmd_select_latest(args):
    combo = connect_combo(args.hwnd, args.auto_id, args.name)
    items = list_items(combo)
    latest_name, latest_elem = pick_latest(items, args.prefer_preview)
    if not latest_name:
        try:
            combo.collapse()
        except Exception:
            pass
        print("ERROR: no .NET x.x items found", file=sys.stderr)
        sys.exit(1)
    try:
        latest_elem.select()
    except Exception:
        try:
            combo.select(latest_name)
        except Exception as e:
            print(f"ERROR: failed to select {latest_name!r}: {e}", file=sys.stderr)
            sys.exit(1)
    try:
        combo.collapse()
    except Exception:
        pass
    # Confirm the selection stuck.
    for _ in range(10):
        if read_selected(combo) == latest_name:
            break
        time.sleep(0.1)
    print(latest_name)


def cmd_verify_default_is_latest(args):
    combo = connect_combo(args.hwnd, args.auto_id, args.name)
    selected = read_selected(combo)
    items = list_items(combo)
    latest_name, _ = pick_latest(items, args.prefer_preview)
    try:
        combo.collapse()
    except Exception:
        pass
    print(f"selected: {selected!r}")
    print(f"latest:   {latest_name!r}")
    if not latest_name:
        kill_pid(args.kill_pid)
        print("ERROR: no .NET x.x items found", file=sys.stderr)
        sys.exit(1)
    if selected != latest_name:
        kill_pid(args.kill_pid)
        print(f"ERROR: default framework {selected!r} != latest {latest_name!r}",
              file=sys.stderr)
        sys.exit(1)


def cmd_verify_default_equals(args):
    combo = connect_combo(args.hwnd, args.auto_id, args.name)
    selected = read_selected(combo)
    print(f"selected: {selected!r}")
    print(f"expected: {args.expected!r}")
    if selected != args.expected:
        kill_pid(args.kill_pid)
        print(f"ERROR: default framework {selected!r} != expected {args.expected!r}",
              file=sys.stderr)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)

    def add_common(sp, extras=()):
        sp.add_argument("hwnd", type=lambda s: int(s, 0))
        sp.add_argument("--auto-id", dest="auto_id", default=None)
        sp.add_argument("--name", default="Framework")
        for arg in extras:
            arg(sp)

    def prefer_preview(sp):
        sp.add_argument("--prefer-preview", dest="prefer_preview",
                        action="store_true",
                        help="when a preview at the max (major.minor) exists, pick it")

    def kill_pid_arg(sp):
        sp.add_argument("--kill-pid", dest="kill_pid", type=int, default=None,
                        help="on verification failure, kill this pid before exiting")

    add_common(sub.add_parser("list"))
    add_common(sub.add_parser("latest"), (prefer_preview,))
    add_common(sub.add_parser("select-latest"), (prefer_preview,))
    add_common(sub.add_parser("verify-default-is-latest"), (prefer_preview, kill_pid_arg))
    ve = sub.add_parser("verify-default-equals")
    add_common(ve, (kill_pid_arg,))
    ve.add_argument("--expected", required=True, help="expected default combo label")

    a = p.parse_args()
    handlers = {
        "list": cmd_list,
        "latest": cmd_latest,
        "select-latest": cmd_select_latest,
        "verify-default-is-latest": cmd_verify_default_is_latest,
        "verify-default-equals": cmd_verify_default_equals,
    }
    handlers[a.mode](a)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
