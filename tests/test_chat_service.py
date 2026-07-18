import unittest
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.bootstrap import create_schema
from app.core.database import Base, build_engine
from app.models.entities import (
    MESSAGE_ROLE_ASSISTANT,
    MESSAGE_ROLE_USER,
    ROLE_USER,
    ChatMessage,
    ChatSession,
)
from app.services.chat_service import (
    MAX_MESSAGE_LENGTH,
    MAX_TITLE_LENGTH,
    ChatSessionNotFoundError,
    create_chat_message,
    create_chat_session,
    get_chat_history,
)
from app.services.user_service import create_user


class ChatServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = build_engine(
            "sqlite+pysqlite:///:memory:",
        )

        create_schema(self.engine)

        self.SessionTesting = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

        with self.SessionTesting() as database:
            self.owner = create_user(
                database,
                username="owner",
                display_name="Owner",
                password="owner-password-2026",
                roles={ROLE_USER},
            )

            self.other = create_user(
                database,
                username="other",
                display_name="Other",
                password="other-password-2026",
                roles={ROLE_USER},
            )

            database.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

        self.engine.dispose()

    def test_create_session_generates_public_uuid_and_owner(self):
        with self.SessionTesting() as database:
            chat_session = create_chat_session(
                database,
                owner=self.owner,
                title="  First conversation  ",
            )

            database.commit()

        self.assertEqual(
            chat_session.title,
            "First conversation",
        )

        self.assertEqual(
            chat_session.user_id,
            self.owner.id,
        )

        self.assertEqual(
            str(UUID(chat_session.public_id)),
            chat_session.public_id,
        )

    def test_service_supports_user_and_assistant_messages_in_order(
        self,
    ):
        with self.SessionTesting() as database:
            chat_session = create_chat_session(
                database,
                owner=self.owner,
                title="History",
            )

            create_chat_message(
                database,
                owner=self.owner,
                session_public_id=chat_session.public_id,
                role=MESSAGE_ROLE_USER,
                content="Hello",
            )

            create_chat_message(
                database,
                owner=self.owner,
                session_public_id=chat_session.public_id,
                role=MESSAGE_ROLE_ASSISTANT,
                content="Hi there",
            )

            database.commit()

            history = get_chat_history(
                database,
                owner=self.owner,
                session_public_id=chat_session.public_id,
            )

        self.assertEqual(
            [(item.role, item.content) for item in history.messages],
            [
                ("user", "Hello"),
                ("assistant", "Hi there"),
            ],
        )

    def test_unknown_role_is_rejected(self):
        with self.SessionTesting() as database:
            chat_session = create_chat_session(
                database,
                owner=self.owner,
                title="Roles",
            )

            with self.assertRaises(ValueError):
                create_chat_message(
                    database,
                    owner=self.owner,
                    session_public_id=chat_session.public_id,
                    role="system",
                    content="Not allowed",
                )

    def test_another_owner_cannot_read_session(self):
        with self.SessionTesting() as database:
            chat_session = create_chat_session(
                database,
                owner=self.owner,
                title="Private",
            )

            database.commit()

            with self.assertRaises(ChatSessionNotFoundError):
                get_chat_history(
                    database,
                    owner=self.other,
                    session_public_id=chat_session.public_id,
                )

    def test_blank_message_is_not_persisted(self):
        with self.SessionTesting() as database:
            chat_session = create_chat_session(
                database,
                owner=self.owner,
                title="Blank",
            )

            with self.assertRaises(ValueError):
                create_chat_message(
                    database,
                    owner=self.owner,
                    session_public_id=chat_session.public_id,
                    role=MESSAGE_ROLE_USER,
                    content="   ",
                )

            count = database.scalar(select(func.count()).select_from(ChatMessage))

        self.assertEqual(count, 0)

    def test_overlong_title_is_not_persisted(self):
        with self.SessionTesting() as database:
            with self.assertRaisesRegex(
                ValueError,
                f"Title must not exceed {MAX_TITLE_LENGTH} characters.",
            ):
                create_chat_session(
                    database,
                    owner=self.owner,
                    title="a" * (MAX_TITLE_LENGTH + 1),
                )

            count = database.scalar(select(func.count()).select_from(ChatSession))

        self.assertEqual(count, 0)

    def test_overlong_message_is_not_persisted(self):
        with self.SessionTesting() as database:
            chat_session = create_chat_session(
                database,
                owner=self.owner,
                title="Length limit",
            )

            with self.assertRaisesRegex(
                ValueError,
                (f"Message content must not exceed {MAX_MESSAGE_LENGTH} characters."),
            ):
                create_chat_message(
                    database,
                    owner=self.owner,
                    session_public_id=chat_session.public_id,
                    role=MESSAGE_ROLE_USER,
                    content="a" * (MAX_MESSAGE_LENGTH + 1),
                )

            count = database.scalar(select(func.count()).select_from(ChatMessage))

        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
