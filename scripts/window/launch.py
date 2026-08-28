"""Launch an executable, optionally wait for its top-level window to appear.

Prints `pid` on success when `--wait-window` is not used. With `--wait-window`,
prints `pid<TAB>hwnd<TAB>left<TAB>top<TAB>right<TAB>bottom<TAB>title` once a
matching window is found (same column order as find_window.py). The match must
hold the same hwnd across `--stable-checks` consecutive polls (default 2)
before being returned -- some apps (e.g. Visual Studio) briefly show a
splash/loading window with a title matching the final main window's regex,
then swap it out for the real main-frame window under a different hwnd; a
caller that captured the splash's handle would later fail with an "invalid
handle" error the moment it tried to use it. Exit codes:
  0 OK   1 launch failed   2 window-wait timed out   3 bad usage
"""
import argparse, os, re, subprocess, sys, time
from pywinauto import Desktop

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def find_matching_window(title_rx, backend, prefer_pid=None):
    """Return the first window whose title matches `title_rx`.

    `prefer_pid` (optional) wins ties: if any candidate window is owned by
    that pid, it is returned first; otherwise the first match (any pid) wins.
    Modern Windows apps (UWP, Win11 Notepad) often host their UI in a
    sibling process distinct from the launcher pid, so we never use pid as
    a *filter* — only as a tiebreaker.
    """
    backends = ["uia", "win32"] if backend == "any" else [backend]
    seen = set()
    fallback = None
    for b in backends:
        for w in Desktop(backend=b).windows():
            try:
                if w.handle in seen:
                    continue
                seen.add(w.handle)
                title = w.window_text() or ""
                if not title_rx.search(title):
                    continue
                r = w.rectangle()
                row = (w.process_id(), w.handle, r.left, r.top, r.right, r.bottom, title)
                if prefer_pid is not None and row[0] == prefer_pid:
                    return row
                if fallback is None:
                    fallback = row
            except Exception:
                continue
    return fallback


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("executable", help="path or name on PATH (e.g. notepad, calc)")
    p.add_argument("--args", nargs=argparse.REMAINDER, default=[],
                   help="trailing args passed to the executable (place after `--args`)")
    p.add_argument("--cwd", default=None, help="working directory for the launched process")
    p.add_argument("--wait-window", dest="wait_window", default=None,
                   help="regex on window title; if set, poll until matched or timeout")
    p.add_argument("--wait-timeout-ms", dest="wait_timeout_ms", type=int, default=10000)
    p.add_argument("--poll-ms", dest="poll_ms", type=int, default=250)
    p.add_argument("--stable-checks", dest="stable_checks", type=int, default=2,
                   help="require the SAME hwnd to match on this many consecutive polls before "
                        "returning it (default 2). Guards against apps (e.g. Visual Studio) that "
                        "briefly show a splash/loading window with a matching title before "
                        "swapping in the real main-frame window under a different hwnd; without "
                        "this, callers could capture a handle that is destroyed moments later.")
    p.add_argument("--backend", choices=["uia", "win32", "any"], default="any")
    a = p.parse_args()

    if a.cwd is not None and not os.path.isdir(a.cwd):
        print(f"ERROR: --cwd not a directory: {a.cwd}", file=sys.stderr); sys.exit(3)

    cmd = [a.executable] + list(a.args)
    try:
        proc = subprocess.Popen(cmd, cwd=a.cwd)
    except FileNotFoundError as e:
        print(f"ERROR: executable not found: {a.executable} ({e})", file=sys.stderr); sys.exit(1)
    except OSError as e:
        print(f"ERROR: launch failed: {e}", file=sys.stderr); sys.exit(1)

    pid = proc.pid

    if not a.wait_window:
        print(pid)
        return

    title_rx = re.compile(a.wait_window)
    deadline = time.time() + a.wait_timeout_ms / 1000.0
    interval = max(a.poll_ms, 0) / 1000.0
    stable_needed = max(a.stable_checks, 1)
    last_handle = None
    stable_count = 0
    attempts = 0
    while True:
        attempts += 1
        hit = find_matching_window(title_rx, a.backend, prefer_pid=pid)
        if hit:
            if hit[1] == last_handle:
                stable_count += 1
            else:
                last_handle = hit[1]
                stable_count = 1
            if stable_count >= stable_needed:
                print("\t".join(str(x) for x in hit))
                return
        else:
            last_handle = None
            stable_count = 0
        if time.time() >= deadline:
            print(f"timeout: window matching {a.wait_window!r} not found after "
                  f"{a.wait_timeout_ms}ms ({attempts} attempts); launcher pid={pid}",
                  file=sys.stderr)
            sys.exit(2)
        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
