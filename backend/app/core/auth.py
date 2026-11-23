# 비밀번호 해시, 토큰 (시험용 — 표준 라이브러리만)  [채원]
import base64, hashlib, hmac, json, os, time

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud
from app.db.database import get_db

TOKEN_SECONDS = 12 * 3600
# 서버를 켤 때마다 바뀌는 값. dev.py(DEV_TOOLS=1) 로 켰을 때만 토큰에 넣고 확인한다 → 서버를 다시 켜면 모두 로그아웃 (개발 · 시험용).
# 시연 서버(app.server, DEV_TOOLS 꺼짐)는 확인하지 않는다: 재시작돼도 관객(손님 학부모, 비밀번호 없음)이 쫓겨나지 않게.
BOOT_ID = os.urandom(8).hex()
_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)  # /docs 의 Authorize 가 아이디·비번 입력창이 됨


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + "$" + h.hex()


def verify_password(pw: str, stored: str) -> bool:
    salt, h = stored.split("$")
    cand = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000)
    return hmac.compare_digest(cand.hex(), h)


def _sign(body: bytes) -> str:
    return hmac.new(settings.jwt_secret.encode(), body, hashlib.sha256).hexdigest()


def make_token(user_id: int) -> str:
    data = {"uid": user_id, "exp": time.time() + TOKEN_SECONDS}
    if settings.dev_tools:
        data["boot"] = BOOT_ID
    body = base64.urlsafe_b64encode(json.dumps(data).encode())
    return body.decode() + "." + _sign(body)


def user_from_token(token: str | None, db: Session):
    """토큰이 맞으면 사용자, 아니면 None.  HTTP(current_user) 와 WebSocket(routers/ws.py) 이 같이 쓴다."""
    if not token:
        return None
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(body.encode())):
            return None
        data = json.loads(base64.urlsafe_b64decode(body))
        if data["exp"] < time.time():
            return None
        if settings.dev_tools and data.get("boot") != BOOT_ID:
            return None  # 서버를 다시 켜기 전에 받은 토큰 (dev.py 만)
        return crud.get_user(db, data["uid"])
    except (ValueError, TypeError, KeyError):
        return None


def current_user(token: str | None = Depends(_oauth2), db: Session = Depends(get_db)):
    user = user_from_token(token, db)
    if user is None:
        raise HTTPException(401, "로그인이 필요합니다")
    return user
