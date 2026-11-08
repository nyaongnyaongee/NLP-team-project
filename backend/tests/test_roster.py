"""시연용 명단 시험 (키 · DB 없이)"""
import pytest

from app.ai.pii_mask import PiiMasker
from app.ai.roster import load_sample_roster


def test_명단은_20명이고_중복이_없다():
    roster = load_sample_roster()
    assert len(roster) == 20 and len(set(roster)) == 20


@pytest.mark.parametrize("tail", ["이가", "는", "를", "에게", "한테", "이랑", "의", "와", "까지"])
def test_명단_이름은_흔한_조사가_붙어도_가려지고_복원된다(tail):
    roster = load_sample_roster()
    m = PiiMasker(roster=roster, adults=[])
    text = f"오늘 {roster[0]}{tail} 학교에서 속상한 일이 있었다고 합니다."
    masked, mp = m.mask(text)
    assert roster[0] not in masked
    assert m.unmask(masked, mp) == text


@pytest.mark.xfail(strict=True, reason="알려진 구멍: 이름 뒤에 에 · 에서 · 으로 · 로 · 에 대한 이 오면 가려지지 않음 (pii_mask FOLLOW)")
@pytest.mark.parametrize("tail", ["에", "에서", "으로", "에 대한", "에 대해"])
def test_이름_뒤에_에_에서_으로_에_대한이_와도_가려져야_한다(tail):
    roster = load_sample_roster()
    masked, _ = PiiMasker(roster=roster, adults=[]).mask(f"오늘 {roster[0]}{tail} 학교에서 속상한 일이 있었다고 합니다.")
    assert roster[0] not in masked
