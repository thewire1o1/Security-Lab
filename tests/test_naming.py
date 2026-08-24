from __future__ import annotations

import unittest

from security_lab.naming import normalize_slug


class NormalizeSlugTests(unittest.TestCase):
    def test_normalizes_spaces_and_symbols(self) -> None:
        self.assertEqual(normalize_slug("case one/test"), "case-one-test")

    def test_preserves_safe_characters(self) -> None:
        self.assertEqual(normalize_slug("case_01.alpha-beta"), "case_01.alpha-beta")

    def test_rejects_parent_directory(self) -> None:
        with self.assertRaises(ValueError):
            normalize_slug("..")

    def test_rejects_dot_prefixed_name(self) -> None:
        with self.assertRaises(ValueError):
            normalize_slug(".hidden")

    def test_rejects_overlong_name(self) -> None:
        with self.assertRaises(ValueError):
            normalize_slug("a" * 81)


if __name__ == "__main__":
    unittest.main()
