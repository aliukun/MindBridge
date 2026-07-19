import re
import unittest

from app.services.privacy_service import (
    CAMPUS_ID_PLACEHOLDER,
    EMAIL_PLACEHOLDER,
    NATIONAL_ID_PLACEHOLDER,
    PHONE_PLACEHOLDER,
    PrivacySanitizer,
    sanitize_for_ai,
)


class PrivacyServiceTests(unittest.TestCase):
    def test_standard_identifiers_use_fixed_placeholders(self):
        original = (
            "电话 13800138000，邮箱 student@example.edu.cn，身份证 11010519491231002X。"
        )

        sanitized = sanitize_for_ai(original)

        self.assertNotIn("13800138000", sanitized)
        self.assertNotIn("student@example.edu.cn", sanitized)
        self.assertNotIn("11010519491231002X", sanitized)

        self.assertIn(PHONE_PLACEHOLDER, sanitized)
        self.assertIn(EMAIL_PLACEHOLDER, sanitized)
        self.assertIn(NATIONAL_ID_PLACEHOLDER, sanitized)

        self.assertIn("13800138000", original)

    def test_labeled_chinese_and_english_campus_ids_are_redacted(self):
        sanitized = sanitize_for_ai("我的学号：2026123456，student id=AB-123456。")

        self.assertNotIn("2026123456", sanitized)
        self.assertNotIn("AB-123456", sanitized)

        self.assertEqual(
            sanitized.count(CAMPUS_ID_PLACEHOLDER),
            2,
        )

    def test_unlabeled_ordinary_numbers_are_not_over_redacted(self):
        text = "教室是 101，课程年份是 2026，今天完成 3 道题。"

        self.assertEqual(
            sanitize_for_ai(text),
            text,
        )

    def test_trusted_extra_campus_pattern_is_extensible(self):
        sanitizer = PrivacySanitizer(
            extra_campus_id_patterns=(re.compile(r"MB#[0-9]{6}"),)
        )

        sanitized = sanitizer.sanitize("校内编号 MB#123456")

        self.assertEqual(
            sanitized,
            f"校内编号 {CAMPUS_ID_PLACEHOLDER}",
        )

    def test_sanitizing_twice_is_idempotent(self):
        once = sanitize_for_ai("电话 13800138000，邮箱 a@example.com")

        self.assertEqual(
            sanitize_for_ai(once),
            once,
        )

    def test_phone_pattern_does_not_redact_digits_inside_longer_id(self):
        text = "编号 91380013800012345678"

        self.assertEqual(
            sanitize_for_ai(text),
            text,
        )


if __name__ == "__main__":
    unittest.main()
