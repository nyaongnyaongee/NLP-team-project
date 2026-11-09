# WebSocket 알림  [채원]  (시험용으로 재관이 채움)
"""대화가 바뀌면(메시지 저장 · 정제 끝 · 답장 추천 붙음) 그 대화의 교사 · 학부모에게 알린다.

    연결:  ws://localhost:8000/ws  → 열리면 첫 메시지로 {"token": "<로그인 토큰>"}
           (토큰을 주소에 넣지 않는다: 주소는 서버 로그에 남는다)
    받는 것: {"type": "changed", "conversation_id": 3}

알림에는 내용을 넣지 않는다. 받은 쪽은 GET /conversations/{id}/messages 로 다시 읽는다.
그래야 원문을 거르는 곳이 messages._view 한 곳으로 남는다.

시연용: 서버 1대 · 프로세스 1개 기준 (연결 목록이 메모리에 있음). 여러 대로 늘리면 Redis 같은 중계가 필요하다.
"""
import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.auth import user_from_token
from app.db import crud
from app.db.database import SessionLocal

log = logging.getLogger("routers.ws")
router = APIRouter(tags=["ws"])

TOKEN_WAIT_SECONDS = 5


class Hub:
    """사용자 id → 열린 연결들. 목록은 이벤트 루프 스레드에서만 고친다."""

    def __init__(self):
        self.conns: dict[int, set[WebSocket]] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def add(self, user_id: int, ws: WebSocket) -> None:
        self.loop = asyncio.get_running_loop()
        self.conns.setdefault(user_id, set()).add(ws)

    def remove(self, user_id: int, ws: WebSocket) -> None:
        group = self.conns.get(user_id)
        if group:
            group.discard(ws)
            if not group:
                del self.conns[user_id]

    async def _send(self, user_ids: list[int], data: dict) -> None:
        for uid in user_ids:
            for ws in list(self.conns.get(uid, ())):
                try:
                    await ws.send_json(data)
                except Exception:  # 끊긴 연결은 버린다
                    self.remove(uid, ws)

    def notify_conversation(self, conv_id: int) -> None:
        """어느 스레드에서 불러도 된다 (요청 처리 · 백그라운드 정제). 기다리지 않고 바로 돌아온다.
        알림이 실패해도 부른 쪽 일(저장 등)에는 영향이 없다 — 화면은 끊기면 2초마다 다시 읽는다."""
        loop = self.loop
        if loop is None or not self.conns or loop.is_closed():
            return  # 연결한 사람이 없으면 DB 도 안 본다
        try:
            with SessionLocal() as db:
                conv = crud.get_conversation(db, conv_id)
            if conv is None:
                return
            asyncio.run_coroutine_threadsafe(
                self._send([conv["teacher_id"], conv["parent_id"]], {"type": "changed", "conversation_id": conv_id}),
                loop)
        except Exception:
            log.exception("알림 보내기 실패 (대화 %s)", conv_id)


hub = Hub()


def _check_token(token):
    with SessionLocal() as db:
        return user_from_token(token, db)


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_json(), TOKEN_WAIT_SECONDS)
        token = first.get("token") if isinstance(first, dict) else None
    except (asyncio.TimeoutError, ValueError, WebSocketDisconnect):
        token = None
    user = await run_in_threadpool(_check_token, token) if token else None
    if user is None:
        await websocket.close(code=1008, reason="로그인이 필요합니다")
        return

    hub.add(user["id"], websocket)
    await websocket.send_json({"type": "ready"})
    try:
        while True:  # 화면이 보내는 것은 없다. 연결이 끊길 때까지 기다린다
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(user["id"], websocket)
