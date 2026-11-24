"""dev.py(DEV_TOOLS=1) 로 켠 서버는 다시 켜면 예전 토큰을 받지 않는다 (= 모두 로그아웃). 시연 서버는 그대로 받는다."""
import app.core.auth as auth
from app.core.config import settings


def _fake_user(monkeypatch):
    monkeypatch.setattr(auth.crud, "get_user", lambda db, uid: {"id": uid})


def test_dev_서버를_다시_켜면_예전_토큰은_안_된다(monkeypatch):
    _fake_user(monkeypatch)
    monkeypatch.setattr(settings, "dev_tools", True)
    token = auth.make_token(7)
    assert auth.user_from_token(token, db=None) == {"id": 7}
    monkeypatch.setattr(auth, "BOOT_ID", "다시-켠-서버")
    assert auth.user_from_token(token, db=None) is None


def test_시연_서버는_다시_켜도_토큰이_그대로(monkeypatch):
    _fake_user(monkeypatch)
    monkeypatch.setattr(settings, "dev_tools", False)
    token = auth.make_token(7)
    monkeypatch.setattr(auth, "BOOT_ID", "다시-켠-서버")
    assert auth.user_from_token(token, db=None) == {"id": 7}
