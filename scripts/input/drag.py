"""Press a mouse button at (x1,y1), drag to (x2,y2), release.

Uses an explicit mouseDown -> moveTo -> mouseUp sequence with small settle
pauses, because pyautogui.dragTo() is unreliable on Windows 11 (the down/move
events can fire faster than the OS recognises as a drag, registering as a
click instead).

Sets process-DPI-awareness on import so the (x, y) screen coords align with
the physical pixels reported by pywinauto / find_window.py / find_control.py
when this script is invoked standalone (e.g. via an MCP server). When invoked
by ui-auto's run_test.py the parent has already set this, so the call here
is a harmless no-op.
"""
import argparse, sys, time

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import pyautogui
pyautogui.FAILSAFE = False  # this RDP session can report cursor position as
# (0, 0) even when not actually stuck at a corner, which would otherwise
# permanently trip pyautogui's fail-safe abort.


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("x1", type=int)
    p.add_argument("y1", type=int)
    p.add_argument("x2", type=int)
    p.add_argument("y2", type=int)
    p.add_argument("--duration", type=float, default=0.5,
                   help="seconds spent moving from start to end (default 0.5)")
    p.add_argument("--button", choices=["left", "right", "middle"], default="left")
    p.add_argument("--settle-ms", dest="settle_ms", type=int, default=80,
                   help="pause after mouseDown and before mouseUp so the OS "
                        "recognises the drag (default 80)")
    a = p.parse_args()

    settle = max(a.settle_ms, 0) / 1000.0
    pyautogui.moveTo(a.x1, a.y1)
    pyautogui.mouseDown(button=a.button)
    if settle:
        time.sleep(settle)
    pyautogui.moveTo(a.x2, a.y2, duration=a.duration)
    if settle:
        time.sleep(settle)
    pyautogui.mouseUp(button=a.button)
    print(f"dragged {a.button} from {a.x1},{a.y1} to {a.x2},{a.y2} in {a.duration}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            pyautogui.mouseUp(button="left")
            pyautogui.mouseUp(button="right")
            pyautogui.mouseUp(button="middle")
        except Exception:
            pass
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
