"""Press a single key or hotkey combo (e.g. enter, win, ctrl+s)."""
import argparse, sys
import pyautogui
pyautogui.FAILSAFE = False  # this RDP session can report cursor position as
# (0, 0) even when not actually stuck at a corner; pyautogui's fail-safe check
# runs before keyboard actions too, so it must be disabled here as well.

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("combo")
    a = p.parse_args()
    parts = [k.strip().lower() for k in a.combo.split("+") if k.strip()]
    if len(parts) == 1:
        pyautogui.press(parts[0])
    else:
        pyautogui.hotkey(*parts)
    print(f"pressed {a.combo}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)
