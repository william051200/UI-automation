"""Tests for the runner's toast-notification failure recovery
(run_test.run_steps_retrying / run_test.dismiss_toasts).

This is on by default for every CSV (see docs/csv-test-format.md): the
runner auto-detects the window to target from whichever `vars.*hwnd` was
most recently captured. When a step fails and a window handle is available,
the runner dismisses toasts, re-runs the *previous* step (its click may have
been swallowed by the toast), then retries the failed step once before
giving up. A CSV can opt out with `# CONFIG` row `retry,toast_dismiss,off`,
or pin a specific window with `retry,toast_dismiss_var,<vars name>`.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import run_test  # noqa: E402


# Increments a counter file each time it runs and prints the new count; exits
# 1 while the count is below --fail-until, then exits 0.
_COUNTER_SRC = '''\
import sys
path = sys.argv[1]
fail_until = int(sys.argv[2]) if len(sys.argv) > 2 else 0
try:
    with open(path) as f:
        n = int(f.read() or "0")
except FileNotFoundError:
    n = 0
n += 1
with open(path, "w") as f:
    f.write(str(n))
print(n)
if n < fail_until:
    sys.exit(1)
'''


class ToastRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.counter_script = os.path.join(self.tmp, "counter.py")
        with open(self.counter_script, "w") as f:
            f.write(_COUNTER_SRC)
        run_test.QUIET = True

    def _make_ctx(self, toast_dismiss_var=None, toast_dismiss_off=False,
                  vs_hwnd=None, last_hwnd=None):
        spec = {"name": "t", "artifacts": {"screenshot_dir": self.tmp}, "steps": []}
        retry = {}
        if toast_dismiss_var:
            retry["toast_dismiss_var"] = toast_dismiss_var
        if toast_dismiss_off:
            retry["toast_dismiss"] = "off"
        if retry:
            spec["retry"] = retry
        ctx = run_test.Ctx(spec)
        if vs_hwnd is not None:
            ctx.vars["vs_hwnd"] = vs_hwnd
        if last_hwnd is not None:
            ctx.last_hwnd = last_hwnd
        return ctx

    def _counter_file(self, name):
        return os.path.join(self.tmp, name)

    def test_no_retry_when_disabled_via_config(self):
        # recovery is on by default, but this spec opts out
        ctx = self._make_ctx(toast_dismiss_off=True, last_hwnd="12345")
        current = self._counter_file("current.txt")
        # fails once then would pass on a 2nd call, but nothing should retry it
        steps = [
            {"id": "current", "type": "key", "script": self.counter_script,
             "args": [current, "2"]},
        ]
        with self.assertRaises(AssertionError):
            run_test.run_steps_retrying(steps, ctx, {})
        with open(current) as f:
            self.assertEqual(int(f.read()), 1)  # only ran once, no retry

    def test_no_retry_when_no_hwnd_captured_yet(self):
        # retry is enabled by default, but no window has been captured yet
        # (e.g. the failure happened before the app launched) -> no retry.
        ctx = self._make_ctx()
        current = self._counter_file("current.txt")
        steps = [
            {"id": "current", "type": "key", "script": self.counter_script,
             "args": [current, "2"]},
        ]
        with self.assertRaises(AssertionError):
            run_test.run_steps_retrying(steps, ctx, {})
        with open(current) as f:
            self.assertEqual(int(f.read()), 1)

    @mock.patch("run_test.dismiss_toasts", return_value=True)
    def test_recovers_by_rerunning_previous_step_then_retrying(self, mock_dismiss):
        ctx = self._make_ctx(last_hwnd="12345")  # auto-detected window, default-on
        prev = self._counter_file("prev.txt")
        current = self._counter_file("current.txt")
        # current fails on its 1st call, succeeds on its 2nd (the retry).
        steps = [
            {"id": "prev", "type": "key", "script": self.counter_script,
             "args": [prev, "0"]},
            {"id": "current", "type": "key", "script": self.counter_script,
             "args": [current, "2"]},
        ]
        run_test.run_steps_retrying(steps, ctx, {})  # should not raise
        mock_dismiss.assert_called_once_with(ctx)
        with open(prev) as f:
            self.assertEqual(int(f.read()), 2)  # ran once normally + once on recovery
        with open(current) as f:
            self.assertEqual(int(f.read()), 2)  # 1st call failed, 2nd (retry) passed

    @mock.patch("run_test.dismiss_toasts", return_value=True)
    def test_still_fails_if_retry_also_fails(self, mock_dismiss):
        ctx = self._make_ctx(last_hwnd="12345")
        current = self._counter_file("current.txt")
        # fail_until=99 -> never passes, so both the original attempt and the
        # single retry fail; the runner must not retry a second time.
        steps = [
            {"id": "current", "type": "key", "script": self.counter_script,
             "args": [current, "99"]},
        ]
        with self.assertRaises(AssertionError):
            run_test.run_steps_retrying(steps, ctx, {})
        mock_dismiss.assert_called_once_with(ctx)
        with open(current) as f:
            self.assertEqual(int(f.read()), 2)  # original attempt + exactly one retry

    @mock.patch("run_test.dismiss_toasts", return_value=True)
    def test_first_step_failure_has_no_previous_step_to_rerun(self, mock_dismiss):
        ctx = self._make_ctx(last_hwnd="12345")
        current = self._counter_file("current.txt")
        steps = [
            {"id": "current", "type": "key", "script": self.counter_script,
             "args": [current, "2"]},
        ]
        run_test.run_steps_retrying(steps, ctx, {})  # should not raise
        with open(current) as f:
            self.assertEqual(int(f.read()), 2)

    def test_dismiss_toasts_noop_when_disabled(self):
        ctx = self._make_ctx(toast_dismiss_off=True, last_hwnd="12345")
        self.assertFalse(run_test.dismiss_toasts(ctx))

    def test_dismiss_toasts_noop_when_no_hwnd_captured(self):
        ctx = self._make_ctx()
        self.assertFalse(run_test.dismiss_toasts(ctx))

    def test_dismiss_toasts_uses_explicit_var_override(self):
        # retry.toast_dismiss_var pins a specific window even if a different
        # (e.g. stale/popup) window was captured more recently.
        ctx = self._make_ctx(toast_dismiss_var="vs_hwnd", vs_hwnd="12345",
                              last_hwnd="99999")
        script = os.path.join(REPO_ROOT, "scripts", "window", "dismiss_toasts.py")
        with mock.patch("run_test.os.path.exists", return_value=True), \
             mock.patch("run_test.subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            self.assertTrue(run_test.dismiss_toasts(ctx))
            called_args = mock_run.call_args[0][0]
            self.assertIn("12345", called_args)

    def test_capture_tracks_last_hwnd_from_any_var_ending_in_hwnd(self):
        ctx = self._make_ctx()
        self.assertIsNone(ctx.last_hwnd)
        run_test.capture("111\t222\n", {"vars.vs_hwnd": "$.cols[0]"}, ctx)
        self.assertEqual(ctx.last_hwnd, "111")
        run_test.capture("333\n", {"vars.popup_hwnd": "$.cols[0]"}, ctx)
        self.assertEqual(ctx.last_hwnd, "333")  # most recent capture wins


if __name__ == "__main__":
    unittest.main()
