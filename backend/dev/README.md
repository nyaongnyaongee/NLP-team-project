# 개발용 확인 화면

학부모 · 교사를 한 화면에 나란히 놓고, 보낸 메시지가 저장돼 다른 계정에서 보이는지 확인하는 임시 화면.
서비스 화면(`frontend/`)이 아니다. 프론트가 나오면 필요 없어진다.

```
cd backend
py dev\dev.py          # Windows      (Mac 은 python3 dev/dev.py)
```

처음이면 루트 `README.md` 의 「실행」 절대로 PostgreSQL · `.venv` · `.env` 를 먼저 준비한다.
DB · 테이블 · 테스트 계정은 `dev.py` 가 알아서 만들고, PostgreSQL · 백엔드(8000) · 이 화면(5173) 을 켠 뒤 브라우저를 연다.
끄기는 `Ctrl+C` (Mac 에서 `dev.py` 가 PostgreSQL 을 켰다면 같이 꺼진다). 열면 학부모 · 교사 칸이 이미 로그인돼 있다.

왼쪽(학부모)에서 보내면 오른쪽(교사)에 먼저 「정제 중…」이 뜨고 몇 초 뒤 정제문 · 분석 칩이 나온다. 「원문 보기」로 원문을 펼치고, 정제가 실패하면 원문과 「다시 정제」가 나온다.
학부모 칸에는 자기가 쓴 글이 그대로 보인다. 정제는 `backend/.env` 의 `ANTHROPIC_API_KEY` 로 진짜 Claude 를 부른다(건당 약 $0.006).
계정: `parent1` · `parent2` · `teacher1`, 비밀번호 `test1234`.
