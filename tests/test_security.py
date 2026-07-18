import unittest

from app.core.security import MIN_PASSWORD_LENGTH, hash_password, verify_password


class PasswordSecurityTests(unittest.TestCase):
    def test_password_is_hashed_and_can_be_verified(self):
        password = "student-password-2026"

        password_hash = hash_password(password)

        self.assertNotEqual(password_hash, password)
        self.assertTrue(password_hash.startswith("$argon2"))
        self.assertTrue(verify_password(password, password_hash))

    def test_wrong_password_is_rejected(self):
        password_hash = hash_password("student-password-2026")

        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_same_password_gets_different_hashes(self):
        password = "student-password-2026"

        first_hash = hash_password(password)
        second_hash = hash_password(password)

        self.assertNotEqual(first_hash, second_hash)
        self.assertTrue(verify_password(password, first_hash))
        self.assertTrue(verify_password(password, second_hash))

    def test_short_password_is_rejected(self):
        short_password = "a" * (MIN_PASSWORD_LENGTH - 1)

        with self.assertRaises(ValueError):
            hash_password(short_password)


if __name__ == "__main__":
    unittest.main()
