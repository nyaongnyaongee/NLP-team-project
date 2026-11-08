"""개발용 확인 화면을 한 번에 켠다.   실행: cd backend && python3 dev/dev.py [--refine]   (끄기: Ctrl+C)

정제(Claude API 호출)는 기본이 꺼짐이다. 화면 위쪽 스위치로 켜거나, --refine 을 붙이면 켠 채로 시작한다.

PostgreSQL → DB · 테이블 · 테스트 계정 → 백엔드(8000) → 확인 화면(5173) → 브라우저 순서로 켜고,
Ctrl+C 로 끄면 이 스크립트가 켠 것만 같이 끈다.  venv 를 따로 켜지 않아도 된다.
"""
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DEV = Path(__file__).resolve().parent
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
PG = "postgresql@16"
started = []  # 끌 때 정리할 프로세스


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port: int, name: str, secs: int = 20):
    for _ in range(secs * 5):
        if port_open(port):
            return
        time.sleep(0.2)
    sys.exit(f"{name} 가 {secs}초 안에 안 켜졌습니다. 로그를 확인하세요.")


def _stop(signum, frame):
    raise KeyboardInterrupt  # 터미널을 닫아도 (SIGHUP) · kill 해도 (SIGTERM) 같은 정리 경로로


def check_env():
    env = BACKEND / ".env"
    if not env.exists():
        sys.exit("backend/.env 가 없습니다. 먼저 만드세요:  copy .env.example .env  (Mac: cp)  그리고 열어서 값을 채우세요.")
    values = {}
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:  # 주석 줄은 무시
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    db = values.get("DATABASE_URL", "")
    if not db or "Mac사용자이름" in db or "비밀번호@" in db:
        sys.exit("backend/.env 의 DATABASE_URL 이 비어 있거나 예시 그대로입니다. 본인 값으로 바꾸세요 (.env.example 위쪽 안내 참고).")
    if not values.get("JWT_SECRET"):
        sys.exit("backend/.env 의 JWT_SECRET 이 비어 있습니다. 아무 긴 문자열을 넣으세요 (.env.example 안내 참고).")


def main():
    if hasattr(sys.stdout, "reconfigure"):  # 한국어 Windows 콘솔(cp949)에서 특수문자 때문에 죽지 않게
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    check_env()
    for name in ("SIGTERM", "SIGHUP", "SIGINT"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _stop)
    if not VENV_PY.exists():
        sys.exit(f"{VENV_PY} 가 없습니다. README 대로 backend/.venv 를 먼저 만드세요.")
    for port, name in ((8000, "백엔드"), (5173, "확인 화면")):
        if port_open(port):
            sys.exit(f"{port} 번 포트를 이미 쓰는 프로그램이 있습니다. 이미 켜져 있으면 그대로 브라우저로 여세요 ({name}).")

    # 1. PostgreSQL (Mac 은 brew 로 켬, Windows 는 보통 서비스가 이미 켜져 있음)
    pg_started_by_me = False
    if not port_open(5432):
        if shutil.which("brew"):
            print("PostgreSQL 켜는 중...")
            subprocess.run(["brew", "services", "run", PG], check=True, capture_output=True)
            pg_started_by_me = True
            wait_port(5432, "PostgreSQL")
        else:
            sys.exit(
                "PostgreSQL 이 꺼져 있습니다 (5432 번 포트).\n"
                "  Windows: 시작 메뉴에서 '서비스'(services.msc) → 'postgresql-x64-16' 을 찾아 [시작].\n"
                "           설치 직후에는 보통 이미 켜져 있고, 컴퓨터를 켜면 자동으로 켜집니다.\n"
                "  PostgreSQL 을 아직 설치하지 않았다면 README 의 「Windows」 절 1번부터 하세요."
            )

    try:
        # 2. DB · 테이블 (없으면 만들고, 있으면 건너뜀)
        r = subprocess.run([str(VENV_PY), str(DEV / "setup_db.py")], cwd=BACKEND)
        if r.returncode != 0:
            sys.exit(1)
        # 3. 테스트 계정 (이미 있으면 알아서 건너뜀)
        subprocess.run([str(VENV_PY), "-m", "app.db.seed"], cwd=BACKEND, capture_output=True)
        # 4. 백엔드
        refine_on = "--refine" in sys.argv  # 기본은 정제 꺼짐 (돈이 실수로 안 나가게). 화면의 스위치로 켠다
        env = {**os.environ, "DEV_TOOLS": "1", "REFINE_ENABLED": "1" if refine_on else "0"}
        started.append(subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--port", "8000"], cwd=BACKEND, env=env))
        wait_port(8000, "백엔드")
        # 5. 확인 화면 (CORS 에 허용된 5173 포트)
        started.append(subprocess.Popen(
            [sys.executable, "-m", "http.server", "5173", "--directory", str(DEV)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait_port(5173, "확인 화면")

        url = "http://localhost:5173/"
        print(f"\n켜졌습니다 → {url}   (끄기: Ctrl+C)")
        print(f"정제(Claude API): {'켜짐' if refine_on else '꺼짐 — 화면 위쪽 스위치로 켜세요'}\n")
        if "--no-open" not in sys.argv:
            webbrowser.open(url)
        while all(p.poll() is None for p in started):
            time.sleep(1)
        print("서버 하나가 종료됐습니다.")
    except KeyboardInterrupt:
        pass
    finally:
        print("\n끄는 중...")
        for p in started:
            p.terminate()
        for p in started:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        if pg_started_by_me:
            subprocess.run(["brew", "services", "stop", PG], capture_output=True)
        print("모두 껐습니다.")


if __name__ == "__main__":
    main()
