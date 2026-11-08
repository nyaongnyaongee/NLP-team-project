# 비밀번호 해시, 토큰 (시험용 — 표준 라이브러리만)  [채원]
import base64, hashlib, hmac, json, os, time

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import crud
from app.db.database import get_db

TOKEN_SECONDS = 12 * 3600
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
    body = base64.urlsafe_b64encode(json.dumps({"uid": user_id, "exp": time.time() + TOKEN_SECONDS}).encode())
    return body.decode() + "." + _sign(body)


def current_user(token: str | None = Depends(_oauth2), db: Session = Depends(get_db)):
    unauthorized = HTTPException(401, "로그인이 필요합니다")
    if token is None:
        raise unauthorized
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(body.encode())):
            raise unauthorized
        data = json.loads(base64.urlsafe_b64decode(body))
    except (ValueError, TypeError):
        raise unauthorized
    if data["exp"] < time.time():
        raise unauthorized
    user = crud.get_user(db, data["uid"])
    if user is None:
        raise unauthorized
    return user
