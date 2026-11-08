"""학부모 메시지 개인정보 가명처리 / 복원.

API 로 보내기 전에 이름 · 전화번호 · 이메일 · 주민번호 · 계좌 · 학교 · 학원 · 주소 · 아파트 · 차량번호를 가짜 값으로 바꾸고,
응답이 오면 매핑표로 원래 값으로 되돌린다. 매핑표는 호출 하나 동안 메모리에만 둔다(저장 · 로그 금지).

이름은 [학생1] 같은 토큰 대신 **받침 종류가 같은 가짜 이름**으로 바꾼다.
  받침 없음(지우) ↔ 받침 없음, ㄹ 받침(소율) ↔ ㄹ 받침, 그 밖의 받침(민준) ↔ 그 밖의 받침
그래서 「민준이가」 → 「서담이가」, 「소율로」 → 「하솔로」처럼 조사가 깨지지 않고, 되돌린 뒤에도 자연스럽다.

이름 찾기 (GPU 없음, 형태소 분석기 kiwipiepy 만 씀)
  1단계 후보 찾기
    - 명단(roster) 이름: Kiwi 사용자 사전에 넣어 둔다
    - 명단에 없는 이름: Kiwi 고유명사(NNP) + 이름 자리 문맥(「이」 접미사, 호격, 조사, 엄마 · 선생님 …)
    - 정규식 보조: 「OO 엄마」, 「동생 OO」 (Kiwi 가 이름을 쪼갠 경우)
    - 성 + 이름 세 글자(어른 실명): 이름이 오는 자리만 본다 — 「OOO 선생님 · 교감」, 「보건교사 · 예금주 OOO」,
      「OO 엄마 OOO」, 「OOO 드림 · 올림」, 전화번호 옆, 「저는 OOO입니다」, 글 끝 (FULL_RULES). 성까지 붙은 모양만 가린다
    - 명단 이름 오타(1107 밤): 명단 이름에서 자모 하나를 헷갈리기 쉬운 것으로 바꾼 모양(민준 → 민쥰 · 민중, 서연 → 서현,
      정수진 → 정수지)이 이름 자리 단서와 함께 나오면 가린다 — 뒤에 「이 + 조사」 · 엄마 · 아빠, 앞에 우리 · 저희 · 동생 · 친구.
      어른 명단은 성까지 세 글자 + 이름 뒤 경계(FULL_FOLLOW)만 본다. 용언 활용형(때린 · 찌우)과 TYPO_STOP(손주 · 집안 …)은 뺀다
  2단계 훑기: 1단계에서 나온 이름 + 명단 이름을 글 전체에서 다시 찾아 모두 가린다
    (Kiwi 는 같은 이름도 문장마다 다르게 쪼갤 수 있어서, 한 번 찾은 이름은 모든 자리에서 가린다)

사용:
    m = PiiMasker(roster=["서윤", "민재"])
    masked, mapping = m.mask(text)
    answer = call_api(masked)
    final = m.unmask(answer, mapping)
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from kiwipiepy import Kiwi

# ---------------------------------------------------------------- 낱말 목록
SURNAMES = set(
    "김이박최정강조윤장임한오서신권황안송류유전홍고문양손배백허남심노하곽성차주우구민진나지엄채원천방공현함변염여추도소석선설마길연위표명기반왕금옥육인맹제모탁국어은편용예경봉사부라감빈피"
)
KIN = ("엄마", "아빠", "어머니", "아버지", "어머님", "아버님", "할머니", "할아버지", "할미", "할애비", "할아비",
       "이모", "고모", "삼촌", "맘", "보호자")
TITLE = ("선생님", "선생", "쌤", "샘", "교사", "님", "씨", "군", "양")
REL = ("동생", "형", "오빠", "누나", "언니", "친구", "짝", "짝꿍")

# Kiwi 가 NNP 로 잡지만 이름이 아닌 것 (데이터셋 1,000개에서 확인한 것 + 흔한 것)
NNP_STOP = {
    "영어", "한국어", "중국어", "일본어", "수학", "국어", "과학", "사회", "체육", "음악", "미술", "피구", "축구", "야구",
    "체험학습", "모닝콜", "태블릿", "국민신문고", "코로나", "출결", "빼빼로", "개인정보", "인스타", "보건실", "베트남",
    "단톡", "레고", "고글", "샤프", "수두", "카톡", "카카오", "카카오톡", "유튜브", "네이버", "구글", "줌", "하이클래스",
    "클래스팅", "알리미", "중국", "일본", "미국", "한국", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "제주",
    "우리", "다른", "친구", "동네", "쌍둥", "일일", "한둘", "고양", "만원", "개같", "난간", "같은", "자기", "남의", "애들", "아이", "그집", "그쪽", "반", "하나", "문제",
}

# 이름 바로 뒤에 올 수 있는 것 (2단계 훑기에서 이름 끝 경계로 씀).
# 「이」는 뒤에 무엇이 오든 받는다: 지훈이었는데 · 하율이로 · 서진이가 (지우개 · 하준비 같은 낱말만 거른다)
FOLLOW = re.compile(
    rf"(?:이|아(?![가-힣])|야(?![가-힣])|[가는은를을랑와과도만의]|한테|에게|하고|께|네|보다|처럼|까지|부터"
    rf"|입니|예요|드림|올림"
    rf"|{'|'.join(KIN)}|{'|'.join(TITLE)}|\s|[,.!?~^'\")\]]|$)"
)


# 성 + 이름 세 글자(어른 실명: 교사 · 학부모 서명 · 예금주). Kiwi 는 이런 이름을 일반 명사로 자주 읽어서(오지현 · 문성호 NNG)
# 낱말인지로는 못 거른다. 이름이 오는 자리만 보고, 조사 · 용언이 섞인 것만 버린다(_full_ok).
_S = "[" + "".join(sorted(SURNAMES)) + "]"
# 이름 앞에 오는 직함만(「선생님 · 담임 + 세 글자」는 서술형 · 추천서 같은 낱말이 더 많아서 뺐다. 「윤태호 선생님」은 첫 규칙이 잡음)
_ROLE = ("교감|교장|원장|부장|보건교사|영양사|예금주|계좌주|주무관|실장|기사|강사|사범님|사범|코치|관장님|관장"
         "|(?:돌봄|방과후|학원|원어민|보조|특수|상담|영양|보건|체육|음악|미술|영어|태권도)\\s?(?:선생님|선생|교사|쌤)")
_PHONE = r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}"
FULL_RULES = [
    re.compile(rf"(?<![가-힣])({_S}[가-힣]{{2}})\s?(?=선생님|선생|쌤|샘|교사|교감|교장|원장|부장|강사|님(?![가-힣])|씨(?!발|바|빨|팔|부랄))"),
    re.compile(rf"(?<![가-힣])(?:{_ROLE})\s?\(?\s?({_S}[가-힣]{{2}})"),          # 보건교사 강은지 · 예금주 정미경
    re.compile(rf"(?:{'|'.join(KIN)})\s?({_S}[가-힣]{{2}})"),                      # 민준 엄마 김지영
    re.compile(rf"(?<![가-힣])({_S}[가-힣]{{2}})\s?(?=드림|올림|배상)"),
    re.compile(rf"(?<![가-힣])({_S}[가-힣]{{2}})\s?[/,]?\s?(?={_PHONE})"),         # 박진아 010-…
    re.compile(rf"(?<!\d){_PHONE}\s?[/,]?\s?({_S}[가-힣]{{2}})"),                 # 031-123-4567 박주연
    re.compile(rf"(?<![가-힣])(?:저는|전|저|제 이름은|저희는)\s({_S}[가-힣]{{2}})(?=입니|이고|고(?![가-힣])|예요|이에요|이구요|이요|인데|이라|라고)"),
    # 「담임이 한주연이라며」: 교사를 가리키는 말 + 이름 + 「이라 · 이잖 …」
    re.compile(rf"(?<![가-힣])(?:담임|교감|교장|선생님|선생|쌤)(?:이|은|는|가)?\s({_S}[가-힣]{{2}})(?=이라|이잖|이야|이었|이던|인데)"),
    # 띄어 쓴 이름: 「이루 아빠 김 태훈입니다」
    re.compile(rf"(?:{'|'.join(KIN)}|저는|저|예금주|계좌주)\s?({_S}\s[가-힣]{{2}})(?=입니|이고|이에요|예요|드림|올림|\s?[/,]?\s?0\d|\s*$|[,.])"),
    re.compile(rf"(?<![가-힣])({_S}[가-힣]{{2}})\s*[.!~^]*\s*$"),                   # 글 끝 서명
    re.compile(rf"(?<![가-힣])({_S}[가-힣]{{2}})\s(?=너(?![가-힣])|니가|네가)"),        # 최민철 너 …
]
# 명단 이름 오타를 받을 때 쓰는 이름 자리 단서: 뒤에 「이 + 조사」(민중이랑) · 엄마 · 선생님, 앞에 우리 · 동생 …
TYPO_AFTER = re.compile(rf"(?:이(?:[가는를랑도만의네]|한테|에게|하고|랑|아|야)|이?\s?(?:{'|'.join(KIN)}))")
# 이름 자리에 자주 오는 일반 낱말 (우리 손주가 · 저희 집안 · 시누이가 …)
TYPO_STOP = {"손주", "손녀", "집안", "시누", "남편", "아들", "아내", "가족", "부모", "식구", "동생", "사람", "이름", "시간", "나이"}
TYPO_BEFORE = re.compile(rf"(?:^|[^가-힣])(?:우리|저희|울|{'|'.join(REL)})\s?[{''.join(sorted(SURNAMES))}]?$")
FULL_FOLLOW = re.compile(rf"(?:{FOLLOW.pattern}|고(?![가-힣])|인데|이라|라고)")  # 저는 오영미고 · 변상우인데요 …
# 명단(학생 · 어른)에 있는 이름은 에 · 에서 · 으로 · 로 · 에 대한 … 앞에서도 이름으로 본다 (준서에 대한 · 지민으로 · 소율로).
# Kiwi 가 찾은 일반 후보에는 쓰지 않는다: 수원에서 · 서울로 같은 지명이 이름으로 가려지지 않게. 에 · 로 바로 뒤에 낱말이 이어지면(지우로봇) 뺀다
_LISTED_EXTRA = r"|에(?:서|도|는|만|까지|\s|[,.!?]|$)|으?로(?:서|써|부터|는|도|만|\s|[,.!?]|$)"
FOLLOW_LISTED = re.compile(rf"(?:{FOLLOW.pattern}{_LISTED_EXTRA})")
FULL_FOLLOW_LISTED = re.compile(rf"(?:{FULL_FOLLOW.pattern}{_LISTED_EXTRA})")
FULL_STOP = {"어머니", "아버지", "할머니", "고모부", "이모부", "선생들", "교장실", "교무실", "행정실", "보건실", "연락처",
             "유치원", "방과후", "원어민", "기간제", "도우미", "어린이", "도시락", "전화번", "문자로"}


def batchim_class(word: str) -> int:
    """마지막 글자 받침: 0 없음, 1 ㄹ, 2 그 밖."""
    code = ord(word[-1]) - 0xAC00
    if not 0 <= code < 11172:
        return 0
    jong = code % 28
    return 0 if jong == 0 else (1 if jong == 8 else 2)


def is_hangul(s: str) -> bool:
    return bool(s) and all("가" <= ch <= "힣" for ch in s)


# 오타로 볼 자모 바꿈: 헷갈리기 쉬운 것끼리만 (아무 자모나 바꾸면 손주 · 집안 · 이름 같은 낱말이 너무 많이 걸린다)
# 초성 번호: ㄱ0 ㄲ1 ㄴ2 ㄷ3 ㄸ4 ㄹ5 ㅁ6 ㅂ7 ㅃ8 ㅅ9 ㅆ10 ㅇ11 ㅈ12 ㅉ13 ㅊ14 ㅋ15 ㅌ16 ㅍ17 ㅎ18
_CHO_SIM = [{0, 1, 15}, {3, 4, 16}, {7, 8, 17}, {12, 13, 14}, {9, 10}, {11, 18}]
# 중성: ㅏ0 ㅐ1 ㅑ2 ㅒ3 ㅓ4 ㅔ5 ㅕ6 ㅖ7 ㅗ8 ㅘ9 ㅙ10 ㅚ11 ㅛ12 ㅜ13 ㅝ14 ㅞ15 ㅟ16 ㅠ17 ㅡ18 ㅢ19 ㅣ20
_JUNG_SIM = [{0, 2}, {4, 6}, {8, 12, 13}, {13, 17}, {1, 5}, {3, 7}, {10, 11, 15}, {9, 14}]
# 종성: 받침이 빠지거나 생김(0 ↔ 아무것), ㄴ4 ㅇ21 ㅁ16 끼리
_JONG_SIM = [{4, 21, 16}]


def _sim(groups: list[set[int]], x: int) -> set[int]:
    return set().union(*(g for g in groups if x in g)) - {x}


def typo_variants(name: str) -> set[str]:
    """명단 이름의 오타 모양: 한 글자에서 자모 하나를 헷갈리기 쉬운 것으로 바꾼 것.
    민준 → 민쥰(ㅜ/ㅠ) · 민중(ㄴ/ㅇ), 지호 → 지후, 서연 → 서현(ㅇ/ㅎ), 정수진 → 정수지(받침 빠짐)."""
    out: set[str] = set()
    for k, ch in enumerate(name):
        code = ord(ch) - 0xAC00
        if not 0 <= code < 11172:
            continue
        cho, jung, jong = code // 588, (code % 588) // 28, code % 28
        alts = ([(c, jung, jong) for c in _sim(_CHO_SIM, cho)] + [(cho, j, jong) for j in _sim(_JUNG_SIM, jung)]
                + [(cho, jung, g) for g in (_sim(_JONG_SIM, jong) | ({0} if jong else set(range(1, 28))))])
        for c2, j2, g2 in alts:
            out.add(name[:k] + chr(0xAC00 + c2 * 588 + j2 * 28 + g2) + name[k + 1:])
    return out


# ---------------------------------------------------------------- 정규식 개인정보
# 학원 이름 끝의 과목은 남긴다(행복수학학원 → 한빛수학학원)
ACAD_SUBJ = ("영어", "수학", "피아노", "미술", "음악", "태권도", "논술", "과학", "국어", "코딩", "수영", "발레", "컴퓨터",
             "주산", "바둑", "독서", "한자", "중국어", "보습", "입시", "종합", "속셈", "체육", "줄넘기", "검도", "합기도")
PATTERNS = [
    # (종류, 정규식) — 위에서부터 차례로, 이미 잡힌 자리는 건너뜀
    ("RRN", re.compile(r"(?<!\d)\d{6}\s?-\s?[1-4]\d{6}(?!\d)")),
    ("PHONE", re.compile(r"(?<!\d)01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")),
    ("PHONE", re.compile(r"(?<!\d)0(?:2|[3-6][1-5])[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("ACCOUNT", re.compile(r"(?<![\d-])\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,3})?(?![\d-])")),
    ("ADDR", re.compile(r"[가-힣0-9]{1,15}(?:로|길)\s?\d{1,4}(?:-\d{1,4})?(?:번길\s?\d{1,4})?(?![\d가-힣])")),
    ("APT", re.compile(r"\d{1,4}\s?동\s?\d{1,4}\s?호")),
    ("SCHOOL", re.compile(r"(?<![가-힣])[가-힣]{2,10}(?=(?:초등학교|중학교|고등학교|초교|유치원|어린이집))")),
    ("SCHOOL", re.compile(r"(?<![가-힣])[가-힣]{2,10}(?=초(?:[\s,.!?]|$|[이가은는에의를도랑]))")),
    ("SCHOOL", re.compile(r"(?<![가-힣])([가-힣]{2,10})(?=[중고]\s?\d학년)")),  # 해솔중 1학년 (같다고 2학년 은 _place_ok 가 거름)
    ("CAR", re.compile(r"(?<!\d)\d{2,3}\s?[가나다라마거너더러머버서어저고노도로모보소오조구누두루무부수우주아바사자배하허호]\s?\d{4}(?!\d)")),
    # 아래는 무리 1 만 가린다: 「행복」수학학원, 「래미안」 아파트
    ("ACADEMY", re.compile(rf"(?<![가-힣])([가-힣]{{1,10}}?)(?:{'|'.join(ACAD_SUBJ)})?(?=(?:학원|교습소|공부방|지역아동센터|아동센터|태권도|합기도|체육관|아카데미))")),
    ("APT", re.compile(r"(?<![가-힣])([가-힣]{2,10})\s?(?=아파트)")),
    ("APT", re.compile(r"(?<![가-힣])([가-힣]{2,10})\s(?=\d{1,4}\s?동\s?\d{1,4}\s?호)")),
]
# 「OO초」 앞부분이 이것으로 끝나면 학교 이름이 아님 (올해초, 학기초 …)
SCHOOL_PREFIX_STOP = ("올해", "작년", "내년", "학기", "연말", "연초", "이번", "다음", "지난", "월", "년", "주")
# 학원 · 아파트 이름 자리에 오지만 고유 이름이 아닌 것
NAME_PLACE_STOP = {"우리", "저희", "같은", "다른", "동네", "근처", "주변", "무슨", "어느", "그런", "이런", "다니던", "다니는",
                   "보습", "입시", "종합", "단과", "대형", "임대", "주공", "옆", "앞", "그", "이", "저", "큰", "새", "집"}


# ---------------------------------------------------------------- 가짜 값
# 받침 종류별 가짜 이름. 일반 낱말 · 지명과 겹치지 않는 것으로 골랐다.
# 실행할 때 명단 이름과 그 메시지에 나온 글자는 빼고 고른다.
FAKE_NAMES = {
    0: ["서희", "소희", "채희", "다희", "나희", "주희", "가희", "세희", "도희", "아희", "예주", "유주", "하예",
        "해나", "윤희", "시아", "서애", "채아", "효주", "연희", "수애", "지애", "혜리", "은비", "다예"],
    1: ["하솔", "예솔", "다솔", "유솔", "아율", "가율", "나율", "세율", "채율", "도율", "서율", "하율",
        "시율", "지율", "은율", "주별", "한별", "새별", "가을", "다을", "예설", "하설", "소율"],
    2: ["서담", "하담", "예담", "소담", "세담", "채담", "유담", "도담", "세빈", "예빈", "채린", "해린",
        "소은", "다현", "하경", "서진", "윤슬", "가윤", "하온", "서온", "예온", "채온", "지온", "다온", "아린"],
}
FAKE_NAMES[2] = [n for n in FAKE_NAMES[2] if batchim_class(n) == 2]  # 윤슬(ㄹ) 같은 것 정리
FAKE_SURNAMES = list("김이박최정강조윤장임한오신권황안송홍")
FAKE_SCHOOLS = ["한빛", "새솔", "푸른숲", "가람", "누리", "솔빛", "다솜", "해오름", "별빛", "은하수"]
FAKE_APTS = ["솔숲마을", "햇빛타운", "가온빌", "들꽃마을", "다올타운"]


@dataclass
class Mapping:
    """가짜 값 ↔ 원래 값. 메모리에만 둔다."""
    fake2orig: dict[str, str] = field(default_factory=dict)
    orig2fake: dict[str, str] = field(default_factory=dict)
    kinds: dict[str, str] = field(default_factory=dict)  # 가짜 값 → 종류(NAME, PHONE …)

    def add(self, orig: str, fake: str, kind: str) -> None:
        self.orig2fake[orig] = fake
        self.fake2orig[fake] = orig
        self.kinds[fake] = kind


@dataclass
class Span:
    start: int
    end: int
    kind: str
    orig: str
    key: str = ""      # 이름이면 성을 뗀 이름(민준), 아니면 orig
    surname: str = ""  # 성이 붙어 있으면 성
    source: str = ""   # roster / kiwi / rule / regex


class PiiMasker:
    def __init__(self, roster: list[str] | None = None, seed: int | None = 0, adults: list[str] | None = None):
        """roster: 반 학생 이름(성 있어도 됨, 두 글자 이름으로 글 전체를 훑음).
        adults: 교직원 · 학부모 실명(성 + 이름). 성까지 붙은 모양(띄어 쓴 것 포함)만 가린다."""
        self.roster = {self._stem(n) for n in (roster or []) if n}
        self.adults = sorted({a.replace(" ", "") for a in (adults or []) if len(a.replace(" ", "")) >= 3}, key=len, reverse=True)
        self._adult_set = set(self.adults)
        self.rng = random.Random(seed)
        self.kiwi = Kiwi()
        self.kiwi_plain = Kiwi()  # 명단을 넣지 않은 것: 실명 판정(_full_ok)용
        for name in self.roster:
            self.kiwi.add_user_word(name, "NNP", 0.0)
        self._fake_pool = {c: [n for n in ns if n not in self.roster] for c, ns in FAKE_NAMES.items()}
        # 오타 모양 → 원래 명단 이름. 일반 낱말 목록(NNP_STOP)과 겹치는 것, 명단 이름 자체는 뺀다
        self.roster_typos = {v for n in self.roster if len(n) >= 2 for v in typo_variants(n)} - self.roster - NNP_STOP - TYPO_STOP
        adult_set = set(self.adults)
        self.adult_typos = {v for a in self.adults for v in typo_variants(a)} - adult_set - FULL_STOP

    @staticmethod
    def _stem(name: str) -> str:
        """「민준이」 → 「민준」, 「김민준」 → 「민준」(성 + 두 글자일 때)."""
        name = name.strip()
        if len(name) == 3 and name[-1] == "이" and batchim_class(name[1]) != 0:
            name = name[:2]
        if len(name) == 3 and name[0] in SURNAMES:
            name = name[1:]
        return name

    def _not_a_word(self, g: str) -> bool:
        """이름 자리(엄마 앞 · 우리 뒤 · 「이」 앞)에 온 두 글자가 낱말이 아니면 참.

        거르는 것: 한 낱말(상대 · 지역 · 다른), 활용형(다친 · 나온 · 거라 · 다름 · 개같), 한 글자 낱말 + 조사(애가 · 꿈을 · 제가).
        받는 것:   쪼개진 이름(은 + 호, 이 + 안, 예 + 다 + ㅁ). 「로아」처럼 Kiwi 가 낱말로 아는 이름은 놓친다(명단으로 보완).
        """
        if g in NNP_STOP:
            return False
        toks = self.kiwi.tokenize(g)
        if len(toks) == 1:
            return toks[0].tag == "NNP"
        if any(t.tag in ("ETM", "ETN", "VCP") or t.tag.startswith("V") for t in toks):
            return False
        if len(toks) == 2 and toks[0].len == 1 and toks[1].tag.startswith("J"):
            return False
        return True

    # ------------------------------------------------ 정규식
    def _find_regex(self, text: str) -> list[Span]:
        spans: list[Span] = []
        taken = [False] * len(text)
        for kind, pat in PATTERNS:
            for m in pat.finditer(text):
                s, e = m.span(1) if pat.groups else m.span()
                val = text[s:e]
                if not val or any(taken[s:e]):
                    continue
                if pat.groups and (val in NAME_PLACE_STOP or val in ACAD_SUBJ
                                   or (kind != "ACADEMY" and not self._place_ok(val))):
                    continue
                if kind == "SCHOOL" and val.endswith(SCHOOL_PREFIX_STOP):
                    continue
                if kind == "ADDR" and not re.search(r"\d", val):
                    continue
                spans.append(Span(s, e, kind, val, key=val, source="regex"))
                taken[s:e] = [True] * (e - s)
        return spans

    def _place_ok(self, val: str) -> bool:
        """아파트 · 「OO중 N학년」 자리에 조사 · 용언 · 부사 · 감탄사가 섞이면 이름이 아님(어제 아파트 · 같다고 2학년 · 아니고 2학년).
        학원 · 센터 · 태권도는 바로 붙어 문맥이 강해서 안 본다(아라 · 맑은샘 은 감탄사 · 용언으로 읽힘)."""
        bad = ("XSV", "XSA", "MAG", "IC", "NP", "NR")
        return not any(t.tag.startswith(("J", "V", "E")) or t.tag in bad for t in self.kiwi_plain.tokenize(val))

    # ------------------------------------------------ 성 + 이름 (어른 실명)
    def _full_ok(self, form: str) -> bool:
        if (form in FULL_STOP or form.endswith("님") or form[:2] in ("선생", "어머", "아버", "할머", "할아")
                or form in NNP_STOP or not is_hangul(form)):
            return False
        toks = self.kiwi_plain.tokenize(form)
        if toks and toks[-1].tag.startswith("J") and toks[-1].form in ("가", "이", "의", "는", "은", "를", "을", "도", "와", "과", "랑", "로", "에"):
            return False  # 두 글자 이름 + 조사(연우가 · 라미의) — 두 글자 이름 쪽이 맡음
        for k, t in enumerate(toks):
            # 조사가 붙으면 낱말(마음 + 이 · 사과 + 는). 박진 + 아(JKV) · 설미(NNP) + 나 처럼 앞이 고유명사면 받음
            if t.tag.startswith("J") and t.tag != "JKV" and not (k > 0 and toks[k - 1].tag == "NNP"):
                return False
            if t.tag.startswith("V") or t.tag in ("XSV", "XSA", "ETM", "ETN", "EC"):
                return False
        return not (len(toks) == 1 and toks[0].tag in ("MAG", "MM", "NR", "NP", "NNB"))

    def _full_names(self, text: str) -> list[str]:
        found: list[str] = []
        for a in self.adults:  # 어른 명단: 붙여 쓴 것 · 띄어 쓴 것
            for f in (a, a[0] + " " + a[1:]):
                if f in text and f not in found:
                    found.append(f)
        if self.adult_typos:  # 어른 명단 오타(정수지 ← 정수진): 낱말 첫머리 + 이름 뒤 경계
            for i in range(len(text) - 2):
                w = text[i:i + 3]
                if (w in self.adult_typos and w not in found and (i == 0 or not is_hangul(text[i - 1]))
                        and FULL_FOLLOW.match(text, i + 3)):
                    found.append(w)
        for pat in FULL_RULES:
            for m in pat.finditer(text):
                f = m.group(1)
                c = f.replace(" ", "")
                if (c[2] == "이" and batchim_class(c[1]) != 0) or c[2] in "가의는를을도와과랑":
                    continue  # 유진이 · 연우가 · 라미의: 두 글자 이름 + 조사 (두 글자 이름 쪽이 맡음, 이름 끝 글자로 드문 것만)
                if f not in found and FULL_FOLLOW.match(text, m.end(1)) and self._full_ok(c):
                    found.append(f)
        return found

    def _sweep_full(self, text: str, fulls: list[str], taken: list[bool]) -> list[Span]:
        """성까지 붙은 모양만 가린다(이름 두 글자만 따로 훑지 않음: 정하나 → 「하나」 낱말을 건드리지 않게)."""
        spans: list[Span] = []
        for f in fulls:
            for m in re.finditer(rf"(?<![가-힣]){re.escape(f)}", text):
                s, e = m.span()
                c = f.replace(" ", "")
                follow = FULL_FOLLOW_LISTED if c in self._adult_set else FULL_FOLLOW
                if not follow.match(text, e) or any(taken[s:e]):
                    continue
                spans.append(Span(s, e, "NAME", f, key=c[1:], surname=c[0], source="full"))
                taken[s:e] = [True] * (e - s)
        return spans

    # ------------------------------------------------ 이름 1단계: 후보
    def _name_context_ok(self, toks, i: int) -> bool:
        """명단에 없는 NNP 가 이름 자리에 있는지."""
        nx = toks[i + 1] if i + 1 < len(toks) else None
        pv = toks[i - 1] if i > 0 else None
        if nx is None:
            return True
        if nx.tag in ("XSN", "JKV") and nx.form in ("이", "아", "야"):
            return True
        if nx.form in KIN or nx.form in TITLE or nx.tag.startswith("J") or nx.tag == "VCP":
            return True
        return pv is not None and pv.form in REL

    def _candidates(self, text: str) -> dict[str, str]:
        """이 글에 나온 이름 후보 {이름: 출처}."""
        found: dict[str, str] = {}
        toks = self.kiwi.tokenize(text)
        for i, t in enumerate(toks):
            if t.tag != "NNP":
                continue
            s, e = t.start, t.start + t.len
            form = text[s:e]
            if len(form) == 3 and form[-1] == "이" and batchim_class(form[1]) != 0:
                form = form[:2]  # 「재원이」 → 재원
            if not is_hangul(form) or form in NNP_STOP:
                continue
            if len(form) == 3 and form[0] in SURNAMES:
                given = form[1:]
            elif len(form) == 2:
                given = form
            else:
                continue  # 한 글자 조각, 네 글자 이상은 건너뜀
            if given in NNP_STOP or given[-1] in "의를을":
                continue  # 라 + 미의: 이름 끝 글자로 안 쓰는 조사
            if given in self.roster:
                found.setdefault(given, "roster")
                continue
            # 낱말 중간 조각(인권위 → 권위, 방충망 → 충망)은 버림
            if s > 0 and is_hangul(text[s - 1]) and not (text[s - 1] in SURNAMES and len(form) == 2):
                continue
            if self._name_context_ok(toks, i):
                found.setdefault(given, "kiwi")

        # Kiwi 가 이름을 낱말로 잘못 읽거나 쪼개도(서진 → NNG, 은찬 → 은 + 찬) 뒤의 사람 접미사 「이」(XSN)는
        # 잘 붙인다: 낱말 첫머리부터 그 「이」 앞까지가 받침 있는 두 글자면 이름으로 본다.
        for t in toks:
            if t.tag != "XSN" or t.form != "이":
                continue
            ws = t.start
            while ws > 0 and is_hangul(text[ws - 1]):
                ws -= 1
            stem = text[ws:t.start]
            if len(stem) == 3 and stem[0] in SURNAMES:
                stem = stem[1:]
            if len(stem) == 2 and batchim_class(stem) != 0 and stem not in NNP_STOP:
                found.setdefault(stem, "roster" if stem in self.roster else "kiwi")

        kin, rel = "|".join(KIN), "|".join(REL)
        rules = [
            re.compile(rf"(?<![가-힣])(?:우리|저희|울)\s([가-힣]{{2}})(?=이|가|는|를|랑|한테|도|만|의|\s|[,.!?])"),
            re.compile(rf"(?<![가-힣])([가-힣]{{2}})(?:이)?\s?(?:{kin})(?![가-힣]{{2}})"),
            re.compile(rf"(?<![가-힣])(?:{rel})\s([가-힣]{{2}})(?=이[가는를랑]|가|는|랑|한테|를|아(?![가-힣])|야(?![가-힣]))"),
            # 받침 있는 두 글자 + 「이」: 시연이 팔 · 소담이 건데 (어린이 · 사람이 같은 낱말은 _not_a_word 가 거름)
            re.compile(r"(?<![가-힣0-9])([가-힣]{2})(?=이(?:[\s,.!?]|가|는|를|랑|한테|도|만|네|의|었|였|에요|예요))"),
        ]
        for pat in rules:
            for m in pat.finditer(text):
                g = m.group(1)
                if g in found:
                    continue
                if pat is rules[3] and batchim_class(g) == 0:
                    continue
                if g in self.roster or self._not_a_word(g):
                    found[g] = "rule"
        for name in self.roster:  # 명단 이름이 글에 있으면 후보
            if name in text:
                found.setdefault(name, "roster")
        if self.roster_typos:  # 명단 이름 오타(민쥰 · 지후 ← 민준 · 지호): 낱말 첫머리(성 붙어도 됨) + 이름 뒤 경계
            for i in range(len(text) - 1):
                w = text[i:i + 2]
                if w not in self.roster_typos or w in found:
                    continue
                start_ok = i == 0 or not is_hangul(text[i - 1]) or (
                    text[i - 1] in SURNAMES and (i == 1 or not is_hangul(text[i - 2])))
                if not (start_ok and FOLLOW.match(text, i + 2)):
                    continue
                # 오타 모양은 일반 낱말과 잘 겹치고(해서 · 사이 · 기준) Kiwi 도 모르는 낱말을 일반 명사로 읽어 못 가른다.
                # 그래서 이름 자리 단서가 뚜렷할 때만 받는다(민중이랑 · 지후 엄마 · 우리 지후)
                if not (TYPO_AFTER.match(text, i + 2) or TYPO_BEFORE.search(text[:i])):
                    continue
                if any(tk.tag.startswith(("V", "E", "XS")) for tk in self.kiwi_plain.tokenize(w)):
                    continue  # 용언 활용형(친구 때린 · 동생 나온)
                found[w] = "typo"
        return found

    # ------------------------------------------------ 이름 2단계: 훑기
    def _sweep(self, text: str, names: dict[str, str], taken: list[bool]) -> list[Span]:
        spans: list[Span] = []
        surn = "".join(sorted(SURNAMES))
        for name in sorted(names, key=len, reverse=True):
            pat = re.compile(rf"(?<![가-힣])([{surn}])?{re.escape(name)}")
            for m in pat.finditer(text):
                s, e = m.span()
                surname = m.group(1) or ""
                follow = FOLLOW_LISTED if names[name] == "roster" else FOLLOW
                if not follow.match(text, e):
                    continue  # 지우개 · 하준비 …
                if any(taken[s:e]):
                    continue
                spans.append(Span(s, e, "NAME", text[s:e], key=name, surname=surname, source=names[name]))
                taken[s:e] = [True] * (e - s)
        return spans

    def find(self, text: str) -> list[Span]:
        spans = self._find_regex(text)
        taken = [False] * len(text)
        for sp in spans:
            taken[sp.start:sp.end] = [True] * (sp.end - sp.start)
        cands = self._candidates(text)
        # 성 + 이름을 먼저 가린다(두 글자 이름 훑기는 「변상우인데요」의 「인데」를 이름 끝으로 안 받아서)
        spans += self._sweep_full(text, self._full_names(text), taken)
        spans += self._sweep(text, cands, taken)
        return sorted(spans, key=lambda x: x.start)

    # ------------------------------------------------ 가짜 값
    def _fake_name(self, given: str, used: set[str], text: str) -> str:
        pool = self._fake_pool[batchim_class(given)]
        cand = [n for n in pool if n not in used and n not in text and n != given]
        return self.rng.choice(cand or pool)

    def _fake_value(self, sp: Span, n: int, text: str, used: set[str]) -> str:
        if sp.kind == "PHONE":
            return f"010-0000-{1000 + n:04d}"
        if sp.kind == "EMAIL":
            return f"parent{n}@example.com"
        if sp.kind == "RRN":
            return f"000000-{3000000 + n:07d}"
        if sp.kind == "ACCOUNT":
            return f"000-0000-{n:04d}"
        if sp.kind == "ADDR":
            return f"가상로 {n}"
        if sp.kind == "APT":
            if not re.search(r"\d", sp.orig):  # 아파트 이름
                for a in FAKE_APTS:
                    if a not in text and a not in used:
                        return a
            return f"{100 + n}동 {100 + n}호"
        if sp.kind == "CAR":
            return f"00가 {1000 + n:04d}"
        if sp.kind in ("SCHOOL", "ACADEMY"):
            for s in FAKE_SCHOOLS:
                if s not in text and s not in used:
                    return s
        return f"가상{n}"

    # ------------------------------------------------ 공개 함수
    def mask(self, text: str, mapping: Mapping | None = None) -> tuple[str, Mapping]:
        """mapping 을 넘기면 같은 대화의 이전 메시지와 같은 가짜 값을 이어 쓴다."""
        mp = mapping or Mapping()
        used = set(mp.fake2orig)
        out, last = [], 0
        for sp in self.find(text):
            out.append(text[last:sp.start])
            if sp.kind == "NAME":
                if sp.key not in mp.orig2fake:
                    fake = self._fake_name(sp.key, used, text)
                    used.add(fake)
                    mp.add(sp.key, fake, "NAME")
                fake = mp.orig2fake[sp.key]
                if sp.surname:
                    full = sp.orig  # 김민준
                    if full not in mp.orig2fake:
                        fs = self.rng.choice([s for s in FAKE_SURNAMES if s != sp.surname])
                        mp.add(full, fs + fake, "NAME")
                    fake = mp.orig2fake[full]
            else:
                if sp.orig not in mp.orig2fake:
                    fake = self._fake_value(sp, len(mp.fake2orig) + 1, text, used)
                    used.add(fake)
                    mp.add(sp.orig, fake, sp.kind)
                fake = mp.orig2fake[sp.orig]
            out.append(fake)
            last = sp.end
        out.append(text[last:])
        return "".join(out), mp

    @staticmethod
    def unmask(text: str, mp: Mapping) -> str:
        """가짜 값 → 원래 값. 긴 것부터 한 번에 바꿔서 겹침 · 연쇄 치환을 막는다."""
        if not mp.fake2orig:
            return text
        keys = sorted(mp.fake2orig, key=len, reverse=True)
        pat = re.compile("|".join(map(re.escape, keys)))
        return pat.sub(lambda m: mp.fake2orig[m.group(0)], text)

    def check_response(self, response: str, mp: Mapping, masked_input: str) -> list[str]:
        """복원 전 응답 점검: 가린 입력에 없던 이름이 응답에 생겼는지(LLM 이 지어낸 이름) 경고."""
        warns = []
        for sp in self.find(response):
            if sp.kind == "NAME" and sp.key not in mp.fake2orig and sp.key not in masked_input:
                warns.append(f"입력에 없던 이름 '{sp.orig}' (응답 {sp.start}번째 글자)")
        return warns
