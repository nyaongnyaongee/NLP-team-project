# 앱 생성, CORS, 라우터 등록  [채원]
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, drafts, message_intake, messages, ws

app = FastAPI(title="이음")
app.state.message_intake_service = None  # A-2/A-3의 영속 작업 등록 구현이 연결되면 설정
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(auth.router)
app.include_router(messages.router)
app.include_router(message_intake.router)
app.include_router(drafts.router)
app.include_router(ws.router)
app.add_exception_handler(RequestValidationError, message_intake.safe_validation_error)


@app.get("/health")
def health():
    return {"ok": True}
