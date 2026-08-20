"""Dismiss known toast notifications / info-bars that can render on top of dialog
buttons and silently swallow clicks (the click lands on the toast instead of the
control underneath, so the wizard/dialog never advances).

Covers popups observed in VS 2026 Insiders, e.g.:
  - "Discover Writing Assistance, a new way to work" (first-run feature promo)
  - "Writing Assistance (Preview)" / "Writing Assistance paused" toast
  - "Visual Studio 2026 will update when closed" update-available toast
  - "How satisfied are you with Visual Studio 2026, on a scale of 1 to 5?"
    in-IDE satisfaction-survey info-bar

Tolerant by design: if no matching toast/info-bar is present this is a fast
no-op (exit 0), so it is safe to call speculatively before/after any wizard
click instead of only reactively after a failure.
"""
import argparse, re, sys, time
from pywinauto import Application

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DEFAULT_PATTERNS = [
    r"Discover Writing Assistance",
    r"Writing Assistance",
    r"will update when closed",
    r"How satisfied are you",
    r"is available and will be applied",
]

# Preference order: prefer an explicit dismiss/close action over an affirmative one
# so we never accidentally trigger "Update now" etc.
DISMISS_BUTTON_NAMES = ["Close", "No, thanks", "Postpone", "Dismiss", "Not now", "Got it", "OK"]


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def find_dismiss_button(scope):
    """Look for a known dismiss/close button on scope itself or among its descendants."""
    if scope is None:
        return None
    candidates = [scope] + list(_safe(scope.descendants, []) or [])
    by_name = {}
    for c in candidates:
        try:
            if c.element_info.control_type != "Button":
                continue
            name = (c.window_text() or "").strip()
        except Exception:
            continue
        if name:
            by_name.setdefault(name, c)
    for want in DISMISS_BUTTON_NAMES:
        for name, ctrl in by_name.items():
            if name == want or name.startswith(want):
                return ctrl
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("hwnd", type=lambda s: int(s, 0),
                   help="root window to scan for toasts (e.g. vars.vs_hwnd)")
    p.add_argument("--pattern", action="append", dest="patterns", default=None,
                   help="regex matched against a control's name to identify a toast/info-bar; "
                        "may repeat. Defaults to a built-in list of known VS toasts.")
    p.add_argument("--max-count", dest="max_count", type=int, default=5,
                   help="maximum number of toasts to dismiss in one call (default 5)")
    p.add_argument("--timeout-ms", dest="timeout_ms", type=int, default=0,
                   help="if > 0, keep polling for a toast to appear for up to this many ms "
                        "before giving up (default 0 = single scan, for a fast speculative call)")
    p.add_argument("--poll-ms", dest="poll_ms", type=int, default=300)
    p.add_argument("--backend", choices=["uia", "win32"], default="uia")
    a = p.parse_args()

    patterns = [re.compile(pat, re.I) for pat in (a.patterns or DEFAULT_PATTERNS)]

    app = Application(backend=a.backend).connect(handle=a.hwnd)
    win = app.window(handle=a.hwnd)

    deadline = time.time() + max(0, a.timeout_ms) / 1000.0
    dismissed = 0

    while dismissed < a.max_count:
        found = None
        for c in win.descendants():
            name = _safe(c.window_text, "") or ""
            if name and any(rx.search(name) for rx in patterns):
                found = c
                break
        if found is None:
            if a.timeout_ms > 0 and time.time() < deadline:
                time.sleep(max(0.05, a.poll_ms / 1000.0))
                continue
            break

        btn = find_dismiss_button(found)
        if btn is None:
            btn = find_dismiss_button(_safe(found.parent))
        if btn is None:
            print(f"NOTE: toast matched {(_safe(found.window_text, '') or '')[:60]!r} "
                  f"but no dismiss button found; leaving it", file=sys.stderr)
            break

        clicked = False
        for action in ("invoke", "click_input"):
            try:
                getattr(btn, action)()
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            print("ERROR: found dismiss button but click failed", file=sys.stderr)
            sys.exit(2)

        dismissed += 1
        print(f"dismissed: {(_safe(found.window_text, '') or '')[:60]!r} "
              f"via {(_safe(btn.window_text, '') or '')!r}")
        time.sleep(0.4)

    print(f"dismissed {dismissed} toast(s)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(2)
