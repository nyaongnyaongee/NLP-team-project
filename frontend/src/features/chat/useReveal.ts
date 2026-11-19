// 새로 생긴 블록(폼 · 오류 · 추출 결과)이 화면 밖이면 보이는 곳까지만 스크롤한다. 이미 보이면 움직이지 않는다.
// 모션을 줄이는 설정이면 부드럽게 움직이지 않고 바로 이동한다.
export function revealElement(el: Element | null | undefined) {
  if (!el) return
  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
  el.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
}

// 요소에 ref={revealRef} 를 달면 그 요소가 화면에 생길 때 한 번 revealElement 한다 (조건부로 나타나는 블록용).
export const revealRef = (el: HTMLElement | null) => {
  if (el) revealElement(el)
}
