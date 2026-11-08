# 개발용 확인 화면

학부모 · 교사를 한 화면에 나란히 놓고, 보낸 메시지가 저장돼 다른 계정에서 보이는지 확인하는 임시 화면.
서비스 화면(`frontend/`)이 아니다. 프론트가 나오면 필요 없어진다.

```bash
# 터미널 1: 백엔드 (PostgreSQL 이 켜져 있어야 함)
cd backend && source .venv/bin/activate
python -m app.db.seed                       # 처음 한 번 (테스트 계정)
uvicorn app.main:app --port 8000

# 터미널 2: 이 화면 (CORS 에 허용된 5173 포트로 열어야 함)
cd backend/dev && python3 -m http.server 5173
```

Windows 는 `source .venv/bin/activate` 대신 `.venv\Scripts\activate`, `python3` 대신 `python` 을 쓴다.

브라우저에서 http://localhost:5173 → 양쪽 [로그인] → 왼쪽에서 보내면 오른쪽에 2초 안에 뜬다.
계정: `parent1` · `parent2` · `teacher1`, 비밀번호 `test1234`.
