#!/usr/bin/env bash
# 이음 시연 서버 (맥) — 공개 주소(Tailscale Funnel) + QR
#
#   켜기:  bash deploy/start-demo-mac.sh            (프런트를 새로 빌드하려면 --build)
#   끄기:  Ctrl+C  → 공개 주소 닫기 · 백엔드 끄기 · (이 스크립트가 켠 경우만) PostgreSQL 끄기
#
# 폰 ─https/wss─▶ tailscale funnel (공개 :443) ─http/ws─▶ uvicorn app.server:app (127.0.0.1:8000)
#
# Funnel 은 serve 와 달리 **인터넷 누구나** 접속할 수 있다 (관객 폰에 Tailscale 이 필요 없게).
# 그래서 이 스크립트는 앞에 떠 있는 동안만 공개하고, 끝나면 반드시 닫는다.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOG_DIR="$ROOT/deploy/logs"
PORT=8000
BASE="http://127.0.0.1:$PORT"
PY="$BACKEND/.venv/bin/python"
PG_BIN="/opt/homebrew/opt/postgresql@16/bin"

BUILD=0
for a in "$@"; do
  case "$a" in
    --build) BUILD=1 ;;
    -h|--help) sed -n 2,10p "$0"; exit 0 ;;
    *) echo "모르는 옵션: $a" >&2; exit 2 ;;
  esac
done

red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
step()  { printf '\n\033[36m== %s\033[0m\n' "$*"; }
fail()  { red "[실패] $1"; [ -n "${2:-}" ] && yellow "       다음 행동: $2"; exit 1; }

# ------------------------------------------------------------------ 1. 사전 점검
step "1. 사전 점검"
TS="$(command -v tailscale || true)"
[ -z "$TS" ] && [ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ] && TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
[ -z "$TS" ] && fail "Tailscale 이 없습니다." "App Store 에서 Tailscale 설치 → 로그인"
"$TS" status >/dev/null 2>&1 || fail "Tailscale 이 연결되어 있지 않습니다." "메뉴 막대의 Tailscale 아이콘 → Log in / Connect"
green "[확인] Tailscale 연결됨"

[ -x "$PY" ] || fail "backend/.venv 가 없습니다." "cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt"
[ -f "$BACKEND/.env" ] || fail "backend/.env 가 없습니다." ".env.example 을 복사해 채우기"

if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  lsof -nP -iTCP:$PORT -sTCP:LISTEN
  fail "8000 포트를 이미 누가 쓰고 있습니다 (dev.py 가 켜져 있나요?)." "그 프로그램을 끄고 다시 실행"
fi
green "[확인] 8000 포트 비어 있음"

# ------------------------------------------------------------------ 2. 프런트 빌드
step "2. 화면 파일 (frontend/dist)"
if [ "$BUILD" = 1 ] || [ ! -f "$FRONTEND/dist/index.html" ]; then
  [ -d "$FRONTEND/node_modules" ] || (cd "$FRONTEND" && npm install) || fail "npm install 실패"
  (cd "$FRONTEND" && npm run build) || fail "npm run build 실패"
  green "[확인] 빌드함"
else
  green "[확인] 이미 있는 dist 사용 (새로 빌드하려면 --build)"
fi

# ------------------------------------------------------------------ 3. PostgreSQL
step "3. PostgreSQL"
PG_STARTED=0
if "$PG_BIN/pg_isready" -q 2>/dev/null; then
  green "[확인] 이미 켜져 있음 (끝날 때 끄지 않음)"
else
  brew services run postgresql@16 >/dev/null || fail "PostgreSQL 을 켜지 못했습니다."
  for _ in $(seq 40); do "$PG_BIN/pg_isready" -q && break; sleep 0.25; done
  "$PG_BIN/pg_isready" -q || fail "PostgreSQL 이 응답하지 않습니다."
  PG_STARTED=1
  green "[확인] 켰음 (끝날 때 끔)"
fi

# ------------------------------------------------------------------ 끝날 때 정리
SERVER_PID=""
FUNNEL_ON=0
cleanup() {
  trap - EXIT INT TERM
  echo
  step "정리"
  if [ "$FUNNEL_ON" = 1 ]; then "$TS" funnel reset >/dev/null 2>&1 && green "[확인] 공개 주소 닫음"; fi
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID"; wait "$SERVER_PID" 2>/dev/null; green "[확인] 백엔드 끔"
  fi
  if [ "$PG_STARTED" = 1 ]; then brew services stop postgresql@16 >/dev/null 2>&1 && green "[확인] PostgreSQL 끔"; fi
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------------ 4. 백엔드
step "4. 백엔드 (app.server, 127.0.0.1:$PORT)"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/server-$(date +%Y%m%d-%H%M%S).log"
(cd "$BACKEND" && exec "$PY" -m uvicorn app.server:app --host 127.0.0.1 --port $PORT) >"$LOG" 2>&1 &
SERVER_PID=$!
for _ in $(seq 60); do
  curl -s -o /dev/null "$BASE/" && break
  kill -0 "$SERVER_PID" 2>/dev/null || { tail -20 "$LOG"; fail "백엔드가 바로 꺼졌습니다." "로그: $LOG"; }
  sleep 0.25
done
code() { curl -s -o /dev/null -w '%{http_code}' "$BASE$1"; }
[ "$(code /)" = 200 ]                  || fail "화면(/)이 200 이 아닙니다." "로그: $LOG"
[ "$(code /api/conversations)" = 401 ] || fail "/api/conversations 가 401 이 아닙니다." "로그: $LOG"
[ "$(code /api/dev/refine)" = 404 ]    || fail "/api/dev/* 가 열려 있습니다. 공개 전에 .env 의 DEV_TOOLS 를 끄세요."
green "[확인] 화면 200 · API 401 · /api/dev 404   (로그: ${LOG#$ROOT/})"

# ------------------------------------------------------------------ 5. Funnel
step "5. 공개 주소 (Tailscale Funnel)"
if ! "$TS" funnel --bg $PORT; then
  fail "Funnel 을 켜지 못했습니다." "위에 나온 링크로 관리 콘솔에서 Funnel 을 허용(처음 한 번) → 다시 실행"
fi
FUNNEL_ON=1
HOST="$("$TS" status --json | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
URL="https://$HOST/"

printf '\n공개 주소: \033[1m%s\033[0m\n' "$URL"
if command -v qrencode >/dev/null; then
  qrencode -t ANSIUTF8 -m 2 "$URL"
  qrencode -o "$ROOT/deploy/logs/qr.png" -s 12 -m 2 "$URL" && echo "QR 이미지: deploy/logs/qr.png (발표 자료에 넣기)"
else
  yellow "QR 을 보려면: brew install qrencode"
fi
yellow "켠 직후 몇 분은 일부 폰에서 「보안 연결을 할 수 없음」이 날 수 있습니다 (Funnel 설정이 퍼지는 중)."
yellow "시연 10분 전에 켜 두고, 폰으로 한 번 열어 확인하세요."
yellow "누구나 접속 가능: 시드 계정 비밀번호가 고정값이니 진짜 내용은 넣지 마세요. 끝나면 Ctrl+C."
echo
echo "켜 둔 채로 기다립니다 … (Ctrl+C 로 모두 끔)"
wait "$SERVER_PID"
red "백엔드가 멈췄습니다. 로그: $LOG"
