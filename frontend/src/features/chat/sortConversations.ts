import type { Conversation } from '../../api/types'
import { parentTitle } from './chatTitle'
import type { SortOption } from './SortSelect'

// 대화 목록 정렬. 「최근 메시지 순」이 기본이고 (누가 보냈든 마지막 메시지), 종료된 대화 탭에만 「종료 순」이 있다.
// 방향은 항목마다 오름(↑)·내림(↓) 둘 다 된다.
export type ConversationSortKey = 'recent' | 'created' | 'unread' | 'name' | 'closed'

export const SORT_LABEL: Record<ConversationSortKey, string> = {
  recent: '최근 메시지 순',
  created: '생성 순',
  unread: '안 읽은 메시지 순',
  name: '이름 순',
  closed: '종료 순',
}

// 탭 · 화면별로 고를 수 있는 정렬. 이름 순은 교사 화면만 (학부모에게는 대화 상대가 담임 한 분이라 의미가 없다)
export const SORT_KEYS = {
  teacherOpen: ['recent', 'created', 'unread', 'name'],
  teacherClosed: ['recent', 'closed', 'created', 'unread', 'name'],
  parentOpen: ['recent', 'created', 'unread'],
  parentClosed: ['recent', 'closed', 'created', 'unread'],
} as const satisfies Record<string, readonly ConversationSortKey[]>

export const sortOptions = (keys: readonly ConversationSortKey[]): SortOption[] =>
  keys.map((k) => ({ value: k, label: SORT_LABEL[k] }))

// 처음 고를 때의 방향: 이름 순만 오름차순(가→하), 나머지는 내림차순(최신 · 많은 것이 위)
export const defaultSortDesc = (key: ConversationSortKey) => key !== 'name'

const ts = (s: string | null | undefined) => (s ? Date.parse(s) || 0 : 0)
const lastAt = (c: Conversation) => ts(c.last_message_at ?? c.created_at)
// 종료 시각. 이 열이 생기기 전에 닫은 대화는 마지막 메시지 시각으로 대신한다
const closedAt = (c: Conversation) => ts(c.closed_at ?? c.last_message_at ?? c.created_at)

// 모두 오름차순 비교이고, desc 면 뒤집는다 (같은 값은 번호 순)
const COMPARE: Record<ConversationSortKey, (a: Conversation, b: Conversation) => number> = {
  recent: (a, b) => lastAt(a) - lastAt(b),
  created: (a, b) => ts(a.created_at) - ts(b.created_at),
  unread: (a, b) => (a.unread ?? 0) - (b.unread ?? 0) || lastAt(a) - lastAt(b),
  closed: (a, b) => closedAt(a) - closedAt(b),
  name: (a, b) => parentTitle(a).localeCompare(parentTitle(b), 'ko'),
}

export function sortConversations(
  list: Conversation[],
  key: ConversationSortKey = 'recent',
  desc: boolean = defaultSortDesc(key),
): Conversation[] {
  const sign = desc ? -1 : 1
  return [...list].sort((a, b) => sign * (COMPARE[key](a, b) || a.id - b.id))
}
