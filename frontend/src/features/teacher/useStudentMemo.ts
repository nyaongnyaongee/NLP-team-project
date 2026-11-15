import { useEffect, useRef, useState } from 'react'
import { getMemo, saveMemo } from '../../api/students'

const SAVE_DELAY = 800 // 입력을 멈추고 이만큼 지나면 저장 (ms)

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

// 학생 메모장 하나 (담임만 보고, Claude 에는 넣지 않는다). 저장 단추 없이 저절로 저장한다:
// 입력을 멈추고 0.8초 뒤, 칸을 벗어날 때, 화면을 떠날 때.
// 단추(MemoToggle)와 칸(MemoPanel)을 따로 놓을 수 있게 상태는 이 훅에 둔다 (대화방: 단추는 이름 옆, 칸은 그 아래).
export function useStudentMemo(studentId: number | null) {
  const [text, setText] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [state, setState] = useState<SaveState>('idle')
  const saved = useRef('') // 서버에 저장된 글
  const latest = useRef('') // 지금 칸에 있는 글 (떠날 때 저장용)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (studentId === null) return
    let alive = true
    getMemo(studentId).then(
      (m) => {
        if (!alive) return
        saved.current = latest.current = m.body
        setText(m.body)
        setLoaded(true)
      },
      (e: unknown) => alive && setLoadError(e instanceof Error ? e.message : '메모를 불러오지 못했습니다'),
    )
    return () => {
      alive = false
      window.clearTimeout(timer.current)
      if (latest.current !== saved.current) void saveMemo(studentId, latest.current).catch(() => {}) // 떠날 때 남은 것
    }
  }, [studentId])

  const save = async () => {
    window.clearTimeout(timer.current)
    const body = latest.current
    if (studentId === null || body === saved.current) return
    setState('saving')
    try {
      await saveMemo(studentId, body)
      saved.current = body
      setState(latest.current === body ? 'saved' : 'saving')
    } catch {
      setState('error')
    }
  }

  const change = (value: string) => {
    setText(value)
    latest.current = value
    setState('idle')
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => void save(), SAVE_DELAY)
  }

  return { text, loaded, loadError, state, save, change, hasMemo: text.trim() !== '' }
}

export type StudentMemoState = ReturnType<typeof useStudentMemo>
