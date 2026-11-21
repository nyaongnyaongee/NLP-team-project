import type { ReactNode } from 'react'

// 초안의 check(보내기 전에 확인할 것)를 눈에 띄게 보여 준다 (노란 바탕과 테두리, app-layout.css 의 .draft-checks).
export default function DraftChecks({
  items,
  children,
  title = '보내기 전에 확인하세요',
}: {
  items: string[]
  children?: ReactNode
  title?: string
}) {
  return (
    <aside className="draft-checks" role="note" aria-label={title}>
      <strong>⚠ {title}</strong>
      {items.length === 0 ? (
        <p>특별히 확인할 것은 없어요. 그래도 한 번 읽어 보세요.</p>
      ) : (
        <ul>
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      )}
      {children}
    </aside>
  )
}
