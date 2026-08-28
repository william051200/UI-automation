"""Mouse click at (x, y)."""
import argparse, sys
import pyautogui
pyautogui.FAILSAFE = False  # see move_mouse.py comment: this RDP session can
# report cursor position as (0, 0) even when not actually stuck at a corner.

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--right", action="store_true")
    p.add_argument("--double", action="store_true")
    a = p.parse_args()
    btn = "right" if a.right else "left"
    clicks = 2 if a.double else 1
    pyautogui.click(a.x, a.y, button=btn, clicks=clicks, interval=0.05)
    print(f"clicked {btn} {clicks}x at {a.x},{a.y}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
