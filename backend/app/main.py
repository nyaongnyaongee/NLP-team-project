# 앱 생성, CORS, 라우터 등록  [채원]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, conversations, drafts, events, messages, notices, reports, students, todos, ws

app = FastAPI(title="이음")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"]
)
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(drafts.router)
app.include_router(todos.router)
app.include_router(events.router)
app.include_router(notices.router)
app.include_router(reports.router)
app.include_router(students.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    return {"ok": True}
