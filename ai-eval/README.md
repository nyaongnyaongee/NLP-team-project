# AI 평가  [재관]

서비스와 별개. 프롬프트를 바꿀 때 품질을 확인하는 평가셋과 스크립트를 둔다.
데이터는 저장소 루트의 `dataset/` 을 쓴다.

## 가명처리 검증 — `test_pii.py`

`dataset/full_1000.jsonl` 1,000건으로 가명처리를 확인한다 (키 · DB 없이, Kiwi 만 쓴다).

```bash
cd backend
.venv/bin/python ../ai-eval/test_pii.py [--show N] [--fp] [--roster signature|sample]
# Windows: .venv\\Scripts\\python ..\\ai-eval\\test_pii.py
```

세 가지를 본다: ① 복원(`unmask(mask(원문)) == 원문`) ② 가린 글에 이름이 남았는지 ③ 정답 정제문으로 흉내 낸 복원.
명단 없음(A) · 명단 있음(B) 두 경우를 각각 낸다. 결과 `ai-eval/output/roster.json` 은 git 에 안 올라간다.

- `--roster signature`(기본): 원문의 「OO 엄마」 서명에서 명단을 뽑는다. 이 데이터셋에서는 3명뿐이라 B 가 실제와 다르다.
- `--roster sample`: `backend/app/ai/sample_roster.json` 20명으로 한다. 실제 쓰는 모양에 가깝다.

기준 (2026-11-08, `--roster sample`): B 에서 이름 남음 **0/1000**, 복원 실패 0, 흉내 실패 0.
`에 · 에서 · 으로 · 로 · 에 대한` 이 뒤따르는 명단 이름이 안 가려지던 구멍(4건)을 고친 뒤의 값.
이름 남음 검사에도 `에 · 에서 · 으로 · 로` 를 이름 뒤 말로 넣었다.
