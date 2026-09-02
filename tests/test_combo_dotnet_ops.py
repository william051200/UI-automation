"""Unit tests for scripts/uia/combo_dotnet_ops.py version selection."""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "uia"))

import combo_dotnet_ops  # noqa: E402


class PickLatestTests(unittest.TestCase):
    def test_ignores_non_dotnet_labels(self):
        name, element = combo_dotnet_ops.pick_latest(
            [("Choose a framework", object()), ("Custom", object())], False)
        self.assertIsNone(name)
        self.assertIsNone(element)

    def test_picks_highest_version(self):
        items = [(".NET 8.0", "8"), (".NET 10.0", "10"), (".NET 9.0", "9")]
        self.assertEqual(combo_dotnet_ops.pick_latest(items, False), (".NET 10.0", "10"))

    def test_prefers_lts_for_same_version(self):
        items = [
            (".NET 10.0 (Standard Term Support)", "sts"),
            (".NET 10.0 (Long Term Support)", "lts"),
        ]
        self.assertEqual(
            combo_dotnet_ops.pick_latest(items, False),
            (".NET 10.0 (Long Term Support)", "lts"))

    def test_preview_requires_preference_when_stable_exists(self):
        items = [
            (".NET 11.0", "stable"),
            (".NET 11.0 Preview 1", "preview"),
        ]
        self.assertEqual(combo_dotnet_ops.pick_latest(items, False), (".NET 11.0", "stable"))
        self.assertEqual(
            combo_dotnet_ops.pick_latest(items, True),
            (".NET 11.0 Preview 1", "preview"))


if __name__ == "__main__":
    unittest.main()
