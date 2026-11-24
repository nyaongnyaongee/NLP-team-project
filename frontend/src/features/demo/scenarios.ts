// 시연용 역할 카드 (실제 교권침해 사례 모음집을 각색). QR 주소 /join?code=…&card=<id> 로 들어오면
// 학부모 「메시지 작성」 위에 이 카드가 뜬다. 고른 카드는 이 폰에만 둔다 (서버에 안 보냄).
// 로그인과 같이: 탭(sessionStorage)을 먼저, 없으면 브라우저(localStorage). 한 노트북에서 탭마다 다른 카드로 시험할 수 있게.

export type Scenario = {
  id: string
  emoji: string
  title: string
  heat: number // 맵기 1~5 (🔥 개수). 고르기 화면은 순한 것부터
  heatText?: string // 🔥 개수 대신 보여 줄 글자 (VIP 처럼 점점 매워지는 카드)
  situation: string[] // 문단마다 하나, 문단 안 줄바꿈은 \n
  missions: string[]
  hint: string // 「막히면」 예시 문장
  note?: string
}

const ALL: Scenario[] = [
  {
    id: 'birthday',
    emoji: '🎂',
    title: '생일파티 실종 사건',
    heat: 1,
    situation: [
      '오늘은 우리 애기 생일이다.\n그런데 반에서 생일 노래 한 번을 안 불러 줬단다.',
      '다른 데는 다 해 준다던데?',
    ],
    missions: ['생일파티를 왜 안 해 줬는지 묻기', '다음 주에라도 꼭 해 달라고 하기'],
    hint: '오늘 우리 애기 생일인 거 모르셨어요?\n노래라도 한 번 불러 주시지 그러셨어요.',
  },
  {
    id: 'duck',
    emoji: '🦆',
    title: '오리주물럭 대첩',
    heat: 2,
    situation: [
      '급식에 오리주물럭이 나왔는데\n우리 애가 떡만 골라 먹는다고 선생님이 한마디 했단다.',
      '그럴 거면 오리 몇 개, 떡 몇 개 뜨라고\n써서 붙여 놓든가!',
    ],
    missions: ['애한테 지적한 걸 따지기', '오리 몇 개 떡 몇 개인지 정해 달라고 하기', '안 되면 교장실에 전화한다고 하기'],
    hint: '떡만 먹는다고 애한테 뭐라 하셨다면서요?\n그럼 오리 몇 개 떡 몇 개 뜨라고 써 붙여 놓으세요.',
  },
  {
    id: 'academy',
    emoji: '🚕',
    title: '학원 픽업 서비스',
    heat: 3,
    situation: [
      '갑자기 일이 생겼다.\n선생님께 아이를 학원까지 좀 데려다 달라고 했다.',
      '그런데 「근무 중이라 어렵다」고 거절당했다.\n학교 바로 옆 학원인데?',
    ],
    missions: ['그것도 못 해 주냐고 따지기', '학부모 부탁을 무시한다고 몰아붙이기'],
    hint: '학교 바로 옆인데 그것도 못 데려다주세요?\n학부모가 부탁하면 좀 들어 주셔야죠.',
  },
  {
    id: 'wedding',
    emoji: '💒',
    title: '3월의 신부',
    heat: 3,
    situation: [
      '담임 선생님이 3월 말에 결혼하고\n일주일 신혼여행을 다녀왔다.',
      '애들 새 학기 적응해야 할 때\n왜 하필 3월에 결혼을?',
    ],
    missions: ['왜 3월에 결혼했냐고 따지기', '학부모랑 상의도 없었다고 하기', '교원평가에 다 쓰겠다고 하기'],
    hint: '애들 적응해야 하는 3월에 결혼을 하시면 어떡해요?\n학부모한테 한마디 상의도 없이요?',
  },
  {
    id: 'night',
    emoji: '🌙',
    title: '밤 11시의 인성교육',
    heat: 5,
    situation: [
      '밤 11시에 선생님께 전화했는데 안 받는다.\n급한 일이었는데!',
      '학부모 전화도 안 받는 사람이\n애들한테 인성교육을 한다고?',
    ],
    missions: ['인성이 그 모양이냐고 따지기', '우리 애한테 사과문 써 오라고 하기', '안 하면 고소한다고 하기'],
    hint: '밤에 학부모 전화도 안 받는 사람이 인성교육을 해요?\n우리 애한테 사과문 써서 보내세요.',
  },
  {
    id: 'medifoam',
    emoji: '🩹',
    title: '메디폼 대첩',
    heat: 4,
    situation: [
      '쉬는 시간에 친구 손톱에 긁혀 아이 팔에 0.5cm 상처가 났다.\n보건실에선 연고만 발라 줬다.',
      '메디폼 하나 붙이는 게 그렇게 어렵나?\n흉 지면 누가 책임지는데?',
    ],
    missions: ['흉 지면 책임질 거냐고 따지기', '선생님 자격까지 들먹이기', '내일까지 해명하라고 하기'],
    hint: '야 메디폼 하나 붙이는 게 그렇게 어렵냐?\n흉 지면 니가 책임질 거야?',
  },
  {
    id: 'coffee',
    emoji: '☕',
    title: '커피 한 잔의 무게',
    heat: 5,
    situation: [
      '아이를 데리러 학교에 갔는데, 커피 한 잔 안 내준다.\n완전히 무시당한 기분이다.',
      '이건 사과로 끝날 일이 아니다.',
    ],
    missions: ['무시당한 것에 분노하기', '무릎 꿇고 사과하든지 담임을 바꾸라고 하기'],
    hint: '학부모가 왔는데 커피 한 잔 안 줘요?\n사람 무시하는 거예요? 무릎 꿇고 사과하세요.',
  },
  {
    id: 'vip',
    emoji: '👑',
    title: 'VIP 예약석',
    heat: 3,
    heatText: '🔥 → 🔥🔥🔥 → 🔥🔥🔥🔥🔥',
    situation: [
      '새 학기 첫날, 담임에게 세 가지를 확실히 해 두고 싶다.\n① 자리는 앞쪽 고정\n② 심부름은 우리 아이만\n③ 하루에 칭찬 한 번은 꼭',
      '…그런데 일주일이 지나도 하나도 안 지켜진다.',
    ],
    missions: ['1차: 정중하게 부탁하기', '2차: 「저번에 말씀드렸는데요?」', '3차: 폭발 💥'],
    hint: '몇 번을 말해야 알아들어요?\n칭찬 한 번 하는 게 그렇게 힘들어?',
    note: '시간을 두고 세 번 보내 보세요.\n같은 요구가 쌓이면 선생님은 민원 이관을 할 수 있습니다.',
  },
]

// 순한 것부터 (같은 맵기는 적은 순서대로)
export const SCENARIOS: Scenario[] = [...ALL].sort((a, b) => a.heat - b.heat)

const LEVEL = ['', '순한맛', '순한맛', '중간맛', '매운맛', '지옥맛']

export function heatLabel(s: Scenario): { fire: string; level: string } {
  return { fire: s.heatText ?? '🔥'.repeat(s.heat), level: s.heatText ? '점점 매워짐' : LEVEL[s.heat] }
}

export function findScenario(id: string | null | undefined): Scenario | null {
  return SCENARIOS.find((s) => s.id === id) ?? null
}

const KEY = 'ieum.demoCard'
// 시연 QR 로 들어왔지만 아직 상황을 안 고른 상태 (학부모 화면에 「상황 고르기」가 뜬다)
export const PICK = 'pick'

export function loadScenarioId(): string | null {
  try {
    return sessionStorage.getItem(KEY) ?? localStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function saveScenarioId(id: string | null): void {
  try {
    if (id) {
      sessionStorage.setItem(KEY, id)
      localStorage.setItem(KEY, id)
    } else {
      sessionStorage.removeItem(KEY)
      localStorage.removeItem(KEY)
    }
  } catch {
    // 저장하지 못해도 이번 화면에는 보인다
  }
}
