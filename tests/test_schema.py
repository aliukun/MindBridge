import unittest

from sqlalchemy import inspect

from app.core.bootstrap import create_schema
from app.core.database import Base, build_engine
from app.core.schema import (
    IncompatibleDatabaseSchemaError,
)

EXPECTED_TABLES = {
    "user_accounts",
    "chat_sessions",
    "chat_messages",
    "psychological_reports",
}


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine("sqlite+pysqlite:///:memory:")

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def schema_snapshot(self) -> list[tuple[object, ...]]:
        with self.engine.connect() as connection:
            return [
                tuple(row)
                for row in connection.exec_driver_sql(
                    """
                    SELECT type, name, tbl_name, sql
                    FROM sqlite_master
                    WHERE name NOT LIKE 'sqlite_%'
                    ORDER BY type, name
                    """
                ).all()
            ]

    def create_v050_legacy_schema(self) -> None:
        """创建与 v0.5.0 相同、尚无 CASCADE 的结构。"""

        statements = (
            """
            CREATE TABLE user_accounts (
                id INTEGER NOT NULL,
                username VARCHAR(64) NOT NULL,
                display_name VARCHAR(128) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                roles_csv VARCHAR(256) NOT NULL,
                created_at DATETIME
                    DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
                PRIMARY KEY (id)
            )
            """,
            """
            CREATE UNIQUE INDEX ix_user_accounts_username
            ON user_accounts (username)
            """,
            """
            CREATE TABLE chat_sessions (
                id INTEGER NOT NULL,
                public_id VARCHAR(36) NOT NULL,
                user_id INTEGER NOT NULL,
                title VARCHAR(160) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(user_id)
                    REFERENCES user_accounts (id)
            )
            """,
            """
            CREATE UNIQUE INDEX ix_chat_sessions_public_id
            ON chat_sessions (public_id)
            """,
            """
            CREATE INDEX ix_chat_sessions_user_id
            ON chat_sessions (user_id)
            """,
            """
            CREATE TABLE chat_messages (
                id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                role VARCHAR(16) NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT ck_chat_messages_role CHECK (role IN ('user', 'assistant')),
                FOREIGN KEY(session_id)
                    REFERENCES chat_sessions (id)
            )
            """,
            """
            CREATE INDEX ix_chat_messages_session_id
            ON chat_messages (session_id)
            """,
            """
            CREATE TABLE psychological_reports (
                id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                risk_level VARCHAR(16) NOT NULL,
                matched_signals_csv VARCHAR(512) NOT NULL,
                assessment_method VARCHAR(64) NOT NULL,
                summary TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT ck_psychological_reports_risk_level CHECK (risk_level IN ('MEDIUM', 'HIGH')),
                FOREIGN KEY(message_id)
                    REFERENCES chat_messages (id)
            )
            """,
            """
            CREATE UNIQUE INDEX
                ix_psychological_reports_message_id
            ON psychological_reports (message_id)
            """,
            """
            CREATE INDEX ix_psychological_reports_risk_level
            ON psychological_reports (risk_level)
            """,
        )

        with self.engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)

    def test_empty_database_is_created_from_orm_metadata(self):
        self.assertEqual(
            inspect(self.engine).get_table_names(),
            [],
        )

        create_schema(self.engine)

        self.assertEqual(
            set(inspect(self.engine).get_table_names()),
            EXPECTED_TABLES,
        )

    def test_compatible_schema_can_be_initialized_twice(self):
        create_schema(self.engine)
        first_snapshot = self.schema_snapshot()

        create_schema(self.engine)
        second_snapshot = self.schema_snapshot()

        self.assertEqual(
            second_snapshot,
            first_snapshot,
        )

    def test_v050_schema_is_rejected_without_modification(self):
        self.create_v050_legacy_schema()
        before = self.schema_snapshot()

        with self.assertRaises(IncompatibleDatabaseSchemaError) as raised:
            create_schema(self.engine)

        after = self.schema_snapshot()

        self.assertEqual(after, before)
        self.assertEqual(
            raised.exception.differences,
            (
                "chat_messages: foreign keys differ",
                "chat_sessions: foreign keys differ",
                ("psychological_reports: foreign keys differ"),
            ),
        )

    def test_partial_schema_is_rejected_without_new_tables(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE user_accounts (
                    id INTEGER PRIMARY KEY
                )
                """
            )

        before = self.schema_snapshot()

        with self.assertRaises(IncompatibleDatabaseSchemaError):
            create_schema(self.engine)

        self.assertEqual(
            self.schema_snapshot(),
            before,
        )


if __name__ == "__main__":
    unittest.main()
