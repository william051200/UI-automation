"""Move the mouse cursor to (x, y) without clicking (e.g. to trigger a hover tooltip)."""
import argparse, sys, time
import pyautogui
pyautogui.FAILSAFE = False  # this RDP session can report cursor position as
# (0, 0) even when not actually stuck at a corner, which would otherwise
# permanently trip pyautogui's fail-safe abort.

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("--duration", type=float, default=0.1,
                   help="seconds spent moving to the target (default 0.1)")
    p.add_argument("--settle-ms", dest="settle_ms", type=int, default=0,
                   help="pause after the move so hover UI (e.g. a tooltip) has time to appear")
    a = p.parse_args()
    pyautogui.moveTo(a.x, a.y, duration=a.duration)
    if a.settle_ms > 0:
        time.sleep(a.settle_ms / 1000.0)
    print(f"moved mouse to {a.x},{a.y}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
