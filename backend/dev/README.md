# 개발용 확인 화면

학부모 · 교사를 한 화면에 나란히 놓고, 보낸 메시지가 저장돼 다른 계정에서 보이는지 확인하는 임시 화면.
서비스 화면(`frontend/`)이 아니다. 프론트가 나오면 필요 없어진다.

```bash
cd backend && python3 dev/dev.py      # 한 번에 켜짐 (Windows 는 python). 끄기: Ctrl+C
```

PostgreSQL · 백엔드(8000) · 이 화면(5173) 을 순서대로 켜고, 브라우저가 열리면 학부모 · 교사 칸이 이미 로그인돼 있다.
Ctrl+C 로 끄면 PostgreSQL 까지 같이 꺼진다 (Mac 에서 이 스크립트가 켰을 때). `backend/.venv` 는 먼저 만들어 둬야 한다.

왼쪽(학부모)에서 보내면 오른쪽에 2초 안에 뜬다.
계정: `parent1` · `parent2` · `teacher1`, 비밀번호 `test1234`.
