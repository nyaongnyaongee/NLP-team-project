"""시연용 명단 시험 (키 · DB 없이)"""
import pytest

from app.ai.refine import get_masker  # 같은 명단이면 만들어 둔 가명처리기를 다시 씀 (만드는 데 1.5초)
from app.ai.roster import load_sample_roster


def test_명단은_20명이고_중복이_없다():
    roster = load_sample_roster()
    assert len(roster) == 20 and len(set(roster)) == 20


@pytest.mark.parametrize("tail", ["이가", "는", "를", "에게", "한테", "이랑", "의", "와", "까지",
                                  "에", "에서", "으로", "에 대한", "에 대해", "에 관한", "로부터"])
def test_명단_이름은_조사가_붙어도_가려지고_복원된다(tail):
    roster = load_sample_roster()
    m = get_masker(roster, [])
    text = f"오늘 {roster[0]}{tail} 학교에서 속상한 일이 있었다고 합니다."
    masked, mp = m.mask(text)
    assert roster[0] not in masked
    assert m.unmask(masked, mp) == text


@pytest.mark.parametrize("text", [
    "벌점 당장 지우고 사과하세요.",        # 동사
    "지우개로 맞았어요.",                  # 이름이 낱말 앞부분
    "지우로봇을 샀어요.",
    "수원에서 전학 왔습니다.",             # 명단에 없는 지명 + 에서
    "서울로 이사 갑니다.",
    "연락처로 전화 주세요.",
])
def test_일반_낱말과_지명은_가리지_않는다(text):
    masked, _ = get_masker(load_sample_roster(), []).mask(text)
    assert masked == text


@pytest.mark.parametrize("text", ["박서연에 대한 민원입니다.", "김민지로부터 연락 받았습니다.", "김민지에게 말씀드렸어요."])
def test_어른_실명도_에_대한_로부터_앞에서_가려진다(text):
    m = get_masker([], ["김민지", "박서연"])
    masked, mp = m.mask(text)
    assert "박서연" not in masked and "김민지" not in masked
    assert m.unmask(masked, mp) == text
