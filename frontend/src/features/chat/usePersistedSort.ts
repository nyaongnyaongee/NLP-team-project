import { useCallback, useState } from 'react'

export type SortState<K extends string> = { key: K; desc: boolean }

// 정렬 선택(항목 + 방향)을 localStorage 에 기억한다. 읽기·쓰기가 막혀도(시크릿 창 등) 기본값으로 동작한다.
// allowed 는 바뀌지 않는 상수 배열이어야 한다. 저장된 값이 allowed 에 없으면 fallback 으로 돌아간다.
// defaultDesc(key): 그 항목을 처음 고를 때의 방향 (이름 순은 오름차순, 나머지는 내림차순)
export function usePersistedSort<K extends string>(
  storageKey: string,
  allowed: readonly K[],
  fallback: K,
  defaultDesc: (key: K) => boolean,
) {
  const [state, setState] = useState<SortState<K>>(() => {
    try {
      const raw = localStorage.getItem(storageKey)
      if (raw) {
        const v = JSON.parse(raw) as { key?: unknown; desc?: unknown }
        const key = allowed.find((k) => k === v.key)
        if (key && typeof v.desc === 'boolean') return { key, desc: v.desc }
      }
    } catch {
      // 저장소를 못 읽으면 기본값
    }
    return { key: fallback, desc: defaultDesc(fallback) }
  })
  const update = useCallback(
    (next: SortState<K>) => {
      setState(next)
      try {
        localStorage.setItem(storageKey, JSON.stringify(next))
      } catch {
        // 저장 실패는 무시: 이번 화면에서만 적용
      }
    },
    [storageKey],
  )
  // 항목을 고르면 그 항목의 기본 방향으로, 지금 항목을 한 번 더 고르면 방향만 바꾼다
  const pick = useCallback(
    (key: K) => update(key === state.key ? { key, desc: !state.desc } : { key, desc: defaultDesc(key) }),
    [state, update, defaultDesc],
  )
  return [state, pick] as const
}
