import { useState } from 'react'
import type { Conversation } from '../../api/types'
import type { SortControl } from './SortSelect'
import { SORT_KEYS, defaultSortDesc, sortConversations, sortOptions, type ConversationSortKey } from './sortConversations'
import { usePersistedSort } from './usePersistedSort'

export type ConversationStatus = 'open' | 'closed'

// 대화 목록을 「대화 중」 / 「종료된 대화」로 나눠 보고 (교사·학부모 공용), 탭마다 정렬(항목 + 방향)을 따로 기억한다.
// shown 은 정렬된 목록이다 (ConversationList 는 받은 순서대로 그린다).
export function useStatusFilter(conversations: Conversation[], role: 'teacher' | 'parent' = 'teacher') {
  const [show, setShow] = useState<ConversationStatus>('open')
  const openKeys = role === 'teacher' ? SORT_KEYS.teacherOpen : SORT_KEYS.parentOpen
  const closedKeys = role === 'teacher' ? SORT_KEYS.teacherClosed : SORT_KEYS.parentClosed
  // 저장 키의 v2: 예전 저장값은 방향의 뜻이 달랐다 (예전에는 desc=false 가 최신 순)
  const [openSort, pickOpen] = usePersistedSort<ConversationSortKey>('ieum:sort:v2:open', openKeys, 'recent', defaultSortDesc)
  const [closedSort, pickClosed] = usePersistedSort<ConversationSortKey>('ieum:sort:v2:closed', closedKeys, 'recent', defaultSortDesc)

  const sort = show === 'closed' ? closedSort : openSort
  const sortControl: SortControl = {
    options: sortOptions(show === 'closed' ? closedKeys : openKeys),
    value: sort.key,
    desc: sort.desc,
    onPick: (value) => (show === 'closed' ? pickClosed : pickOpen)(value as ConversationSortKey),
  }

  const openCount = conversations.filter((c) => c.status !== 'closed').length
  const shown = sortConversations(
    conversations.filter((c) => (show === 'closed') === (c.status === 'closed')),
    sort.key,
    sort.desc,
  )
  return { show, setShow, shown, openCount, closedCount: conversations.length - openCount, sortControl }
}
