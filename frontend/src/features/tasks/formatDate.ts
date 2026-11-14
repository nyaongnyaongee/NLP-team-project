// 할 일·일정의 날짜는 모두 이 파일을 거친다 (명세 S5).
//
// 서버의 due_at 은 시간대 오프셋이 붙어 온다 (예: "2026-11-20T00:00:00+09:00").
// 근거: 서버가 쓰는 DB 연결(TimeZone=Asia/Seoul)에서 같은 모델로 직렬화해 본 결과.
// 오프셋이 없는 문자열이 오면 JS 는 그것을 "이 기기의 시각"으로 읽으므로, 한국 시각으로 취급해 +09:00 을 붙여 읽는다.
// 시각이 없는 항목은 그날 00:00 (한국 시각) 으로 오므로, 00:00 이면 날짜만 표시한다.

const TZ = 'Asia/Seoul'
export const NO_DUE = '기한 미지정'

const HAS_OFFSET = /(Z|[+-]\d{2}:?\d{2})$/i

function parse(value: string | Date | null): Date | null {
  if (value === null) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value
  const text = HAS_OFFSET.test(value) ? value : `${value}+09:00`
  const d = new Date(text)
  return Number.isNaN(d.getTime()) ? null : d
}

const partsFormatter = new Intl.DateTimeFormat('en-US', {
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

function kstParts(d: Date) {
  const get = (type: string) => partsFormatter.formatToParts(d).find((p) => p.type === type)?.value ?? '00'
  return { y: get('year'), m: get('month'), d: get('day'), h: get('hour'), min: get('minute') }
}

const dateOnly = new Intl.DateTimeFormat('ko-KR', { timeZone: TZ, month: 'long', day: 'numeric' })
const dateAndTime = new Intl.DateTimeFormat('ko-KR', {
  timeZone: TZ,
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
})

// 화면에 보이는 날짜 문장. 예: "11월 20일", "11월 20일 오후 3:20", 없으면 "기한 미지정"
export function formatDate(value: string | null): string {
  const d = parse(value)
  if (d === null) return NO_DUE
  const p = kstParts(d)
  return p.h === '00' && p.min === '00' ? dateOnly.format(d) : dateAndTime.format(d)
}

const timeOnly = new Intl.DateTimeFormat('ko-KR', { timeZone: TZ, hour: 'numeric', minute: '2-digit', hour12: true })

// 캘린더의 일정 시각. 시각이 없는 일정(그날 00:00)은 "종일", 날짜가 없으면 "기한 미지정"
export function formatTimeOfDay(value: string | null): string {
  const d = parse(value)
  if (d === null) return NO_DUE
  const p = kstParts(d)
  return p.h === '00' && p.min === '00' ? '종일' : timeOnly.format(d)
}

// 한국 시각 기준 날짜 키 "YYYY-MM-DD". 날짜가 없으면 null (달력에서 날짜별로 묶을 때 쓴다).
export function kstDateKey(value: string | Date | null): string | null {
  const d = parse(value)
  if (d === null) return null
  const p = kstParts(d)
  return `${p.y}-${p.m}-${p.d}`
}

// <input type="date"> 에 넣을 값. 날짜가 없으면 빈 문자열.
export function toDateInput(value: string | null): string {
  return kstDateKey(value) ?? ''
}

// <input type="date"> 값 → 서버에 보낼 값. 빈 문자열은 날짜 지우기(null). 시각은 그날 00:00 (한국 시각).
export function fromDateInput(date: string): string | null {
  return date === '' ? null : `${date}T00:00:00+09:00`
}
