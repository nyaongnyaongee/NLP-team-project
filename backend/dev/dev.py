"""개발용 확인 화면을 한 번에 켠다.   실행: cd backend && python3 dev/dev.py   (끄기: Ctrl+C)

PostgreSQL → 백엔드(8000) → 확인 화면(5173) → 브라우저 순서로 켜고,
Ctrl+C 로 끄면 이 스크립트가 켠 것만 같이 끈다.  venv 를 따로 켜지 않아도 된다.
"""
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


def main():
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
            sys.exit("PostgreSQL 이 꺼져 있습니다. Windows 는 서비스(services.msc)에서 postgresql 을 시작하세요.")

    try:
        # 2. 테스트 계정 (이미 있으면 알아서 건너뜀)
        subprocess.run([str(VENV_PY), "-m", "app.db.seed"], cwd=BACKEND, capture_output=True)
        # 3. 백엔드
        started.append(subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--port", "8000"], cwd=BACKEND))
        wait_port(8000, "백엔드")
        # 4. 확인 화면 (CORS 에 허용된 5173 포트)
        started.append(subprocess.Popen(
            [sys.executable, "-m", "http.server", "5173", "--directory", str(DEV)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait_port(5173, "확인 화면")

        url = "http://localhost:5173/"
        print(f"\n켜졌습니다 → {url}   (끄기: Ctrl+C)\n")
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
