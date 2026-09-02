"""Tests for the standard-format CSV loader (readable phase format)."""
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "csvfmt"))

import csv_loader  # noqa: E402

CSV = os.path.join(REPO_ROOT, "test_cases", "v0", "powershell_echo_loop.csv")


class CsvLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = csv_loader.load(CSV)

    def test_minimal_top_level_keys(self):
        # The simplified CSV only carries name/description in config; the
        # screenshot folder (artifacts.screenshot_dir) is no longer set per
        # CSV -- it's defaulted by run_test.py's Ctx to
        # "screenshots/{name}-{timestamp}" unless a CSV opts into a custom
        # value.
        for key in ("name", "description", "steps"):
            self.assertIn(key, self.spec)
        self.assertNotIn("artifacts", self.spec)
        # config-heavy blocks are intentionally gone
        for key in ("inputs", "timing", "expected_results"):
            self.assertNotIn(key, self.spec)

    def test_steps_have_inferred_type_and_auto_id(self):
        steps = self.spec["steps"]
        self.assertTrue(steps)
        for step in steps:
            self.assertIn("id", step)
            self.assertIn("type", step)
            # readable-only / source columns must not leak into the spec
            for leaked in ("No", "Main step", "Trigger", "Expected",
                           "args_mode", "wait_ms"):
                self.assertNotIn(leaked, step)
        # unrolled: no foreach steps
        self.assertFalse(any(s["type"] == "foreach" for s in steps))

    def test_types_are_inferred_correctly(self):
        steps = self.spec["steps"]
        # non-special types come from the script basename
        self.assertEqual(steps[0]["type"], "key")
        self.assertEqual(steps[3]["type"], "find_window")
        asserts = [s for s in steps if s["type"] == "assert_console_contains"]
        self.assertEqual(len(asserts), 4)
        for s in asserts:
            self.assertIn("script", s)
            self.assertIn("expected_contains_expr", s)

    def test_four_screenshot_steps(self):
        shots = [s for s in self.spec["steps"] if s["type"] == "screenshot"]
        self.assertEqual(len(shots), 4)
        for s in shots:
            self.assertIn("args_expr_on_pass", s)
            # screenshot dir prepended to the filename pattern
            self.assertTrue(s["args_expr_on_pass"][0]
                            .startswith("{artifacts.screenshot_dir}/"))

    def test_wait_after_is_inline_int(self):
        waits = [s["wait_after"] for s in self.spec["steps"]
                 if "wait_after" in s]
        self.assertTrue(waits)
        self.assertTrue(all(isinstance(w, int) for w in waits))

    def test_poll_values_are_inline_ints(self):
        for s in self.spec["steps"]:
            if s["type"] == "assert_console_contains":
                self.assertIsInstance(s["poll_total_ms"], int)
                self.assertIsInstance(s["poll_interval_ms"], int)

    def test_step_ids_are_unique(self):
        ids = [s["id"] for s in self.spec["steps"]]
        self.assertEqual(len(ids), len(set(ids)))


class CsvLoaderLoopTests(unittest.TestCase):
    LOOP_CSV = os.path.join(REPO_ROOT, "tests", "fixtures", "loop_example.csv")

    @classmethod
    def setUpClass(cls):
        cls.spec = csv_loader.load(cls.LOOP_CSV)

    def test_while_step_is_built(self):
        whiles = [s for s in self.spec["steps"] if s["type"] == "while"]
        self.assertEqual(len(whiles), 1)

    def test_while_condition_body_and_max_iter(self):
        loop = next(s for s in self.spec["steps"] if s["type"] == "while")
        # condition comes from the # LOOP row
        self.assertEqual(loop["condition"]["script"], "scripts/uia/find_control.py")
        self.assertEqual(loop["condition"]["expect_exit"], 0)
        self.assertIn("vars.row_x", loop["condition"]["capture"])
        self.assertEqual(loop["max_iterations"], 5)
        # body holds the two rows between # LOOP and # END LOOP
        self.assertEqual(len(loop["body"]), 2)
        self.assertEqual(loop["body"][0]["type"], "click")
        self.assertEqual(loop["body"][1]["type"], "key")

    def test_steps_surround_the_loop(self):
        types = [s["type"] for s in self.spec["steps"]]
        # one key before, the while, one key after
        self.assertEqual(types, ["key", "while", "key"])

    def test_all_ids_unique_including_body(self):
        ids = []
        for s in self.spec["steps"]:
            ids.append(s["id"])
            ids.extend(b["id"] for b in s.get("body", []))
        self.assertEqual(len(ids), len(set(ids)))


class CsvValidationTests(unittest.TestCase):
    HEADER = ",".join(csv_loader.S.STEPS_COLUMNS)

    def validate_text(self, text):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", encoding="utf-8",
                newline="", delete=False) as f:
            f.write(text)
            path = f.name
        try:
            csv_loader.validate(path)
        finally:
            os.unlink(path)

    def csv(self, step_row):
        return (
            "# CONFIG\n"
            "Section,Key,Value\n"
            "name,,example\n"
            "description,,Example test\n"
            "artifacts,screenshot_dir,screenshots/{timestamp}\n\n"
            "# STEPS\n"
            f"{self.HEADER}\n"
            f"{step_row}\n"
        )

    def test_accepts_canonical_csv(self):
        self.validate_text(self.csv(
            '1,1,Launch,Press a key.,scripts/input/key.py,"[""win""]",'
            '100,,,,,,,,,'))

    def test_rejects_wrong_header(self):
        text = self.csv(
            '1,1,Launch,Press a key.,scripts/input/key.py,"[""win""]",'
            '100,,,,,,,,,').replace("No,step no,", "No,")
        with self.assertRaisesRegex(ValueError, "header must be"):
            self.validate_text(text)

    def test_rejects_nonsequential_step_number(self):
        with self.assertRaisesRegex(ValueError, "step no must be 1"):
            self.validate_text(self.csv(
                '1,2,Launch,Press a key.,scripts/input/key.py,"[""win""]",'
                '100,,,,,,,,,'))

    def test_rejects_missing_or_unknown_script(self):
        with self.assertRaisesRegex(ValueError, "script is required"):
            self.validate_text(self.csv("1,1,Launch,Press a key.,,,,,,,,,,,,"))
        with self.assertRaisesRegex(ValueError, "script does not exist"):
            self.validate_text(self.csv(
                "1,1,Launch,Press a key.,scripts/input/missing.py,,"
                "100,,,,,,,,,"))

    def test_rejects_invalid_json_and_negative_wait(self):
        with self.assertRaisesRegex(ValueError, "args is not valid JSON"):
            self.validate_text(self.csv(
                "1,1,Launch,Press a key.,scripts/input/key.py,not-json,"
                "100,,,,,,,,,"))
        with self.assertRaisesRegex(ValueError, "wait_ms must be"):
            self.validate_text(self.csv(
                '1,1,Launch,Press a key.,scripts/input/key.py,"[""win""]",'
                '-1,,,,,,,,,'))

    def test_rejects_unclosed_loop(self):
        row = (
            '# LOOP,1,Repeat,Find control.,scripts/uia/find_control.py,'
            '"[""0"", ""--name"", ""x""]",,,,,,,,,5,')
        with self.assertRaisesRegex(ValueError, "missing # END LOOP"):
            self.validate_text(self.csv(row))
class CsvLoaderNestedLoopTests(unittest.TestCase):
    NESTED_LOOP_CSV = os.path.join(REPO_ROOT, "tests", "fixtures", "nested_loop_example.csv")

    @classmethod
    def setUpClass(cls):
        cls.spec = csv_loader.load(cls.NESTED_LOOP_CSV)

    def test_outer_while_step_is_built(self):
        types = [s["type"] for s in self.spec["steps"]]
        self.assertEqual(types, ["key", "while", "key"])

    def test_outer_body_contains_click_and_nested_while(self):
        outer = next(s for s in self.spec["steps"] if s["type"] == "while")
        body_types = [s["type"] for s in outer["body"]]
        self.assertEqual(body_types, ["click", "while", "key"])

    def test_inner_while_condition_and_body(self):
        outer = next(s for s in self.spec["steps"] if s["type"] == "while")
        inner = next(s for s in outer["body"] if s["type"] == "while")
        self.assertEqual(inner["condition"]["script"], "scripts/uia/find_control.py")
        self.assertIn("vars.inner_x", inner["condition"]["capture"])
        self.assertEqual(inner["max_iterations"], 3)
        self.assertEqual(len(inner["body"]), 1)
        self.assertEqual(inner["body"][0]["type"], "click")

    def test_all_ids_unique_across_nesting(self):
        ids = []

        def collect(step):
            ids.append(step["id"])
            for b in step.get("body", []):
                collect(b)

        for s in self.spec["steps"]:
            collect(s)
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
