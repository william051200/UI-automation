"""Dump UIA text of a window (e.g. PowerShell console) to stdout."""
import argparse, sys
from pywinauto import Application

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("hwnd", type=lambda s: int(s, 0))
    a = p.parse_args()
    app = Application(backend="uia").connect(handle=a.hwnd)
    win = app.window(handle=a.hwnd)
    texts = []
    try:
        texts = win.descendants()
    except Exception:
        pass
    # Prefer the Document control (PowerShell console exposes its buffer there)
    for c in texts:
        try:
            if c.element_info.control_type != "Document":
                continue
            try:
                v = c.iface_value.CurrentValue
                if v:
                    print(v)
                    return
            except Exception:
                pass
            # fallback: legacy patterns
            try:
                v = c.legacy_properties().get("Value", "")
                if v:
                    print(v)
                    return
            except Exception:
                pass
            # fallback: UIA TextPattern (some conhost/cmd.exe consoles expose
            # their buffer only via TextPattern, not Value/LegacyIAccessible)
            try:
                doc_range = c.iface_text.DocumentRange
                v = doc_range.GetText(-1)
                if v and v.strip():
                    print(v)
                    return
            except Exception:
                pass
        except Exception:
            continue
    # Some consoles (e.g. Windows Terminal-hosted, as used by VS 18's
    # "Start Without Debugging") expose the buffer as a plain Text control
    # instead of Document. Prefer the longest Text control's window_text.
    best = ""
    for c in texts:
        try:
            if c.element_info.control_type == "Text":
                t = c.window_text()
                if t and len(t) > len(best):
                    best = t
        except Exception:
            continue
    if len(best) > 50:
        print(best)
        return
    # Last resort: dump every visible text
    out = []
    for c in texts:
        try:
            t = c.window_text()
            if t:
                out.append(t)
        except Exception:
            continue
    print("\n".join(out))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
