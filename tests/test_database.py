import unittest

from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.bootstrap import create_schema
from app.core.database import Base, build_engine
from app.models.entities import (
    ChatMessage,
    ChatSession,
    PsychologicalReport,
    UserAccount,
)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        """每个测试开始前创建一个全新的内存数据库"""

        self.engine = build_engine(
            "sqlite+pysqlite:///:memory:",
        )

        create_schema(self.engine)

        self.SessionTesting = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def tearDown(self):
        """每个测试结束后释放数据库资源"""

        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_create_schema_creates_required_tables(self):
        """建表函数应创建用户、会话和消息表"""

        table_names = set(inspect(self.engine).get_table_names())

        self.assertTrue(
            {
                "user_accounts",
                "chat_sessions",
                "chat_messages",
                "psychological_reports",
            }.issubset(table_names)
        )

    def test_sqlite_enables_foreign_keys_for_every_connection(
        self,
    ):
        """Engine 提供的 SQLite 连接必须执行外键约束。"""

        with self.engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql(
                "PRAGMA foreign_keys"
            ).scalar_one()

        self.assertEqual(foreign_keys, 1)

    def test_sqlite_rejects_unknown_foreign_key(self):
        """不存在的用户不能被会话外键接受。"""

        with self.assertRaises(IntegrityError):
            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    INSERT INTO chat_sessions (
                        public_id,
                        user_id,
                        title,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "00000000-0000-0000-0000-000000000001",
                        999999,
                        "Invalid owner",
                        "2026-07-18 00:00:00",
                        "2026-07-18 00:00:00",
                    ),
                )

    def test_user_can_be_saved_and_queried(self):
        """UserAccount 应能被写入并重新查询"""

        with self.SessionTesting() as database:
            user = UserAccount(
                username="student",
                display_name="Test Student",
                password_hash="test-only-hash",
            )

            user.roles = {
                "ROLE_USER",
                "ROLE_ADMIN",
            }

            database.add(user)
            database.commit()

        with self.SessionTesting() as database:
            statement = select(UserAccount).where(
                UserAccount.username == "student",
            )

            saved_user = database.scalars(statement).one()

            self.assertEqual(saved_user.username, "student")
            self.assertEqual(
                saved_user.display_name,
                "Test Student",
            )
            self.assertEqual(
                saved_user.roles,
                ["ROLE_ADMIN", "ROLE_USER"],
            )

    def test_raw_sql_delete_cascades_all_child_rows(self):
        """原始 SQL 删除用户时由 SQLite 级联删除子记录。"""

        with self.SessionTesting() as database:
            user = UserAccount(
                username="cascade-user",
                display_name="Cascade User",
                password_hash="test-only-hash",
            )

            chat_session = ChatSession(
                title="Cascade",
                user=user,
            )

            chat_session.messages.append(
                ChatMessage(
                    role="user",
                    content="Hello",
                )
            )

            chat_session.messages[0].assessment_report = PsychologicalReport(
                risk_level="HIGH",
                matched_signals_csv=("SELF_HARM_OR_SUICIDE"),
                assessment_method=("keyword_rule_v1"),
                summary="Test report",
            )

            database.add(user)
            database.commit()

            user_id = user.id

        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "DELETE FROM user_accounts WHERE id = ?",
                (user_id,),
            )

            counts = {
                table_name: connection.exec_driver_sql(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).scalar_one()
                for table_name in (
                    "user_accounts",
                    "chat_sessions",
                    "chat_messages",
                    "psychological_reports",
                )
            }

        self.assertEqual(
            counts,
            {
                "user_accounts": 0,
                "chat_sessions": 0,
                "chat_messages": 0,
                "psychological_reports": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
