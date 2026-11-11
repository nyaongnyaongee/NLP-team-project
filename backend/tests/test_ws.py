"""WebSocket 알림 — 대화가 바뀌면 그 대화의 두 사람에게만 {"type":"changed","conversation_id":N}"""
import pytest
from starlette.websockets import WebSocketDisconnect

from app.routers import messages as messages_router

pytestmark = pytest.mark.usefixtures("clean_messages")

REAL_BACKGROUND = messages_router._refine_in_background


def token(auth, who):
    return auth(who)["Authorization"].split(" ", 1)[1]


def connect(client, auth, who):
    ws = client.websocket_connect("/ws")
    conn = ws.__enter__()
    conn.send_json({"token": token(auth, who)})
    assert conn.receive_json() == {"type": "ready"}
    return ws, conn


def send(client, auth, who, conv, text="안녕하세요"):
    r = client.post(f"/conversations/{conv}/messages", json={"text": text}, headers=auth(who))
    assert r.status_code == 201
    return r.json()


def test_메시지를_보내면_두_사람_모두_알림을_받고_내용은_없다(client, auth, ids):
    conv = ids["conv_parent1"]
    t_ctx, teacher = connect(client, auth, "teacher1")
    p_ctx, parent = connect(client, auth, "parent1")
    try:
        send(client, auth, "teacher1", conv, "내일 준비물은 색연필입니다")
        assert teacher.receive_json() == {"type": "changed", "conversation_id": conv}
        assert parent.receive_json() == {"type": "changed", "conversation_id": conv}  # 글 내용 · 원문은 알림에 없다
    finally:
        t_ctx.__exit__(None, None, None)
        p_ctx.__exit__(None, None, None)


def test_남의_대화_알림은_안_온다(client, auth, ids):
    ctx, parent2 = connect(client, auth, "parent2")
    try:
        send(client, auth, "teacher1", ids["conv_parent1"])  # parent1 대화 → parent2 는 받으면 안 됨
        send(client, auth, "teacher1", ids["conv_parent2"])
        assert parent2.receive_json()["conversation_id"] == ids["conv_parent2"]  # 첫 알림이 자기 대화 것
    finally:
        ctx.__exit__(None, None, None)


def test_정제가_끝나면_또_알린다(client, auth, ids, monkeypatch):
    monkeypatch.setattr(messages_router, "_refine_in_background", REAL_BACKGROUND)
    monkeypatch.setitem(messages_router._refine_state, "enabled", False)  # Claude 없이 바로 failed 로 끝남
    conv = ids["conv_parent1"]
    ctx, teacher = connect(client, auth, "teacher1")
    try:
        send(client, auth, "parent1", conv)
        assert teacher.receive_json()["conversation_id"] == conv  # 저장됨 (정제 중)
        assert teacher.receive_json()["conversation_id"] == conv  # 정제 끝 (여기선 꺼져 있어 failed)
    finally:
        ctx.__exit__(None, None, None)


@pytest.mark.parametrize("first", [{"token": "가짜.토큰"}, {"nothing": 1}])
def test_토큰이_틀리면_끊는다(client, first):
    with client.websocket_connect("/ws") as ws:
        ws.send_json(first)
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
        assert e.value.code == 1008


def test_연결한_사람이_없으면_알림은_아무_일도_안_한다(ids):
    from app.routers.ws import Hub

    Hub().notify_conversation(ids["conv_parent1"])  # 루프도 연결도 없음 → 오류 없이 지나감
