"""Dump readable console/debug-console text from a window to stdout.

Supports:
- PowerShell / classic console windows via UIA Document value/text pattern
- Visual Studio Debug Console fallback via Ctrl+A / Ctrl+C clipboard extraction
- Last-resort visible UIA text dump
"""

import argparse
import sys
import time

from pywinauto import Application
from pywinauto.keyboard import send_keys

try:
    import win32clipboard
except Exception:
    win32clipboard = None

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


UIA_TEXT_PATTERN_ID = 10014


def _clean(text):
    if text is None:
        return ""
    return str(text).replace("\r\n", "\n").replace("\r", "\n").strip()


def _read_clipboard_text():
    if win32clipboard is None:
        return ""

    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return _clean(win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT))
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        return ""

    return ""


def _try_value_pattern(ctrl):
    try:
        if hasattr(ctrl, "iface_value") and ctrl.iface_value:
            value = _clean(ctrl.iface_value.CurrentValue)
            if value:
                return value
    except Exception:
        pass

    try:
        value = _clean(ctrl.legacy_properties().get("Value", ""))
        if value:
            return value
    except Exception:
        pass

    return ""


def _try_text_pattern(ctrl):
    try:
        element = ctrl.element_info.element
        pattern = element.GetCurrentPattern(UIA_TEXT_PATTERN_ID)
        document_range = pattern.DocumentRange
        value = _clean(document_range.GetText(-1))
        if value:
            return value
    except Exception:
        pass

    return ""


def _try_uia_document_text(win):
    controls = []
    try:
        controls.append(win)
    except Exception:
        pass

    try:
        controls.extend(win.descendants())
    except Exception:
        pass

    for ctrl in controls:
        try:
            if ctrl.element_info.control_type != "Document":
                continue
        except Exception:
            continue

        value = _try_value_pattern(ctrl)
        if value:
            return value

        value = _try_text_pattern(ctrl)
        if value:
            return value

    return ""


def _try_clipboard_console_read(win):
    """Fallback for Visual Studio Debug Console.

    Some console windows expose only a UIA Document named 'Text Area' without a readable Value.
    Selecting all text and copying it is the most reliable fallback for those windows.
    """
    try:
        win.set_focus()
        time.sleep(0.2)

        # For Windows console / VS Debug Console:
        # Ctrl+A selects text, Ctrl+C copies selected text.
        send_keys("^a")
        time.sleep(0.2)
        send_keys("^c")
        time.sleep(0.3)

        value = _read_clipboard_text()
        if value:
            return value
    except Exception:
        pass

    return ""


def _visible_text_dump(win):
    out = []
    best = ""

    try:
        controls = win.descendants()
    except Exception:
        controls = []

    for ctrl in controls:
        try:
            text = _clean(ctrl.window_text())
            if text:
                out.append(text)
                if ctrl.element_info.control_type == "Text" and len(text) > len(best):
                    best = text
        except Exception:
            continue

    if len(best) > 50:
        return best
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hwnd", type=lambda s: int(s, 0))
    args = parser.parse_args()

    app = Application(backend="uia").connect(handle=args.hwnd)
    win = app.window(handle=args.hwnd)

    # 1. Prefer real UIA document text.
    value = _try_uia_document_text(win)
    if value:
        print(value)
        return

    # 2. Fallback for Visual Studio Debug Console / Windows console host.
    value = _try_clipboard_console_read(win)
    if value:
        print(value)
        return

    # 3. Last resort: dump visible UIA labels.
    print(_visible_text_dump(win))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)