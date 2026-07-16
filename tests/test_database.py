import unittest

from sqlalchemy import inspect, select, func
from sqlalchemy.orm import sessionmaker

from app.core.bootstrap import create_schema
from app.core.database import build_engine, Base
from app.models.entities import UserAccount, ChatSession, ChatMessage


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        """每个测试开始前创建一个全新的内存数据库"""

        self.engine = build_engine(
            "sqlite+pysqlite:///:memory:",
        )

        create_schema(self.engine)

        self.SessionTesting = sessionmaker(
            bind = self.engine,
            expire_on_commit = False,
        )

    def tearDown(self):
        """每个测试结束后释放数据库资源"""

        Base.metadata.drop_all(bind = self.engine)
        self.engine.dispose()

    def test_create_schema_creates_required_tables(self):
        """建表函数应创建用户、会话和消息表"""

        table_names = set(inspect(self.engine).get_table_names())

        self.assertTrue(
            {
                "user_accounts",
                "chat_sessions",
                "chat_messages",
            }.issubset(table_names)
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

    def test_deleting_user_cascades_sessions_and_messages(self):
        """删除用户时，其会话和消息也应被删除"""

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

            database.add(user)
            database.commit()

            database.delete(user)
            database.commit()

            session_count = database.scalar(
                select(func.count()).select_from(
                    ChatSession
                )
            )

            message_count = database.scalar(
                select(func.count()).select_from(
                    ChatMessage
                )
            )

            self.assertEqual(session_count, 0)
            self.assertEqual(message_count, 0)


if __name__ == '__main__':
    unittest.main()
