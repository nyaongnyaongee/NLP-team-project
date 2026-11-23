// 시연용 역할 카드 (실제 교권침해 사례 모음집을 각색). QR 주소 /join?code=…&card=<id> 로 들어오면
// 학부모 「메시지 작성」 위에 이 카드가 뜬다. 고른 카드는 이 폰에만 둔다 (서버에 안 보냄).
// 로그인과 같이: 탭(sessionStorage)을 먼저, 없으면 브라우저(localStorage). 한 노트북에서 탭마다 다른 카드로 시험할 수 있게.

export type Scenario = {
  id: string
  emoji: string
  title: string
  heat: string // 분노 게이지 (🔥 개수)
  situation: string[]
  missions: string[]
  hint: string // 「막히면」 예시 문장
  note?: string
}

export const SCENARIOS: Scenario[] = [
  {
    id: 'medifoam',
    emoji: '🩹',
    title: '메디폼 대첩',
    heat: '🔥🔥🔥🔥',
    situation: [
      '쉬는 시간에 친구 손톱에 긁혀 아이 팔에 0.5cm 상처가 났다. 보건실에선 연고만 발라 줬다.',
      '메디폼 하나 붙이는 게 그렇게 어렵나? 흉 지면 누가 책임지는데?',
    ],
    missions: ['흉 지면 책임질 거냐고 따지기', '선생님 자격까지 들먹이기', '내일까지 해명하라고 하기'],
    hint: '야 메디폼 하나 붙이는 게 그렇게 어렵냐? 흉 지면 니가 책임질 거야?',
  },
  {
    id: 'five-calls',
    emoji: '📞',
    title: '하루 다섯 번 전화해',
    heat: '🔥🔥🔥🔥🔥',
    situation: [
      '아이가 결국 학교폭력 가해자로 신고됐다. 알고 보니 하루에 다섯 번씩 친구와 싸웠단다.',
      '선생님은 그동안 상담했다는데… 그럼 다섯 번 싸웠으면 다섯 번 전화했어야지!',
    ],
    missions: ['왜 그때그때 안 알려 줬냐고 따지기', '이게 다 담임 탓이라고 몰아붙이기', '교장 선생님께 말하겠다고 하기'],
    hint: '애가 하루에 다섯 번 싸웠으면 다섯 번 전화를 했어야죠! 담임이 하는 게 뭐예요?',
  },
  {
    id: 'morning-call',
    emoji: '⏰',
    title: '모닝콜 서비스',
    heat: '🔥🔥🔥🔥',
    situation: [
      '나는 일찍 출근했는데 아이와 남편이 아직 자는 것 같다.',
      '선생님께 출근길에 우리 집 들러 초인종 눌러서 깨워 달라고 했는데 거절당했다. 그거 잠깐이면 되는데?',
    ],
    missions: ['거절당한 것에 폭발하기', '애가 지각하면 선생님 책임이라고 하기'],
    hint: '출근길에 초인종 한 번 누르는 게 그렇게 어려워요? 애 지각하면 선생님 책임이에요.',
  },
  {
    id: 'coffee',
    emoji: '☕',
    title: '커피 한 잔의 무게',
    heat: '🔥🔥🔥🔥🔥',
    situation: [
      '아이를 데리러 학교에 갔는데, 커피 한 잔 안 내준다. 완전히 무시당한 기분이다.',
      '이건 사과로 끝날 일이 아니다.',
    ],
    missions: ['무시당한 것에 분노하기', '무릎 꿇고 사과하든지 담임을 바꾸라고 하기'],
    hint: '학부모가 왔는데 커피 한 잔 안 줘요? 사람 무시하는 거예요? 무릎 꿇고 사과하세요.',
  },
  {
    id: 'vip',
    emoji: '👑',
    title: 'VIP 예약석',
    heat: '🔥 → 🔥🔥🔥 → 🔥🔥🔥🔥🔥',
    situation: [
      '새 학기 첫날, 담임에게 세 가지를 확실히 해 두고 싶다. ① 자리는 앞쪽 고정 ② 심부름은 우리 아이만 ③ 하루에 칭찬 한 번은 꼭',
      '…그런데 일주일이 지나도 하나도 안 지켜진다.',
    ],
    missions: ['1차: 정중하게 부탁하기', '2차: 「저번에 말씀드렸는데요?」', '3차: 폭발 💥'],
    hint: '몇 번을 말해야 알아들어요? 칭찬 한 번 하는 게 그렇게 힘들어?',
    note: '시간을 두고 세 번 보내 보세요. 같은 요구가 쌓이면 선생님은 민원 이관을 할 수 있습니다.',
  },
  {
    id: 'law',
    emoji: '⚖️',
    title: '법전을 든 학부모',
    heat: '🔥🔥🔥🔥🔥',
    situation: [
      '학교폭력 상담이 내 뜻대로 안 풀렸다. 담임은 대체 한 게 뭔가?',
      '휴대폰에는 아동학대 법 조항을 복사해 두었다.',
    ],
    missions: ['법 조항을 들먹이며 「이거 아시죠 선생님?」', '신고 · 교육청 등 다음 단계 예고하기'],
    hint: '아동학대처벌법 아시죠 선생님? 계속 이러시면 신고합니다.',
  },
]

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
