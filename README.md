# 이음

교사용 학부모 소통 PWA. 학부모 메시지를 가명처리한 뒤 Claude API 로 정제·분석해 교사에게 보여 준다.

```
React PWA → FastAPI ── PostgreSQL
                └→ 가명처리(pii_mask) → Claude API
```

## 폴더

| 폴더 | 내용 | 담당 |
|---|---|---|
| `backend/app/core`, `routers`, `main.py` | 설정 · 인증 · API · WebSocket | 채원 |
| `backend/app/db` | DB 연결 · 테이블 · 저장 · 조회 (`schema.sql` 시연용 테이블, `psql eum -f` 로 만듦) | 어령 |
| `backend/app/schemas` | 요청 · 응답 형식 (Pydantic) | 채원 + 어령 |
| `backend/app/ai` | 가명처리 · Claude 호출 · 정제(A) · 초안(B) · 추출(C) · 보고서(D) | 재관 |
| `frontend` | React PWA | 상수 |
| `ai-eval` | 프롬프트 평가 (서비스와 별개) | 재관 |
| `dataset` | 학부모 민원 정제 합성 데이터셋 1,000개 | |

## 실행 (Windows)

처음 한 번만 하는 준비 (1~2), 그다음부터는 4번만.

**1. PostgreSQL 16 설치** — https://www.postgresql.org/download/windows/ 의 설치 프로그램.
설치 중 `postgres` 사용자의 **비밀번호를 정하라고 나온다. 꼭 기억해 둘 것** (아래 `.env` 에 쓴다). 포트는 기본 `5432` 그대로.
설치가 끝나면 PostgreSQL 이 서비스로 켜져 있고, 컴퓨터를 켤 때마다 자동으로 켜진다.

**2. Python 3.12 설치** — https://www.python.org/downloads/ (3.10 이상 필요, 3.12 권장).
설치 첫 화면의 **「Add python.exe to PATH」 를 체크**.

**3. 코드 받기 · 패키지 설치** (PowerShell)

```powershell
git clone https://github.com/nyaongnyaongee/NLP-team-project.git    # 이미 받았으면 git pull
cd NLP-team-project\backend
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

`backend\.env` 를 메모장으로 열어 **두 값을 채운다** (저장할 때 인코딩은 UTF-8).
- `DATABASE_URL` — `.env.example` 의 Windows 예시 줄을 쓰고, `비밀번호` 자리에 1번에서 정한 비밀번호
- `JWT_SECRET` — 아래 명령이 찍어 주는 긴 문자열을 붙여 넣기
  ```powershell
  .venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
  ```

**4. 켜기**

```powershell
py dev\dev.py
```

DB · 테이블 · 테스트 계정을 알아서 만들고 백엔드와 확인 화면을 켠 뒤 브라우저를 연다. 끄기는 `Ctrl+C`.
화면 사용법은 `backend/dev/README.md`. 자동 확인은 `.venv\Scripts\python -m pytest` (먼저 `.venv\Scripts\python -m pip install -r requirements-dev.txt`).

### 막혔을 때 (Windows)

| 증상 | 해결 |
|---|---|
| `py` 를 찾을 수 없다 | Python 을 PATH 체크 없이 설치한 것. 다시 설치하면서 체크 |
| `PostgreSQL 이 꺼져 있습니다` | 시작 메뉴 → 「서비스」 → `postgresql-x64-16` → [시작] |
| `PostgreSQL 에 접속하지 못했습니다` | `.env` 의 `DATABASE_URL` 비밀번호 확인. 기호(`@ : / #`)가 있으면 `%40` 처럼 바꿔 쓴다 |
| `.env` 관련 안내가 뜬다 | `.env` 의 `DATABASE_URL` · `JWT_SECRET` 을 채웠는지 확인 |
| `5432` · `8000` · `5173` 번 포트를 이미 쓴다 | 이미 켜져 있거나 다른 프로그램이 쓰는 중 |
| 패키지 설치 중 빌드 오류 | Python 버전이 너무 새것일 가능성. 3.12 로 `.venv` 를 다시 만든다 |

## 실행 (Mac)

```bash
# 처음 한 번
brew install postgresql@16
cd backend
python3.12 -m venv .venv                  # brew install python@3.12 (3.10 이상 필요)
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env                      # DATABASE_URL · JWT_SECRET 채우기 (.env.example 안내)

# 켜기 (PostgreSQL 은 필요하면 알아서 켜고 Ctrl+C 로 같이 끔)
python3 dev/dev.py
```

## 확인

- 눈으로: `backend/dev/README.md` (학부모 · 교사 두 칸 화면)
- 자동: `cd backend && .venv/bin/python -m pytest` (Mac) / `.venv\Scripts\python -m pytest` (Windows)

## A-1 메시지 접수 API

기존 `/conversations/{id}/messages`는 시연 화면용 API로 유지합니다. 최상위 `POST /messages`와 `GET /messages`는 `backend/app/routers/message_intake.py`에 있습니다. 이 API는 기존 로그인 Bearer 토큰, 정수 메시지 ID, `pending`/`done`/`failed` 상태, 대화 참여자 권한 규칙을 사용합니다. `GET`은 A-2의 `crud.list_messages`와 기존 응답 필터를 연결해 교사에게 원문·인용문을 숨깁니다. 학부모는 기존 규칙대로 본인 대화의 원문을 볼 수 있습니다.

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 로그인 후 받은 토큰을 환경 변수 TOKEN에 설정하고, 실제 대화 ID를 사용한다.
curl -i -X POST http://127.0.0.1:8000/messages \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"conversation_id":1,"text":"아이의 안전 문제를 확인해 주세요."}'
curl -i -G http://127.0.0.1:8000/messages \
  -H "Authorization: Bearer $TOKEN" --data-urlencode 'conversation_id=1'
```

`POST`는 학부모만 허용하고 공백 메시지, 10,000자 초과, 추가 필드를 `422 invalid_request`로 거절합니다. 원문과 AI 정제 작업이 **같은 트랜잭션에 영속 저장된 뒤** `202 {"id": ..., "conversation_id": ..., "status": "pending"}`를 반환해야 합니다. DB 실패는 `503 storage_unavailable`, 작업 등록 실패는 `503 job_registration_failed`입니다. 응답과 오류에 원문이나 내부 예외 문자열을 넣지 않습니다.

현재 A-2의 메시지 저장·조회와 A-3의 `refine_message`는 있지만, 별도 Worker가 재시작 후에도 조회·재시도할 수 있는 영속 AI 작업 등록 기능은 없습니다. `backend/app/db/schema.sql`의 `tasks`는 C 기능의 할 일·일정 테이블이며 AI 작업 큐가 아닙니다. `messages.status='pending'`만으로는 작업 시도 횟수·재시도 시각·잠금 상태를 관리할 수 없습니다. 기존 시연 API의 `BackgroundTasks`도 프로세스 재시작에 견디는 작업 큐는 아닙니다. 따라서 새 `POST /messages`는 `app.state.message_intake_service`가 연결되기 전 `503 job_store_unavailable`을 반환하며 저장 없이 성공을 보고하지 않습니다. **Worker가 꺼져 있다는 사실만으로 접수를 막지 않습니다.** 영속 작업 등록이 구현되면 Worker가 실행 중이지 않아도 커밋 후 `202`를 반환합니다. `GET /messages?conversation_id=...`는 이 연결 없이도 기존 DB에서 조회합니다.

A-2/A-3 담당자는 `backend/app/services/message_intake.py`의 `MessageIntakeService.submit_message(db, conversation_id, sender_id, raw_text)`를 구현해야 합니다. 구체적인 저장 계약은 다음과 같습니다.

1. PostgreSQL에 C 기능의 `tasks`와 별개인 AI 정제 작업 저장소를 마련합니다. 작업은 `message_id` 외래키, `queued`/`processing`/`done`/`failed` 상태, 시도 횟수, 다음 시도 시각, 잠금 만료 시각을 보존해야 합니다. 한 메시지의 작업 중복 생성 방지도 필요합니다. 오류 기록에는 원문·개인정보·API 키를 넣지 않습니다.
2. `submit_message`는 전달받은 **같은 DB 세션·트랜잭션**에서 `messages` 원문 행(`status='pending'`)과 `queued` 작업을 삽입하고 **한 번만 커밋**합니다. 현재 `crud.add_message`는 자체적으로 먼저 커밋하므로 그대로 호출하면 이 원자성 계약을 지킬 수 없습니다. 두 삽입 중 하나라도 실패하면 모두 롤백하고, DB 오류는 `MessageStorageError`, 작업 등록 오류는 `JobRegistrationError`를 발생시킵니다. 커밋 완료 후에만 기존 정수 ID의 `MessageReceipt`를 반환합니다. `POST` 요청 중에는 AI 모델을 호출하지 않습니다.
3. 별도 Worker는 커밋된 작업을 동시 실행에 안전하게 가져와 잠금·재시도를 관리하고 기존 `refine_message`와 A-2 결과 저장 기능을 연결합니다. 결과·작업 상태를 저장한 뒤 완료 알림을 보냅니다. 작업 선점 방식, 최대 시도 횟수, 실패 상태와 알림 방식은 A-2/A-3 담당자와 확정해야 합니다. 모델 공급자는 A-1에서 선택하지 않습니다.

`backend/.env`는 앱 설정의 `DATABASE_URL`·`JWT_SECRET`을 제공하기 위해 사용합니다. 테스트의 `conftest.py`는 `DATABASE_URL` 환경 변수가 없을 때만 이 파일을 읽고, `JWT_SECRET`은 테스트 기본값을 설정합니다. 따라서 **테스트에서는 `.env` 없이** `DATABASE_URL` 환경 변수만 줄 수 있습니다. 자격 증명이 필요 없는 로컬 PostgreSQL Unix 소켓이 준비된 환경의 예시는 다음과 같습니다.

```bash
cd backend
DATABASE_URL='postgresql+psycopg:///eum_test' .venv/bin/python -m pytest
```

실제 연결 URL은 **테스트 전용 PostgreSQL 서버·계정**의 것으로 설정해야 합니다. `conftest.py`는 URL의 DB 이름을 `eum_test`로 바꾸고, 같은 서버의 `postgres` DB에 접속해 테스트 DB를 만들며, `eum_test`의 `public` 스키마를 매 실행마다 삭제·재생성합니다. 따라서 테스트 계정에는 `postgres` 접속, 테스트 DB 생성(`CREATEDB`), `eum_test` 스키마 재생성 권한이 필요합니다. 운영 DB 연결 URL은 사용하지 마세요. `ANTHROPIC_API_KEY`는 가짜 응답을 쓰는 테스트에 필요하지 않습니다. 실제 비밀값을 테스트 파일이나 Git에 저장하지 않습니다.

DB·AI 없이 A-1 HTTP 계약을 확인하려면 `cd backend && python -m unittest discover -s tests -p test_message_api.py -v`를 실행합니다. 전체 프로젝트 테스트는 PostgreSQL의 테스트 DB와 `backend/requirements-dev.txt` 의존성을 준비한 뒤 `cd backend && python -m pytest`로 실행합니다.
