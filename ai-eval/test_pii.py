"""dataset.jsonl 1,000개로 가명처리 검증.

  cd backend && .venv/bin/python ../ai-eval/test_pii.py [--show N] [--fp]      (Windows: .venv\Scripts\python ..\ai-eval\test_pii.py)

명단: 원문의 「OO(이) 엄마/아빠/…」 서명에서 뽑은 이름 → ai-eval/output/roster.json (가짜 학급 명단 역할, git 에는 안 올림).
두 경우를 본다
  A. 명단 없음 — Kiwi + 규칙만
  B. 명단 있음 — 실제로 쓸 모양
검사
  1. 복원:      unmask(mask(원문)) == 원문
  2. 남은 이름: 가린 글에 원문 이름이 그대로 남았는지
               (참고 이름 = 명단 + B 가 1,000개 전체에서 찾은 이름. 다른 메시지에서 이름으로 잡힌 것이
                이 메시지에선 안 가려졌으면 남은 것으로 센다)
  3. LLM 흉내:  정답 정제문(output)의 원래 이름을 같은 가짜 값으로 바꾼 뒤 되돌려 원래 정제문과 같은지
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # 저장소 루트
sys.path.insert(0, str(ROOT / "backend"))
from app.ai.pii_mask import KIN, NNP_STOP, SURNAMES, PiiMasker  # noqa: E402
ap = argparse.ArgumentParser()
ap.add_argument("--show", type=int, default=5, help="예시 개수")
ap.add_argument("--roster", choices=["signature", "sample"], default="signature",
                help="signature: 서명에서 뽑은 명단(기본), sample: backend/app/ai/sample_roster.json 20명")
ap.add_argument("--fp", action="store_true", help="명단 밖에서 이름으로 잡은 것 전부 출력(오탐 눈으로 확인)")
args = ap.parse_args()

rows = [json.loads(l) for l in open(ROOT / "dataset" / "full_1000.jsonl", encoding="utf-8")]
kin = "|".join(KIN)
SURN = "".join(sorted(SURNAMES))

# ---- 명단
sig = re.compile(rf"(?<![가-힣])([가-힣]{{2}})(?:이)?\s?(?:{kin})")
# 서명 자리에 걸린 낱말 (실제 명단에는 없을 것) — 눈으로 보고 뺐다
ROSTER_JUNK = {"다른", "아이", "동네", "꿈을", "지역", "말도", "다친", "눈빛", "번을", "상대", "하나", "제가", "거라",
               "애는", "시골", "녹색", "나온", "우리", "율이"}
roster = sorted({m.group(1) for r in rows for m in sig.finditer(r["input"])} - NNP_STOP - ROSTER_JUNK)
if args.roster == "sample":
    from app.ai.roster import load_sample_roster  # noqa: E402
    roster = load_sample_roster()
    print(f"명단 {len(roster)}명 (sample_roster.json)")
else:
    (HERE / "output").mkdir(exist_ok=True)
    (HERE / "output" / "roster.json").write_text(json.dumps(roster, ensure_ascii=False), encoding="utf-8")
    print(f"명단 {len(roster)}명 → ai-eval/output/roster.json")

maskers = {"A 명단 없음": PiiMasker(roster=[], seed=0), "B 명단 있음": PiiMasker(roster=roster, seed=0)}

ref_names = set(roster)
for r in rows:
    ref_names |= {sp.key for sp in maskers["B 명단 있음"].find(r["input"]) if sp.kind == "NAME"}


def name_hits(text, names):
    names = [n for n in names if not (len(n) == 2 and n[1] == "이")]  # 「율이」 같은 조각은 「아율이」에도 걸림
    return [n for n in names
            if re.search(rf"(?<![가-힣])(?:[{SURN}])?{re.escape(n)}(?=이|아|야|가|는|를|랑|한테|도|만|의|에게|에서?|으?로|하고|네|\s|[,.!?]|$|{kin})", text)]


for label, m in maskers.items():
    src, kinds, fp = collections.Counter(), collections.Counter(), collections.Counter()
    bad_round, leaks, bad_llm, examples = [], [], [], []
    for i, r in enumerate(rows):
        x, y = r["input"], r["output"]
        masked, mp = m.mask(x)
        for sp in m.find(x):
            kinds[sp.kind] += 1
            if sp.kind == "NAME":
                src[sp.source] += 1
                if sp.key not in roster:
                    fp[sp.key] += 1
        if m.unmask(masked, mp) != x:
            bad_round.append(i)
        left = [n for n in name_hits(masked, set(name_hits(x, ref_names))) if n not in mp.fake2orig]
        if left:
            leaks.append((i, left))
        if mp.orig2fake:
            keys = sorted(mp.orig2fake, key=len, reverse=True)
            y_fake = re.sub("|".join(map(re.escape, keys)), lambda mm: mp.orig2fake[mm.group(0)], y)
            if m.unmask(y_fake, mp) != y:
                bad_llm.append(i)
        if mp.fake2orig and len(examples) < args.show:
            examples.append((x, masked, mp))

    n = len(rows)
    print(f"\n==================== {label}")
    print(f"찾은 것: {dict(kinds)}   이름 출처: {dict(src)}")
    print(f"1. 복원 실패      {len(bad_round)}/{n}")
    print(f"2. 이름 남음      {len(leaks)}/{n}")
    for i, left in leaks[:12]:
        print(f"   #{i} {left}: {rows[i]['input'][:80]}")
    print(f"3. LLM 흉내 실패  {len(bad_llm)}/{n}  {bad_llm[:10]}")
    if args.fp:
        print(f"명단 밖 이름 {len(fp)}종:", " ".join(f"{k}{v}" for k, v in fp.most_common()))
    for x, masked, mp in examples:
        print("\n  원문:", x[:130])
        print("  가림:", masked[:130])
        print("  매핑:", mp.fake2orig)
