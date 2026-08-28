"""Maximize a window by hwnd; skip (no-op) if it is already maximized.

Restores the window first if it is minimised, then maximises it. If the window
is already maximised, nothing is changed and `already maximized hwnd=<n> ...` is
printed. Prints `maximized hwnd=<n> title=<...>` on a successful maximise.
Exits 1 if the hwnd does not exist.
"""
import argparse, sys, time
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("hwnd", type=lambda s: int(s, 0),
                   help="window handle (decimal or 0x-hex)")
    p.add_argument("--backend", choices=["uia", "win32"], default="uia")
    p.add_argument("--settle-ms", dest="settle_ms", type=int, default=100,
                   help="sleep after maximizing so the window can finish animating (default 100)")
    a = p.parse_args()

    # Connecting via UIA immediately after a window is created can transiently
    # raise "Invalid handle ... passed to connect()" if the window's UI Automation
    # provider hasn't finished initializing yet (observed live right after devenv
    # first opens). Retry a few times with a short backoff before giving up.
    win = None
    last_error = None
    for _attempt in range(5):
        try:
            app = Application(backend=a.backend).connect(handle=a.hwnd)
            candidate = app.window(handle=a.hwnd)
            if candidate.exists(timeout=0.5):
                win = candidate
                break
        except ElementNotFoundError as e:
            last_error = e
        except Exception as e:
            last_error = e
        time.sleep(0.5)

    if win is None:
        print(f"ERROR: hwnd {a.hwnd} not found: {last_error}", file=sys.stderr); sys.exit(1)

    try:
        if win.is_minimized():
            win.restore()
        if win.is_maximized():
            title = _title(win)
            print(f"already maximized hwnd={a.hwnd} title={title!r}")
            return
        win.maximize()
    except Exception as e:
        print(f"ERROR: could not maximize hwnd {a.hwnd}: {e}", file=sys.stderr); sys.exit(1)

    if a.settle_ms > 0:
        time.sleep(a.settle_ms / 1000.0)

    print(f"maximized hwnd={a.hwnd} title={_title(win)!r}")


def _title(win):
    try:
        return win.window_text() or ""
    except Exception:
        return ""


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
