"""Minimal regression coverage for the scoreboard's critical behavior.

Run with: python -m unittest discover -s tests
"""

import ast
import math
import time
import unittest
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
APP_SOURCE = APP_PATH.read_text(encoding="utf-8")
APP_TREE = ast.parse(APP_SOURCE)


def load_function(name):
    """Load one top-level function without executing Streamlit UI code."""
    function = next(
        node
        for node in APP_TREE.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace = {"time": time, "math": math}
    exec(compile(ast.fix_missing_locations(module), str(APP_PATH), "exec"), namespace)
    return namespace[name]


class FakeDriver:
    def __init__(self, rows):
        self.rows = rows

    def execute_script(self, script):
        if "window.scrollTo" in script:
            return None
        return self.rows


class ScoreboardRegressionTests(unittest.TestCase):
    def setUp(self):
        self.parse_rows = load_function("parse_all_with_scroll")
        self.rows = [
            ["대표", "대표 홍길동", "0", "0", "1,000", "20"],
            ["야방", "부장 김하늘", "0", "0", "990", "18"],
            ["시그", "인턴 이바다", "0", "0", "975", "17"],
        ]

    def test_excludes_only_ceo_row_when_requested(self):
        people = self.parse_rows(FakeDriver(self.rows), "score", True)
        self.assertEqual([person["name"] for person in people], ["김하늘", "이바다"])

    def test_preserves_actual_label_next_to_each_member(self):
        people = self.parse_rows(FakeDriver(self.rows), "score", True)
        self.assertEqual(
            [(person["name"], person["label"]) for person in people],
            [("김하늘", "야방"), ("이바다", "시그")],
        )

    def test_score_difference_rounding_and_display_remain_present(self):
        self.assertIn("diff_exact = p1['score'] - p2['score']", APP_SOURCE)
        self.assertIn("diff = int(diff_exact) + 1", APP_SOURCE)
        self.assertIn("diff = math.ceil(diff_exact)", APP_SOURCE)
        self.assertIn("점 차이</div>", APP_SOURCE)

    def test_refresh_interval_still_allows_point_one_seconds(self):
        number_inputs = [
            node
            for node in ast.walk(APP_TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "number_input"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "자동 갱신 주기 (초)"
        ]
        self.assertEqual(len(number_inputs), 1)
        keywords = {keyword.arg: keyword.value for keyword in number_inputs[0].keywords}
        self.assertEqual(ast.literal_eval(keywords["min_value"]), 0.1)
        self.assertEqual(ast.literal_eval(keywords["step"]), 0.1)

        fragments = [
            node
            for node in ast.walk(APP_TREE)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fragment"
        ]
        self.assertTrue(
            any(
                keyword.arg == "run_every"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "interval"
                for call in fragments
                for keyword in call.keywords
            )
        )


if __name__ == "__main__":
    unittest.main()
