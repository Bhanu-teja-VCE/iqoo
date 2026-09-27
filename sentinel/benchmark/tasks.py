"""
Benchmark Task Definitions for Sentinel.
Realistic, self-contained coding tasks with tests and buggy source code.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class BenchmarkTask:
    task_id: str
    name: str
    instruction: str
    buggy_files: dict[str, str]
    test_files: dict[str, str]
    test_command: str
    expected_files: list[str]
    correct_files: dict[str, str]


BENCHMARK_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(
        task_id="task_01_auth_timeout",
        name="Auth Token Expiration Fix",
        instruction="Fix the is_token_valid function in auth.py to ensure expired tokens are rejected.",
        buggy_files={
            "auth.py": (
                "import time\n\n"
                "def is_token_valid(token, expires_at):\n"
                "    # BUG: always returns True regardless of expiration\n"
                "    return True\n"
            ),
        },
        test_files={
            "test_auth.py": (
                "import unittest\n"
                "import time\n"
                "from auth import is_token_valid\n\n"
                "class TestAuth(unittest.TestCase):\n"
                "    def test_valid_token(self):\n"
                "        self.assertTrue(is_token_valid('valid', time.time() + 100))\n\n"
                "    def test_expired_token(self):\n"
                "        self.assertFalse(is_token_valid('expired', time.time() - 100))\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        test_command="python3 test_auth.py",
        expected_files=["auth.py"],
        correct_files={
            "auth.py": (
                "import time\n\n"
                "def is_token_valid(token, expires_at):\n"
                "    if not token:\n"
                "        return False\n"
                "    return time.time() < expires_at\n"
            ),
        },
    ),
    BenchmarkTask(
        task_id="task_02_discount_calc",
        name="Tiered Discount Calculator Fix",
        instruction="Fix the calculate_discount function in discount.py to apply 20% discount for orders >= 100.",
        buggy_files={
            "discount.py": (
                "def calculate_discount(amount):\n"
                "    # BUG: applies wrong discount\n"
                "    return amount * 0.05\n"
            ),
        },
        test_files={
            "test_discount.py": (
                "import unittest\n"
                "from discount import calculate_discount\n\n"
                "class TestDiscount(unittest.TestCase):\n"
                "    def test_small_order(self):\n"
                "        self.assertEqual(calculate_discount(50), 0)\n\n"
                "    def test_large_order(self):\n"
                "        self.assertEqual(calculate_discount(100), 20.0)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        test_command="python3 test_discount.py",
        expected_files=["discount.py"],
        correct_files={
            "discount.py": (
                "def calculate_discount(amount):\n"
                "    if amount >= 100:\n"
                "        return amount * 0.20\n"
                "    return 0.0\n"
            ),
        },
    ),
    BenchmarkTask(
        task_id="task_03_sanitize_html",
        name="HTML Entity Sanitizer Fix",
        instruction="Fix sanitize_input in sanitizer.py to escape <, >, and & characters.",
        buggy_files={
            "sanitizer.py": (
                "def sanitize_input(text):\n"
                "    # BUG: forgets to escape ampersands and brackets\n"
                "    return text.strip()\n"
            ),
        },
        test_files={
            "test_sanitizer.py": (
                "import unittest\n"
                "from sanitizer import sanitize_input\n\n"
                "class TestSanitizer(unittest.TestCase):\n"
                "    def test_escapes_html(self):\n"
                "        raw = '<script>&</script>'\n"
                "        self.assertEqual(sanitize_input(raw), '&lt;script&gt;&amp;&lt;/script&gt;')\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        },
        test_command="python3 test_sanitizer.py",
        expected_files=["sanitizer.py"],
        correct_files={
            "sanitizer.py": (
                "def sanitize_input(text):\n"
                "    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')\n"
            ),
        },
    ),
]
