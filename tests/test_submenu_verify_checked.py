"""Unit tests for scripts/uia/submenu_verify_checked.py without a live window."""
import contextlib
import io
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "uia"))

import submenu_verify_checked as svc  # noqa: E402


def _rect(left, top, right, bottom):
    return SimpleNamespace(left=left, top=top, right=right, bottom=bottom)


def _menu_item(name, state, rect):
    item = mock.Mock()
    item.element_info = SimpleNamespace(name=name)
    item.legacy_properties.return_value = {"State": state}
    item.rectangle.return_value = rect
    return item


CHECKED = svc.STATE_SYSTEM_CHECKED
UNCHECKED = 0


class MatchesTests(unittest.TestCase):
    def test_contains_is_case_insensitive(self):
        self.assertTrue(svc.matches("Framework (net10.0-windows)", "framework", "contains"))

    def test_exact_requires_full_match(self):
        self.assertFalse(svc.matches("Framework (net10.0-windows)", "Framework", "exact"))
        self.assertTrue(svc.matches("Framework", "Framework", "exact"))

    def test_regex_mode(self):
        self.assertTrue(svc.matches("net10.0-windows10.0.19041.0", r"windows\d", "regex"))


class IsCheckedTests(unittest.TestCase):
    def test_checked_bit_set(self):
        elem = _menu_item("net10.0-windows10.0.19041.0", CHECKED, _rect(0, 0, 10, 10))
        self.assertTrue(svc.is_checked(elem))

    def test_checked_bit_not_set(self):
        elem = _menu_item("net10.0-android", UNCHECKED, _rect(0, 0, 10, 10))
        self.assertFalse(svc.is_checked(elem))

    def test_missing_legacy_properties_is_unchecked(self):
        elem = mock.Mock()
        elem.legacy_properties.side_effect = RuntimeError("no pattern")
        self.assertFalse(svc.is_checked(elem))


def _run(argv, root_control, submenu_and_leaves):
    """submenu_and_leaves: (submenu_elem, [leaf_elems]) both returned from
    win.descendants(control_type='MenuItem') across the two lookup passes."""
    submenu_elem, leaves = submenu_and_leaves
    out = io.StringIO()
    err = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["submenu_verify_checked.py", *argv]), \
            mock.patch.object(svc, "Application") as application, \
            mock.patch.object(svc, "send_keys"), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        win = application.return_value.connect.return_value.window.return_value
        win.child_window.return_value = root_control
        win.descendants.return_value = [submenu_elem] + leaves
        try:
            svc.main()
        except SystemExit as exc:
            code = exc.code or 0
    return code, out.getvalue(), err.getvalue()


class MainWorkflowTests(unittest.TestCase):
    def _submenu_and_leaves(self):
        submenu = _menu_item("Framework (net10.0-windows10.0.19041.0)", UNCHECKED,
                              _rect(494, 92, 795, 116))
        leaves = [
            _menu_item("net10.0-android", UNCHECKED, _rect(799, 96, 1014, 120)),
            _menu_item("net10.0-ios", UNCHECKED, _rect(799, 120, 1014, 144)),
            _menu_item("net10.0-maccatalyst", UNCHECKED, _rect(799, 144, 1014, 168)),
            _menu_item("net10.0-windows10.0.19041.0", CHECKED, _rect(799, 168, 1014, 192)),
        ]
        return submenu, leaves

    def test_list_mode_prints_checked_flags(self):
        root = mock.Mock()
        root.exists.return_value = True
        code, out, _ = _run(
            ["123", "--root-name", "Debug Target", "--submenu", "Framework", "list"],
            root, self._submenu_and_leaves())

        self.assertEqual(code, 0)
        self.assertIn("net10.0-android\t0", out)
        self.assertIn("net10.0-windows10.0.19041.0\t1", out)
        root.expand.assert_called_once_with()

    def test_verify_checked_matches_expected(self):
        root = mock.Mock()
        root.exists.return_value = True
        code, out, _ = _run(
            ["123", "--root-name", "Debug Target", "--submenu", "Framework",
             "verify-checked", "--expect", "net10.0-windows10.0.19041.0"],
            root, self._submenu_and_leaves())

        self.assertEqual(code, 0)
        self.assertIn("net10.0-windows10.0.19041.0", out)

    def test_verify_checked_mismatch_exits_one(self):
        root = mock.Mock()
        root.exists.return_value = True
        code, _, err = _run(
            ["123", "--root-name", "Debug Target", "--submenu", "Framework",
             "verify-checked", "--expect", "net10.0-ios"],
            root, self._submenu_and_leaves())

        self.assertEqual(code, 1)
        self.assertIn("expected checked item 'net10.0-ios'", err)
        self.assertIn("net10.0-windows10.0.19041.0", err)

    def test_root_control_not_found_exits_one(self):
        root = mock.Mock()
        root.exists.return_value = False
        code, _, err = _run(
            ["123", "--root-name", "Missing", "--submenu", "Framework",
             "--timeout-ms", "100", "list"],
            root, self._submenu_and_leaves())

        self.assertEqual(code, 1)
        self.assertIn("root control not found", err)

    def test_keep_open_skips_escape(self):
        root = mock.Mock()
        root.exists.return_value = True
        with mock.patch.object(sys, "argv",
                                ["submenu_verify_checked.py", "123", "--root-name", "Debug Target",
                                 "--submenu", "Framework", "--keep-open", "list"]), \
                mock.patch.object(svc, "Application") as application, \
                mock.patch.object(svc, "send_keys") as send_keys_mock:
            submenu, leaves = self._submenu_and_leaves()
            win = application.return_value.connect.return_value.window.return_value
            win.child_window.return_value = root
            win.descendants.return_value = [submenu] + leaves
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    svc.main()
                except SystemExit:
                    pass
        send_keys_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
