"""안 읽은 메시지 수 (목록의 unread) — 상대 글만 세고, 읽음 · 내가 보내면 0"""
import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def clean(engine, ids):
    def reset():  # 앞 시험이 남긴 읽음 위치도 지운다 (TRUNCATE 로 메시지 번호가 1 부터 다시 시작하므로)
        with engine.begin() as c:
            c.execute(text("TRUNCATE messages RESTART IDENTITY"))
            c.execute(text("UPDATE conversations SET teacher_read_id = NULL, parent_read_id = NULL"))
    reset()
    yield
    reset()


def unread(client, auth, who, conv):
    return next(c for c in client.get("/conversations", headers=auth(who)).json() if c["id"] == conv)["unread"]


def send(client, auth, who, conv, msg):
    assert client.post(f"/conversations/{conv}/messages", json={"text": msg}, headers=auth(who)).status_code == 201


def test_상대_글만_세고_읽으면_0(client, auth, ids):
    conv = ids["conv_parent1"]
    assert unread(client, auth, "teacher1", conv) == 0
    send(client, auth, "parent1", conv, "첫 번째")
    send(client, auth, "parent1", conv, "두 번째")
    assert unread(client, auth, "teacher1", conv) == 2
    assert unread(client, auth, "parent1", conv) == 0  # 내 글은 안 셈

    assert client.post(f"/conversations/{conv}/read", headers=auth("teacher1")).status_code == 204
    assert unread(client, auth, "teacher1", conv) == 0
    send(client, auth, "parent1", conv, "세 번째")
    assert unread(client, auth, "teacher1", conv) == 1


def test_답장하면_앞_글은_읽은_것(client, auth, ids):
    conv = ids["conv_parent1"]
    send(client, auth, "parent1", conv, "질문")
    send(client, auth, "teacher1", conv, "답장")
    assert unread(client, auth, "teacher1", conv) == 0
    assert unread(client, auth, "parent1", conv) == 1
    client.post(f"/conversations/{conv}/read", headers=auth("parent1"))
    assert unread(client, auth, "parent1", conv) == 0


def test_남의_대화는_읽음_처리_못_함(client, auth, ids):
    assert client.post(f"/conversations/{ids['conv_parent1']}/read", headers=auth("parent2")).status_code == 404
