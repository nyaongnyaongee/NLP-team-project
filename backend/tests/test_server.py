"""시연용 진입점(app.server): /api 마운트 + 정적 파일 + SPA 폴백 + dev 차단 + 보안 헤더"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.server import create_server


@pytest.fixture
def dist(tmp_path):
    (tmp_path / "secret.txt").write_text("밖에 있는 파일", encoding="utf-8")  # dist 밖
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "assets" / "a.js").write_text("console.log(1)", encoding="utf-8")
    (d / "index.html").write_text("<!doctype html><title>이음</title>", encoding="utf-8")
    (d / "sw.js").write_text("// sw", encoding="utf-8")
    (d / "manifest.webmanifest").write_text("{}", encoding="utf-8")
    return d


@pytest.fixture
def web(dist, ids):
    return TestClient(create_server(dist))


def test_api_아래에서_기존_앱이_동작한다(web, ids):
    assert web.get("/api/health").status_code == 200
    r = web.post("/api/auth/login", json={"login_id": "teacher1", "password": "pw1234"})
    assert r.status_code == 200 and "token" in r.json()


@pytest.mark.parametrize("path", ["/", "/teacher", "/parent/notices/3", "/index.html"])
def test_화면_주소는_index_html_을_돌려준다(web, path):
    r = web.get(path)
    assert r.status_code == 200
    assert "이음" in r.text
    assert r.headers["cache-control"] == "no-cache"


def test_assets_는_오래_캐시하고_없는_파일은_404(web):
    r = web.get("/assets/a.js")
    assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]
    assert "javascript" in r.headers["content-type"]
    r = web.get("/assets/none.js")
    assert r.status_code == 404
    assert "<title>" not in r.text  # index.html 로 폴백하면 안 된다


@pytest.mark.parametrize("path", ["/sw.js", "/manifest.webmanifest"])
def test_서비스워커와_매니페스트는_캐시하지_않는다(web, path):
    r = web.get(path)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"


def test_sw_js_는_자바스크립트로_나간다(web):
    assert "javascript" in web.get("/sw.js").headers["content-type"]


def test_없는_api_경로는_JSON_404(web):
    r = web.get("/api/없는경로")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_dev_는_꺼져_있으면_404_켜져_있으면_통과(web, monkeypatch):
    monkeypatch.setattr(settings, "dev_tools", False)
    assert web.post("/api/dev/reset").status_code == 404
    assert web.get("/api/dev/refine").status_code == 404
    assert web.delete("/api/dev/anything").status_code == 404
    assert web.post("/api//dev//reset").status_code == 404
    monkeypatch.setattr(settings, "dev_tools", True)
    r = web.get("/api/dev/refine")  # 기존 앱까지 도달
    assert r.status_code == 200 and "enabled" in r.json()


def test_dist_가_없어도_api_는_산다(tmp_path, ids):
    web = TestClient(create_server(tmp_path / "없음"))
    assert web.get("/api/health").status_code == 200
    r = web.get("/")
    assert r.status_code in (404, 503)
    assert "npm run build" in r.text


def test_보안_헤더와_HEAD(web):
    r = web.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "same-origin"
    assert web.get("/api/health").headers["x-content-type-options"] == "nosniff"
    assert web.head("/").status_code == 200
    assert web.head("/assets/a.js").status_code == 200


def test_dist_밖의_파일은_읽을_수_없다(web):
    for p in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
        r = web.get(p)
        assert "밖에 있는 파일" not in r.text


def test_api_ws_로_연결되면_ready(web, auth):
    token = auth("teacher1")["Authorization"].split(" ", 1)[1]
    with web.websocket_connect("/api/ws") as ws:
        ws.send_json({"token": token})
        assert ws.receive_json() == {"type": "ready"}
