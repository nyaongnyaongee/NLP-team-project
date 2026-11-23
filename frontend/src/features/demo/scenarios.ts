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
    id: 'samdasoo',
    emoji: '💧',
    title: '삼다수 불평등 조약',
    heat: 1,
    situation: [
      '아이 말로는 선생님만 교실에서\n집에서 가져온 삼다수를 마신다고 한다.',
      '애들은 정수기 물 마시는데?\n선생님만?',
    ],
    missions: ['선생님만 삼다수 마시는 걸 따지기', '애들한테도 나눠 달라고 하기'],
    hint: '선생님만 삼다수 드세요?\n애들한테도 좀 나눠 주세요.',
  },
  {
    id: 'iphone',
    emoji: '📱',
    title: '아이폰 금지령',
    heat: 2,
    situation: [
      '아이가 요즘 최신형 아이폰을 사 달라고 매일 조른다.\n이유를 물으니 담임 선생님 폰이란다.',
      '선생님 때문에 우리 집이 난리다.',
    ],
    missions: ['교실에서 아이폰 쓰지 말아 달라고 하기', '애들 보는 앞에서 생각 좀 하시라고 하기'],
    hint: '선생님 폰 때문에 애가 매일 아이폰 사 달라고 난리예요.\n교실에서는 좀 안 쓰시면 안 될까요?',
  },
  {
    id: 'stamp',
    emoji: '📒',
    title: '칭찬 도장 실종 사건',
    heat: 2,
    situation: [
      '아이(2학년)가 열심히 쓴 일기에 칭찬 도장이 없다.\n코멘트도 없다.',
      '금요일 오후 5시.\n주말 전에 꼭 말해야겠다.',
    ],
    missions: ['도장 · 코멘트를 왜 안 해 줬는지 묻기', '주말에 일기장 두고 갈 테니 검사해 달라고 하기'],
    hint: '애가 일기를 썼는데 도장 하나 안 찍어 주셨더라고요.\n주말에 학교 앞에 두고 갈 테니 검사해 주세요.',
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
    id: 'five-calls',
    emoji: '📞',
    title: '하루 다섯 번 전화해',
    heat: 5,
    situation: [
      '아이가 결국 학교폭력 가해자로 신고됐다.\n알고 보니 하루에 다섯 번씩 친구와 싸웠단다.',
      '선생님은 그동안 상담했다는데…\n그럼 다섯 번 싸웠으면 다섯 번 전화했어야지!',
    ],
    missions: ['왜 그때그때 안 알려 줬냐고 따지기', '이게 다 담임 탓이라고 몰아붙이기', '교장 선생님께 말하겠다고 하기'],
    hint: '애가 하루에 다섯 번 싸웠으면 다섯 번 전화를 했어야죠!\n담임이 하는 게 뭐예요?',
  },
  {
    id: 'morning-call',
    emoji: '⏰',
    title: '모닝콜 서비스',
    heat: 3,
    situation: [
      '나는 일찍 출근했는데 아이와 남편이 아직 자는 것 같다.',
      '선생님께 출근길에 우리 집 초인종 눌러서\n애 좀 깨워 달라고 했는데 거절당했다.\n그거 잠깐이면 되는데?',
    ],
    missions: ['거절당한 것에 폭발하기', '애가 지각하면 선생님 책임이라고 하기'],
    hint: '출근길에 초인종 한 번 누르는 게 그렇게 어려워요?\n애 지각하면 선생님 책임이에요.',
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
  {
    id: 'law',
    emoji: '⚖️',
    title: '법전을 든 학부모',
    heat: 5,
    situation: [
      '학교폭력 상담이 내 뜻대로 안 풀렸다.\n담임은 대체 한 게 뭔가?',
      '휴대폰에는 아동학대 법 조항을 복사해 두었다.',
    ],
    missions: ['법 조항을 들먹이며 「이거 아시죠 선생님?」', '신고 · 교육청 등 다음 단계 예고하기'],
    hint: '아동학대처벌법 아시죠 선생님?\n계속 이러시면 신고합니다.',
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
