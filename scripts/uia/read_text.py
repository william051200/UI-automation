"""Read the text content of a UIA element (inverse of type_text.py).

Selector model mirrors find_control.py — pass the parent window's hwnd plus
any combination of --name / --auto-id / --control-type to locate a descendant
element, then read its text. Without selectors, reads the parent's own text.

Modern apps (UWP, WinUI, Win11 Notepad) host child controls as UIA elements
without their own Win32 hwnd, so addressing by `<parent_hwnd> + selectors`
is the only thing that works for them.

Prints the value on stdout with no surrounding quotes and no trailing newline,
so `capture: { vars.x: "$.stdout" }` rules get the value verbatim.
Tries window_text() first, then texts() as a fallback (multiline Documents).
Exits 1 if the hwnd / selector resolves to nothing.
"""
import argparse, re, sys
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError

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


def walk(elem):
    yield elem
    try:
        for child in elem.children() or []:
            yield from walk(child)
    except Exception:
        return


def find_descendant(root, name, auto_id, control_type, cls, match_mode, nth=1):
    """Return the nth (1-based) matching descendant, sorted top-to-bottom /
    left-to-right for stable ordering. Disambiguates cases where several
    controls share the same auto_id/name (e.g. the code editor and the
    Output pane both expose a "Text Editor" / WpfTextView Edit control)."""
    found = []
    for el in walk(root):
        try:
            info = el.element_info
            n = el.window_text() or ""
            aid = info.automation_id or ""
            ct = info.control_type or ""
            c = info.class_name or ""
        except Exception:
            continue
        if (matches(n, name, match_mode)
                and matches(aid, auto_id, match_mode)
                and matches(ct, control_type, match_mode)
                and matches(c, cls, match_mode)):
            try:
                r = el.rectangle()
                key = (r.top, r.left)
            except Exception:
                key = (0, 0)
            found.append((key, el))
    if not found:
        return None
    found.sort(key=lambda f: f[0])
    if nth > len(found):
        return None
    return found[nth - 1][1]


def read_value(elem, joiner):
    value = ""
    # For ComboBox controls, try selected_text() first
    try:
        ct = elem.element_info.control_type or ""
        if ct == "ComboBox" and hasattr(elem, "selected_text"):
            value = elem.selected_text() or ""
    except Exception:
        pass
    if not value:
        try:
            value = elem.window_text() or ""
        except Exception:
            pass
    if not value:
        try:
            segments = elem.texts() or []
            if segments and isinstance(segments[0], str) and segments[0] == elem.window_text():
                segments = segments[1:]
            value = joiner.join(s for s in segments if isinstance(s, str))
        except Exception:
            pass
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("hwnd", type=lambda s: int(s, 0),
                   help="parent window handle (decimal or 0x-hex)")
    p.add_argument("--name", default=None)
    p.add_argument("--auto-id", dest="auto_id", default=None)
    p.add_argument("--control-type", dest="control_type", default=None)
    p.add_argument("--class", dest="cls", default=None)
    p.add_argument("--match", choices=["exact", "contains", "regex"], default="exact")
    p.add_argument("--backend", choices=["uia", "win32"], default="uia")
    p.add_argument("--strip", action="store_true",
                   help="strip leading/trailing whitespace before printing")
    p.add_argument("--regex", default=None,
                   help="apply this regex to the value and print only the match; if the "
                        "pattern has a capturing group, print group(1), else the whole match. "
                        "Post-processing step (like --strip); prints nothing and exits 1 if "
                        "the pattern does not match. Useful to extract a token (e.g. a version "
                        "number) from a longer label for clean capture.")
    p.add_argument("--joiner", default="\n",
                   help="string used to join multi-segment texts() fallback (default newline)")
    p.add_argument("--nth", type=int, default=1,
                   help="1-based index into matches sorted top-to-bottom/left-to-right "
                        "(default 1). Use to disambiguate controls that share the same "
                        "name/auto_id, e.g. the code editor vs. the Output pane, which "
                        "both expose a 'Text Editor' / WpfTextView Edit control.")
    a = p.parse_args()

    try:
        app = Application(backend=a.backend).connect(handle=a.hwnd)
        root = app.window(handle=a.hwnd)
        if not root.exists(timeout=0.5):
            print(f"ERROR: hwnd {a.hwnd} not found", file=sys.stderr); sys.exit(1)
    except ElementNotFoundError:
        print(f"ERROR: hwnd {a.hwnd} not found", file=sys.stderr); sys.exit(1)
    except Exception as e:
        print(f"ERROR: could not connect to hwnd {a.hwnd}: {e}", file=sys.stderr); sys.exit(1)

    has_selector = any(s is not None for s in (a.name, a.auto_id, a.control_type, a.cls))
    if has_selector:
        target = find_descendant(root, a.name, a.auto_id, a.control_type, a.cls, a.match, a.nth)
        if target is None:
            print("no match", file=sys.stderr); sys.exit(1)
    else:
        target = root

    value = read_value(target, a.joiner)
    if a.strip:
        value = value.strip()
    if a.regex is not None:
        m = re.search(a.regex, value)
        if not m:
            print(f"ERROR: regex {a.regex!r} did not match value {value!r}",
                  file=sys.stderr); sys.exit(1)
        value = m.group(1) if m.groups() else m.group(0)

    sys.stdout.write(value)
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)

