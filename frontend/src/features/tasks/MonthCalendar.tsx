import { useMemo, useState, type ReactNode } from 'react'
import { kstDateKey } from './formatDate'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const pad = (n: number) => String(n).padStart(2, '0')

// 한국 시각 기준 오늘의 { 연, 월(1~12) }
function todayMonth() {
  const [y, m] = (kstDateKey(new Date()) ?? '1970-01').split('-').map(Number)
  return { y, m }
}

type Dated = { id: number; due_at: string | null }

// 월 달력 + 고른 날의 일정 + 날짜 없는 일정 (교사·학부모 캘린더 공용). 한 줄을 어떻게 그릴지는 renderItem 이 정한다.
export default function MonthCalendar<T extends Dated>({
  items,
  loading,
  renderItem,
}: {
  items: T[]
  loading: boolean
  renderItem: (item: T) => ReactNode
}) {
  const [cursor, setCursor] = useState(todayMonth)
  const [selected, setSelected] = useState<string | null>(() => kstDateKey(new Date()))

  const { byDay, undated } = useMemo(() => {
    const byDay = new Map<string, T[]>()
    const undated: T[] = []
    for (const t of items) {
      const key = kstDateKey(t.due_at)
      if (key === null) undated.push(t)
      else byDay.set(key, [...(byDay.get(key) ?? []), t])
    }
    return { byDay, undated }
  }, [items])

  // 달력 칸: 첫 요일만큼 빈 칸, 그다음 1일부터 말일까지 (UTC 로 계산해 기기의 시간대에 영향받지 않게 한다)
  const firstWeekday = new Date(Date.UTC(cursor.y, cursor.m - 1, 1)).getUTCDay()
  const daysInMonth = new Date(Date.UTC(cursor.y, cursor.m, 0)).getUTCDate()

  const move = (delta: number) =>
    setCursor(({ y, m }) => {
      const d = new Date(Date.UTC(y, m - 1 + delta, 1))
      return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1 }
    })

  const selectedItems = selected ? (byDay.get(selected) ?? []) : []

  return (
    <>
      <div className="calendar-card">
        <div className="month-head">
          <button type="button" onClick={() => move(-1)} aria-label="이전 달">
            ‹
          </button>
          <b>
            {cursor.y}년 {cursor.m}월
          </b>
          <button type="button" onClick={() => move(1)} aria-label="다음 달">
            ›
          </button>
        </div>
        <div className="calendar-grid">
          {WEEKDAYS.map((w) => (
            <span key={w} className="weekday">
              {w}
            </span>
          ))}
          {Array.from({ length: firstWeekday }, (_, i) => (
            <span key={`blank-${i}`} />
          ))}
          {Array.from({ length: daysInMonth }, (_, i) => {
            const day = i + 1
            const key = `${cursor.y}-${pad(cursor.m)}-${pad(day)}`
            const count = byDay.get(key)?.length ?? 0
            return (
              <button
                key={key}
                type="button"
                className={`cal-day ${key === selected ? 'selected' : ''}`}
                onClick={() => setSelected(key)}
                aria-pressed={key === selected}
                aria-label={`${cursor.m}월 ${day}일${count > 0 ? `, 일정 ${count}개` : ''}`}
              >
                {day}
                {count > 0 && <i />}
              </button>
            )
          })}
        </div>
      </div>

      {selected && (
        <div>
          <div className="section-title">
            <h3>
              {Number(selected.slice(5, 7))}월 {Number(selected.slice(8, 10))}일 일정
            </h3>
            <span>{selectedItems.length}개</span>
          </div>
          {!loading && selectedItems.length === 0 && (
            <div className="empty" style={{ padding: '25px 10px' }}>
              이 날 일정이 없어요
            </div>
          )}
          <ul className="plain-list">{selectedItems.map(renderItem)}</ul>
        </div>
      )}

      {undated.length > 0 && (
        <div>
          <div className="section-title">
            <h3>기한 미지정 일정</h3>
            <span>{undated.length}개</span>
          </div>
          <ul className="plain-list">{undated.map(renderItem)}</ul>
        </div>
      )}
    </>
  )
}
