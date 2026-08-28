"""Find a top-level window whose title matches a regex; print info."""
import argparse, re, sys, time
from pywinauto import Desktop

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("title_regex")
    p.add_argument("--class", dest="cls", default=None)
    p.add_argument("--pid", type=int, default=None,
                   help="only match windows owned by this process id")
    p.add_argument("--backend", choices=["uia", "win32", "any"], default="any",
                   help="UIA misses some legacy Win32 dialogs (e.g. classic 'Save As'); 'any' searches both and de-dups by handle.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="print all matches")
    g.add_argument("--nth", type=int, help="print only the Nth match (1-based) after filtering and de-dup")
    p.add_argument("--timeout-ms", dest="timeout_ms", type=int, default=0,
                   help="if > 0, re-scan until a match is found or this many milliseconds elapse "
                        "(handles windows, e.g. context-menu Popups, that render slightly after a "
                        "click). Default 0 = single one-shot scan (unchanged behavior; negative "
                        "assertions -- e.g. 'window is gone' -- stay fast).")
    p.add_argument("--poll-ms", dest="poll_ms", type=int, default=300,
                   help="poll interval in ms when --timeout-ms > 0 (default 300).")
    p.add_argument("--min-height", dest="min_height", type=int, default=0,
                   help="only match windows at least this tall in pixels (default 0 = no filter). "
                        "Useful for a generic class like 'Popup', which Windows also assigns to small, "
                        "unrelated transient windows (e.g. shell tooltips/artifacts) -- confirmed live "
                        "that this can otherwise cause a VS context menu's Popup window to be missed in "
                        "favor of one of these unrelated, much shorter Popup windows.")
    a = p.parse_args()
    if a.nth is not None and a.nth < 1:
        p.error("--nth must be a 1-based integer")
    rx = re.compile(a.title_regex)
    backends = ["uia", "win32"] if a.backend == "any" else [a.backend]

    def scan():
        matches = []
        seen = set()
        for backend in backends:
            for w in Desktop(backend=backend).windows():
                try:
                    if w.handle in seen:
                        continue
                    title = w.window_text() or ""
                    if not rx.search(title):
                        continue
                    if a.pid is not None and w.process_id() != a.pid:
                        continue
                    if a.cls and w.class_name() != a.cls:
                        continue
                    r = w.rectangle()
                    if a.min_height > 0 and (r.bottom - r.top) < a.min_height:
                        continue
                    matches.append((w.process_id(), w.handle, r.left, r.top, r.right, r.bottom, title))
                    seen.add(w.handle)
                except Exception:
                    continue
        # Sort after filtering/de-dup so numbered candidate lists are reproducible.
        matches.sort(key=lambda m: (m[0], m[1]))
        return matches

    deadline = time.time() + a.timeout_ms / 1000.0
    interval = max(a.poll_ms, 0) / 1000.0
    while True:
        matches = scan()
        if matches or a.timeout_ms <= 0 or time.time() >= deadline:
            break
        time.sleep(interval)

    if not matches:
        print("no match", file=sys.stderr); sys.exit(1)
    if a.nth is not None:
        if a.nth > len(matches):
            print("no match", file=sys.stderr); sys.exit(1)
        matches = [matches[a.nth - 1]]
    for m in (matches if a.all else matches[:1]):
        print("\t".join(str(x) for x in m))

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(2)
