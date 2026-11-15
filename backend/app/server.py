# 시연용 서버 진입점: /api 는 기존 앱(app.main.app) 그대로, 그 밖은 frontend/dist(정적 파일 + SPA 폴백)
"""실행:  cd backend && python -m uvicorn app.server:app --host 127.0.0.1 --port 8000   (워커 1개, --reload 금지)

폰 ──https/wss──▶ tailscale serve (TLS 종료) ──http/ws──▶ 이 서버 (127.0.0.1:8000)

app.main.app 의 경로 구조는 바꾸지 않는다 (테스트 · dev.py · Vite 개발 흐름 그대로). 여기서는 /api 에 마운트만 한다.
"""
import logging
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from app.core.config import settings
from app.main import app as api_app

log = logging.getLogger("server")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIST = REPO_ROOT / "frontend" / "dist"

IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
NO_DIST_MESSAGE = "frontend/dist 가 없습니다. frontend 폴더에서 npm run build 를 먼저 하세요."

# 윈도우는 레지스트리 설정에 따라 .js 를 text/plain 으로 돌려주기도 한다 → 자주 쓰는 형식은 직접 정한다
MEDIA_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webmanifest": "application/manifest+json",
    ".json": "application/json",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
}
NO_CACHE_FILES = {"index.html", "sw.js", "manifest.webmanifest"}


class GuardAndHeaders:
    """(1) dev_tools 가 꺼져 있으면 /api/dev/ 이하는 기존 앱에 넘기지 않고 404.  (2) 모든 응답에 최소 보안 헤더.
    설정은 요청 시점에 읽는다 (messages.py 의 검사와 같은 방식)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.inner(scope, receive, send)
            return

        path = re.sub(r"/+", "/", scope.get("path", ""))
        if (path == "/api/dev" or path.startswith("/api/dev/")) and not settings.dev_tools:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            response = JSONResponse({"detail": "Not Found"}, status_code=404)
            await response(scope, receive, self._with_headers(send))
            return

        await self.inner(scope, receive, self._with_headers(send) if scope["type"] == "http" else send)

    @staticmethod
    def _with_headers(send):
        async def wrapped(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                names = {k.lower() for k, _ in headers}
                if b"x-content-type-options" not in names:
                    headers.append((b"x-content-type-options", b"nosniff"))
                if b"referrer-policy" not in names:
                    headers.append((b"referrer-policy", b"same-origin"))
                message = {**message, "headers": headers}
            await send(message)

        return wrapped


def create_server(dist_dir: Path | None) -> GuardAndHeaders:
    root = Path(dist_dir).resolve() if dist_dir else None
    index = root / "index.html" if root else None
    has_dist = bool(index and index.is_file())
    if not has_dist:
        log.warning("정적 파일 폴더가 없습니다 (%s). /api 만 동작합니다. npm run build 를 하세요.", dist_dir)

    server = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    server.mount("/api", api_app)  # HTTP 와 WebSocket(/api/ws) 모두 지나간다

    def index_response() -> Response:
        return FileResponse(index, media_type=MEDIA_TYPES[".html"], headers={"Cache-Control": NO_CACHE})

    @server.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def static(request: Request, full_path: str):
        if not has_dist:
            return PlainTextResponse(NO_DIST_MESSAGE, status_code=503)

        rel = full_path.lstrip("/")
        if rel in ("", "index.html"):
            return index_response()

        candidate = (root / rel).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():  # ".." 로 dist 밖을 읽지 못하게
            headers = {}
            if rel in NO_CACHE_FILES:
                headers["Cache-Control"] = NO_CACHE
            elif rel.startswith("assets/"):
                headers["Cache-Control"] = IMMUTABLE
            return FileResponse(
                candidate, media_type=MEDIA_TYPES.get(candidate.suffix.lower()), headers=headers
            )

        # 확장자가 있는데 없는 파일은 404 (깨진 자바스크립트를 HTML 로 받는 사고 방지)
        if Path(rel).suffix:
            return PlainTextResponse("Not Found", status_code=404)
        return index_response()  # /teacher, /parent/notices/3 같은 화면 주소 → SPA 폴백

    return GuardAndHeaders(server)


app = create_server(DEFAULT_DIST)
