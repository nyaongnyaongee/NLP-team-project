# 이음

학부모·교사·민원담당자용 소통 PWA. 학부모 메시지를 가명처리한 뒤 Claude API 로 정제·분석해 교사에게 보여 준다.

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

## 민원 이관

1. 교사는 **민원 이관** 탭에서 같은 학부모와 나눈 진행 중·종료된 대화를 여러 개 고르고, 부당하다고 느낀 요구와 불편했던 점을 적어 신청한다.
2. 신청 당시 선택한 대화의 메시지 범위를 고정한다. 민원담당자는 학부모 **원문**, 교사에게 전달된 문장, 교사의 신청 사유를 구분해 볼 수 있다. 학부모에게 신청 사유와 AI 보고서는 공개하지 않는다.
3. Claude가 선택된 대화의 학부모 원문을 분석해 일정한 형식의 근거 보고서를 만든다. 학부모 메시지 수, 거친 표현 메시지 수, 반복 요구 메시지 수와 실제 원문 인용을 제공한다. 서버가 인용의 출처를 확인한 뒤 건수를 계산한다.
4. 신청서는 **접수됨 → 진행 중 → 처리 완료** 순서로 이동한다. 담당자가 신청서를 처음 열면 진행 중이 되고, **처리 완료** 버튼을 누르면 완료된다. AI 보고서 작성 상태는 이 처리 상태와 별개다.
5. 진행 중에는 민원담당자가 학부모 및 교사와 각각 별도의 채팅방에서 대화한다. 학부모 채팅은 담당자가 먼저 연락한 뒤 학부모 화면에 나타난다. 처리 완료 후에는 두 채팅 모두 읽기 전용이다.

AI 보고서는 Anthropic API를 호출한다. 서버 GPU는 사용하지 않는다.

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

`backend\.env` 를 메모장으로 열어( 명령어 : notepad .env ) **두 값을 채운다** (저장할 때 인코딩은 UTF-8).
- `DATABASE_URL` — `.env.example` 의 Windows 예시 줄을 쓰고, `비밀번호` 자리에 1번에서 정한 비밀번호
- `JWT_SECRET` — 아래 명령이 찍어 주는 긴 문자열을 붙여 넣기
  ```powershell
  .venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
  ```

**4. 켜기**

```powershell
py dev\dev.py
```

DB · 테이블 · 테스트 계정을 알아서 만들고 백엔드 · 확인 화면(5173) · React 화면(5174) 을 켠 뒤 브라우저(5174)를 연다. 끄기는 `Ctrl+C`.
React 화면은 Node.js(20.19 이상)가 있어야 켜진다 (없으면 건너뛰고 확인 화면만). `npm install` 은 알아서 한다.
화면 사용법은 `backend/dev/README.md`. 자동 확인은 `.venv\Scripts\python -m pytest` (먼저 `.venv\Scripts\python -m pip install -r requirements-dev.txt`).

### 막혔을 때 (Windows)

| 증상 | 해결 |
|---|---|
| `py` 를 찾을 수 없다 | Python 을 PATH 체크 없이 설치한 것. 다시 설치하면서 체크 |
| `PostgreSQL 이 꺼져 있습니다` | 시작 메뉴 → 「서비스」 → `postgresql-x64-16` → [시작] |
| `PostgreSQL 에 접속하지 못했습니다` | `.env` 의 `DATABASE_URL` 비밀번호 확인. 기호(`@ : / #`)가 있으면 `%40` 처럼 바꿔 쓴다 |
| `.env` 관련 안내가 뜬다 | `.env` 의 `DATABASE_URL` · `JWT_SECRET` 을 채웠는지 확인 |
| `5432` · `8000` · `5173` · `5174` 번 포트를 이미 쓴다 | 이미 켜져 있거나 다른 프로그램이 쓰는 중 |
| 패키지 설치 중 빌드 오류 | Python 버전이 너무 새것일 가능성. 3.12 로 `.venv` 를 다시 만든다 |

## 실행 (Mac)

```bash
# 처음 한 번
brew install postgresql@16
cd backend
python3.12 -m venv .venv                  # brew install python@3.12 (3.10 이상 필요)
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env                      # DATABASE_URL · JWT_SECRET 채우기 (.env.example 안내)

# 켜기 (PostgreSQL · 백엔드 · 확인 화면 5173 · React 화면 5174 → 브라우저, Ctrl+C 로 같이 끔)
python3 dev/dev.py                        # React 화면은 brew install node 가 돼 있어야 켜짐
```

## 확인

- 눈으로: `backend/dev/README.md` (학부모 · 교사 두 칸 화면)
- 자동: `cd backend && .venv/bin/python -m pytest` (Mac) / `.venv\Scripts\python -m pytest` (Windows)
