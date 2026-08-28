"""Scroll the mouse wheel at (x, y). Positive delta = up/right, negative = down/left."""
import argparse, sys
import pyautogui
pyautogui.FAILSAFE = False  # this RDP session can report cursor position as
# (0, 0) even when not actually stuck at a corner.

MOUSEEVENTF_HWHEEL = 0x01000
WHEEL_DELTA = 120


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("delta", type=int,
                   help="wheel clicks; positive = up/right, negative = down/left")
    p.add_argument("--horizontal", action="store_true",
                   help="scroll horizontally instead of vertically (Windows only)")
    a = p.parse_args()
    pyautogui.moveTo(a.x, a.y)
    if a.horizontal:
        if sys.platform != "win32":
            print("ERROR: --horizontal is Windows-only", file=sys.stderr); sys.exit(1)
        import ctypes
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, a.delta * WHEEL_DELTA, 0)
        direction = "right" if a.delta > 0 else "left"
    else:
        pyautogui.scroll(a.delta)
        direction = "up" if a.delta > 0 else "down"
    print(f"scrolled {direction} {abs(a.delta)} clicks at {a.x},{a.y}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
