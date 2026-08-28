"""Read or write the Windows clipboard (text only).

Modes:
  read              prints current clipboard text to stdout (no trailing
                    newline added), empty string if clipboard has no text
  write <text>      replaces clipboard contents with <text>
  write --b64 <b64> replaces clipboard contents with base64-decoded <b64>
                    text (UTF-8); use this to avoid literal '{'/'}' in
                    <text> being mistaken for CSV/run_test.py placeholders
  write-stdin       reads stdin verbatim and writes it to the clipboard
                    (use for multi-line / binary-safe text)

Uses the Win32 clipboard API via ctypes — no extra dependency required.
"""
import argparse, base64, ctypes, sys
from ctypes import wintypes

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t


def _open(retries=10):
    # OpenClipboard can fail if another process holds it. Retry briefly.
    import time
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.05)
    raise OSError(f"OpenClipboard failed (error {ctypes.get_last_error()})")


def read_clipboard():
    _open()
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def write_clipboard(text):
    data = text.encode("utf-16-le") + b"\x00\x00"
    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        raise OSError(f"GlobalAlloc failed (error {ctypes.get_last_error()})")
    ptr = kernel32.GlobalLock(h)
    if not ptr:
        raise OSError(f"GlobalLock failed (error {ctypes.get_last_error()})")
    ctypes.memmove(ptr, data, len(data))
    kernel32.GlobalUnlock(h)
    _open()
    try:
        user32.EmptyClipboard()
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            raise OSError(f"SetClipboardData failed (error {ctypes.get_last_error()})")
    finally:
        user32.CloseClipboard()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("read")
    w = sub.add_parser("write")
    w.add_argument("text")
    w.add_argument("--b64", action="store_true",
                    help="treat <text> as base64-encoded UTF-8 and decode before writing")
    sub.add_parser("write-stdin")
    a = p.parse_args()

    if a.mode == "read":
        sys.stdout.write(read_clipboard())
        sys.stdout.flush()
    elif a.mode == "write":
        text = base64.b64decode(a.text).decode("utf-8") if a.b64 else a.text
        write_clipboard(text)
        print(f"wrote {len(text)} chars")
    elif a.mode == "write-stdin":
        text = sys.stdin.read()
        write_clipboard(text)
        print(f"wrote {len(text)} chars")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
