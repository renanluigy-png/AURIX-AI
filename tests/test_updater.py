"""Version ordering tests used by the in-app update checker."""

import unittest

from aurix.versioning import is_newer_version, version_key


class UpdateVersionTests(unittest.TestCase):
    def test_parses_version_tag_prefix(self):
        self.assertEqual(version_key("v1.12.0"), (1, 12, 0))

    def test_new_version_is_detected(self):
        self.assertTrue(is_newer_version("1.9.0", "0.3.0"))

    def test_numeric_order_handles_two_digit_minor(self):
        self.assertTrue(is_newer_version("1.10.0", "1.9.0"))
        self.assertFalse(is_newer_version("1.9.0", "1.10.0"))

    def test_equivalent_versions_do_not_trigger(self):
        self.assertFalse(is_newer_version("v1.9.0", "1.9.0"))
        self.assertFalse(is_newer_version("1.9", "1.9.0"))

    def test_invalid_versions_are_not_newer(self):
        self.assertFalse(is_newer_version("preview", "1.0.0"))
        self.assertFalse(is_newer_version("1.1.0", "dev"))


if __name__ == "__main__":
    unittest.main()
