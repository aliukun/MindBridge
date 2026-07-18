import os
import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.core.bootstrap import (
    create_schema,
    initialize_users,
)
from app.core.config import Settings
from app.core.database import Base, build_engine
from app.core.security import verify_password
from app.models.entities import UserAccount


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine(
            "sqlite+pysqlite:///:memory:",
        )

        create_schema(self.engine)

        self.SessionTesting = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_initialize_users_is_idempotent(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            settings = Settings(
                _env_file=None,
                bootstrap_student_password=("student-password-2026"),
                bootstrap_admin_password=("admin-password-2026"),
            )

        with self.SessionTesting() as database:
            initialize_users(database, settings)
            initialize_users(database, settings)
            database.commit()

        with self.SessionTesting() as database:
            statement = select(UserAccount).order_by(UserAccount.username)

            users = database.scalars(statement).all()

        self.assertEqual(len(users), 2)

        users_by_name = {user.username: user for user in users}

        student = users_by_name["student"]
        admin = users_by_name["admin"]

        self.assertEqual(
            student.roles,
            ["ROLE_USER"],
        )

        self.assertEqual(
            admin.roles,
            ["ROLE_ADMIN", "ROLE_USER"],
        )

        self.assertTrue(
            verify_password(
                "student-password-2026",
                student.password_hash,
            )
        )

        self.assertTrue(
            verify_password(
                "admin-password-2026",
                admin.password_hash,
            )
        )

    def test_missing_passwords_create_no_users(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            settings = Settings(
                _env_file=None,
            )

        with self.SessionTesting() as database:
            initialize_users(database, settings)
            database.commit()

        with self.SessionTesting() as database:
            users = database.scalars(select(UserAccount)).all()

        self.assertEqual(users, [])


if __name__ == "__main__":
    unittest.main()
