"""Unit tests for scripts/input/move_mouse.py without moving the real cursor."""
import contextlib
import io
import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "input"))

import move_mouse  # noqa: E402


class MoveMouseTests(unittest.TestCase):
    def test_moves_with_default_duration(self):
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["move_mouse.py", "10", "20"]), \
                mock.patch.object(move_mouse.pyautogui, "moveTo") as move_to, \
                mock.patch.object(move_mouse.time, "sleep") as sleep, \
                contextlib.redirect_stdout(out):
            move_mouse.main()

        move_to.assert_called_once_with(10, 20, duration=0.1)
        sleep.assert_not_called()
        self.assertEqual(out.getvalue().strip(), "moved mouse to 10,20")

    def test_honors_duration_and_settle_time(self):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(
                sys, "argv",
                ["move_mouse.py", "30", "40", "--duration", "0.5", "--settle-ms", "250"]), \
                mock.patch.object(move_mouse.pyautogui, "moveTo") as move_to, \
                mock.patch.object(move_mouse.time, "sleep") as sleep:
            move_mouse.main()

        move_to.assert_called_once_with(30, 40, duration=0.5)
        sleep.assert_called_once_with(0.25)


if __name__ == "__main__":
    unittest.main()
