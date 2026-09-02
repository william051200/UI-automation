"""Unit tests for scripts/uia/invoke_control.py without a live window."""
import contextlib
import io
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "uia"))

import invoke_control  # noqa: E402


def _control(name, auto_id, control_type):
    control = mock.Mock()
    control.element_info = SimpleNamespace(
        name=name, automation_id=auto_id, control_type=control_type)
    return control


def _run(argv, controls):
    out = io.StringIO()
    err = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["invoke_control.py", *argv]), \
            mock.patch.object(invoke_control, "Application") as application, \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        application.return_value.connect.return_value.window.return_value \
            .descendants.return_value = controls
        try:
            invoke_control.main()
        except SystemExit as exc:
            code = exc.code or 0
    return code, out.getvalue(), err.getvalue()


class InvokeControlTests(unittest.TestCase):
    def test_match_modes(self):
        self.assertTrue(invoke_control.matches("Create Project", "create", "contains"))
        self.assertTrue(invoke_control.matches("Create Project", r"^Create", "regex"))
        self.assertFalse(invoke_control.matches("Create Project", "Cancel", "exact"))

    def test_invokes_matching_control(self):
        cancel = _control("Cancel", "cancel", "Button")
        create = _control("Create", "create", "Button")

        code, out, _ = _run(
            ["123", "--name", "Create", "--auto-id", "create",
             "--control-type", "Button"],
            [cancel, create])

        self.assertEqual(code, 0)
        create.invoke.assert_called_once_with()
        cancel.invoke.assert_not_called()
        self.assertIn("invoked\tCreate\tcreate\tButton", out)

    def test_falls_back_to_click_when_invoke_fails(self):
        control = _control("Create", "create", "Button")
        control.invoke.side_effect = RuntimeError("unsupported")

        code, _, _ = _run(["123", "--name", "Create"], [control])

        self.assertEqual(code, 0)
        control.click_input.assert_called_once_with()

    def test_no_match_exits_one(self):
        code, _, err = _run(["123", "--name", "Missing"], [])

        self.assertEqual(code, 1)
        self.assertIn("no match", err)

    def test_optional_no_match_succeeds(self):
        code, out, err = _run(["123", "--name", "Missing", "--optional"], [])

        self.assertEqual(code, 0)
        self.assertIn("no match; skipping", out)
        self.assertEqual(err, "")

    def test_retries_until_control_appears(self):
        control = _control("Reload projects", "", "Button")
        out = io.StringIO()
        with mock.patch.object(
                sys, "argv",
                ["invoke_control.py", "123", "--name", "Reload projects",
                 "--timeout-ms", "100", "--poll-ms", "0"]), \
                mock.patch.object(invoke_control, "Application") as application, \
                contextlib.redirect_stdout(out):
            descendants = application.return_value.connect.return_value.window \
                .return_value.descendants
            descendants.side_effect = [[], [control]]
            invoke_control.main()

        self.assertEqual(descendants.call_count, 2)
        control.invoke.assert_called_once_with()
        self.assertIn("invoked\tReload projects", out.getvalue())


if __name__ == "__main__":
    unittest.main()
