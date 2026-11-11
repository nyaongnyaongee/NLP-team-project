"""A-1 top-level message intake and lookup routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer

from app.schemas.message import MessageAcceptedOut, MessageIntakeIn, MessageOut
from app.services.message_intake import (
    ExistingMessageReader,
    JobRegistrationError,
    MessageStorageError,
)

router = APIRouter(tags=["messages"])
_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def get_a1_db():
    """Use A-2's existing session lifecycle, imported when a request arrives."""
    from app.db.database import get_db

    yield from get_db()


def get_a1_user(token: str | None = Depends(_oauth2), db=Depends(get_a1_db)):
    """Use the same JWT verification as the conversation message routes."""
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.auth import user_from_token

    try:
        user = user_from_token(token, db)
    except SQLAlchemyError:
        raise HTTPException(503, detail={"code": "storage_unavailable"}) from None
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다")
    return user


def get_a1_reader() -> ExistingMessageReader:
    return ExistingMessageReader()


def _rollback(db) -> None:
    try:
        db.rollback()
    except Exception:
        # The request still returns a sanitized error; session close is next.
        pass


async def safe_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Keep A-1 validation private without changing other routes' errors."""
    if request.url.path != "/messages":
        return await request_validation_exception_handler(request, exc)
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": "invalid_request"}},
        headers={"Cache-Control": "no-store"},
    )


@router.post("/messages", response_model=MessageAcceptedOut, status_code=202)
def submit_message(
    body: MessageIntakeIn,
    request: Request,
    response: Response,
    db=Depends(get_a1_db),
    user=Depends(get_a1_user),
    reader: ExistingMessageReader = Depends(get_a1_reader),
):
    response.headers["Cache-Control"] = "no-store"
    if user["role"] != "parent":
        raise HTTPException(403, "학부모만 메시지를 접수할 수 있습니다")

    service = getattr(request.app.state, "message_intake_service", None)
    if service is None:
        raise HTTPException(503, detail={"code": "job_store_unavailable"})

    try:
        reader.assert_participant(db, body.conversation_id, user)
        receipt = service.submit_message(db, body.conversation_id, user["id"], body.text)
    except MessageStorageError:
        _rollback(db)
        raise HTTPException(503, detail={"code": "storage_unavailable"}) from None
    except JobRegistrationError:
        _rollback(db)
        raise HTTPException(503, detail={"code": "job_registration_failed"}) from None
    except HTTPException:
        raise
    except Exception:
        _rollback(db)
        raise HTTPException(500, detail={"code": "internal_error"}) from None

    return MessageAcceptedOut(
        id=receipt.id, conversation_id=receipt.conversation_id, status=receipt.status
    )


@router.get("/messages", response_model=list[MessageOut])
def list_messages(
    response: Response,
    conversation_id: int = Query(..., gt=0),
    db=Depends(get_a1_db),
    user=Depends(get_a1_user),
    reader: ExistingMessageReader = Depends(get_a1_reader),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        reader.assert_participant(db, conversation_id, user)
        return reader.list_visible(db, conversation_id, user)
    except MessageStorageError:
        raise HTTPException(503, detail={"code": "storage_unavailable"}) from None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(500, detail={"code": "internal_error"}) from None
