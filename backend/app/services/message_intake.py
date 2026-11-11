"""A-1 contract for A-2 persistence and a durable A-3 refinement job."""

from dataclasses import dataclass
from typing import Literal, Protocol

from fastapi import HTTPException


@dataclass(frozen=True)
class MessageReceipt:
    id: int
    conversation_id: int
    status: Literal["pending"] = "pending"


class MessageStorageError(Exception):
    """A database write or read failed."""


class JobRegistrationError(Exception):
    """A durable refinement job could not be registered."""


class MessageIntakeService(Protocol):
    def submit_message(
        self, db, conversation_id: int, sender_id: int, raw_text: str
    ) -> MessageReceipt:
        """Commit a message and its A-3 job atomically, then return.

        Use the existing integer message ID and pending status. The A-3 worker
        must be able to find the committed job after an API process restart.
        Do not use crud.add_message here: it commits before a job can be added.
        Roll back both writes and raise JobRegistrationError if enqueue fails.
        A stopped worker does not prevent acceptance after this commit.
        Never call the AI model in this request.
        """


class ExistingMessageReader:
    """Reuse the team's A-2 CRUD and existing role-based response policy."""

    def assert_participant(self, db, conversation_id: int, user) -> None:
        from sqlalchemy.exc import SQLAlchemyError

        from app.routers.messages import _my_conversation

        try:
            _my_conversation(db, conversation_id, user)
        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            raise MessageStorageError from exc

    def list_visible(self, db, conversation_id: int, user) -> list[dict]:
        from sqlalchemy.exc import SQLAlchemyError

        from app.db import crud
        from app.routers.messages import _view

        try:
            return [_view(row, user) for row in crud.list_messages(db, conversation_id)]
        except SQLAlchemyError as exc:
            raise MessageStorageError from exc
