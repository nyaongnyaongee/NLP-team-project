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
| `backend/app/db` | DB 연결 · 테이블 · 저장 · 조회 (`schema.sql` 시연용 테이블) | 어령 |
| `backend/app/schemas` | 요청 · 응답 형식 (Pydantic) | 채원 + 어령 |
| `backend/app/ai` | 가명처리 · Claude 호출 · 정제(A) · 초안(B) · 추출(C) · 보고서(D) | 재관 |
| `frontend` | React PWA | 상수 |
| `ai-eval` | 프롬프트 평가 (서비스와 별개) | 재관 |
| `dataset` | 학부모 민원 정제 합성 데이터셋 1,000개 | |

## 실행

```bash
# DB
docker compose up -d

# 백엔드
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 값 채우기
uvicorn app.main:app --reload
```
