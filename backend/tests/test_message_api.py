"""A-1 HTTP contract tests without PostgreSQL or a paid AI call."""

import asyncio
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import anyio.to_thread
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.routers import message_intake
from app.services.message_intake import JobRegistrationError, MessageReceipt, MessageStorageError


class FakeDB:
    def __init__(self):
        self.rows = []
        self.jobs = []
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class FakeReader:
    error = None

    def assert_participant(self, db, conversation_id, user):
        if self.error:
            raise self.error
        if conversation_id != 7 or user["id"] not in (1, 2):
            raise HTTPException(404, "대화를 찾을 수 없습니다")

    def list_visible(self, db, conversation_id, user):
        if self.error:
            raise self.error
        result = []
        for row in db.rows:
            if row["conversation_id"] != conversation_id:
                continue
            visible = row.copy()
            if user["role"] == "teacher":
                visible["raw_text"] = None
                if visible["analysis"]:
                    visible["analysis"] = {
                        k: v for k, v in visible["analysis"].items() if k != "quotes"
                    }
            else:
                visible["refined_text"] = None
                visible["analysis"] = None
            result.append(visible)
        return result


class FakeIntakeService:
    error = None

    def submit_message(self, db, conversation_id, sender_id, raw_text):
        if self.error:
            raise self.error
        message_id = len(db.rows) + 1
        db.rows.append({
            "id": message_id,
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "raw_text": raw_text,
            "refined_text": None,
            "analysis": None,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        })
        db.jobs.append(message_id)
        return MessageReceipt(id=message_id, conversation_id=conversation_id)


class APIClient:
    """Call ASGI directly; this sandbox cannot use TestClient's thread portal."""

    def __init__(self, app):
        self.app = app

    def request(self, method, path, **kwargs):
        async def inline_sync(func, *args, **kw):
            return func(*args)

        async def send():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app), base_url="http://testserver"
            ) as client:
                return await client.request(method, path, **kwargs)

        with patch.object(anyio.to_thread, "run_sync", inline_sync):
            return asyncio.run(send())

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)


class MessageAPITests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.reader = FakeReader()
        self.service = FakeIntakeService()
        self.app = FastAPI()
        self.app.include_router(message_intake.router)
        self.app.add_exception_handler(RequestValidationError, message_intake.safe_validation_error)

        async def fake_db():
            return self.db

        async def fake_user(request: Request):
            token = request.headers.get("Authorization")
            if token == "Bearer parent":
                return {"id": 1, "role": "parent"}
            if token == "Bearer teacher":
                return {"id": 2, "role": "teacher"}
            if token == "Bearer outsider":
                return {"id": 3, "role": "parent"}
            raise HTTPException(401, "로그인이 필요합니다")

        async def fake_reader():
            return self.reader

        self.app.dependency_overrides[message_intake.get_a1_db] = fake_db
        self.app.dependency_overrides[message_intake.get_a1_user] = fake_user
        self.app.dependency_overrides[message_intake.get_a1_reader] = fake_reader
        self.client = APIClient(self.app)

    def test_post_accepts_only_after_message_and_job_are_registered(self):
        self.app.state.message_intake_service = self.service
        raw = "아이의 안전 문제를 확인해 주세요."
        accepted = self.client.post(
            "/messages", json={"conversation_id": 7, "text": raw},
            headers={"Authorization": "Bearer parent"},
        )
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(accepted.json(), {"id": 1, "conversation_id": 7, "status": "pending"})
        self.assertEqual(accepted.headers["cache-control"], "no-store")
        self.assertEqual(self.db.rows[0]["raw_text"], raw)
        self.assertEqual(self.db.jobs, [1])
        self.assertNotIn(raw, accepted.text)

        teacher = self.client.get(
            "/messages", params={"conversation_id": 7},
            headers={"Authorization": "Bearer teacher"},
        )
        self.assertEqual(teacher.status_code, 200)
        self.assertEqual(teacher.json()[0]["status"], "pending")
        self.assertIsNone(teacher.json()[0]["raw_text"])
        self.assertNotIn(raw, teacher.text)

        self.db.rows[0].update(status="done", refined_text="안전 문제 확인을 부탁드립니다.",
                               analysis={"topic": "안전", "quotes": [raw]})
        completed = self.client.get(
            "/messages", params={"conversation_id": 7},
            headers={"Authorization": "Bearer teacher"},
        )
        self.assertEqual(completed.json()[0]["refined_text"], "안전 문제 확인을 부탁드립니다.")
        self.assertNotIn(raw, completed.text)
        self.assertNotIn("quotes", completed.json()[0]["analysis"])

    def test_input_and_access_rules(self):
        self.app.state.message_intake_service = self.service
        headers = {"Authorization": "Bearer parent"}
        for body in (
            {"conversation_id": 7, "text": ""},
            {"conversation_id": 7, "text": " \n "},
            {"conversation_id": 0, "text": "확인"},
            {"conversation_id": 7, "text": "x" * 10001},
            {"conversation_id": 7, "text": "확인", "extra": "개인정보"},
        ):
            response = self.client.post("/messages", json=body, headers=headers)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {"detail": {"code": "invalid_request"}})
            self.assertNotIn("개인정보", response.text)
        self.assertFalse(self.db.rows)
        self.assertEqual(self.client.post("/messages", json={"conversation_id": 7, "text": "확인"}).status_code, 401)
        self.assertEqual(self.client.post("/messages", json={"conversation_id": 7, "text": "확인"},
                                          headers={"Authorization": "Bearer teacher"}).status_code, 403)
        self.assertEqual(self.client.get("/messages", params={"conversation_id": 7}).status_code, 401)
        self.assertEqual(self.client.get("/messages", params={"conversation_id": 7},
                                         headers={"Authorization": "Bearer outsider"}).status_code, 404)
        self.assertEqual(self.client.post("/messages", json={"conversation_id": 7, "text": "확인"},
                                          headers={"Authorization": "Bearer outsider"}).status_code, 404)
        self.assertEqual(self.client.get("/messages", params={"conversation_id": 0},
                                         headers=headers).status_code, 422)

    def test_unconfigured_post_never_claims_to_store(self):
        response = self.client.post(
            "/messages", json={"conversation_id": 7, "text": "확인"},
            headers={"Authorization": "Bearer parent"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": {"code": "job_store_unavailable"}})
        self.assertFalse(self.db.rows)
        self.assertFalse(self.db.jobs)
        lookup = self.client.get(
            "/messages", params={"conversation_id": 7},
            headers={"Authorization": "Bearer teacher"},
        )
        self.assertEqual(lookup.status_code, 200)
        self.assertEqual(lookup.json(), [])

    def test_storage_and_job_failures_are_distinct(self):
        self.app.state.message_intake_service = self.service
        for error, code in (
            (MessageStorageError("비밀 원문"), "storage_unavailable"),
            (JobRegistrationError("비밀 원문"), "job_registration_failed"),
        ):
            self.service.error = error
            response = self.client.post(
                "/messages", json={"conversation_id": 7, "text": "비밀 원문"},
                headers={"Authorization": "Bearer parent"},
            )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {"detail": {"code": code}})
            self.assertNotIn("비밀 원문", response.text)
        self.assertEqual(self.db.rollbacks, 2)
        self.assertFalse(self.db.rows)
        self.assertFalse(self.db.jobs)

        self.reader.error = MessageStorageError("비밀 원문")
        response = self.client.get(
            "/messages", params={"conversation_id": 7},
            headers={"Authorization": "Bearer teacher"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": {"code": "storage_unavailable"}})


if __name__ == "__main__":
    unittest.main()
