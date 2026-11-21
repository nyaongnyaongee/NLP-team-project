import { useSync } from './useSync'

// Q&A 목록을 최신으로 유지한다: {"type":"faq"} 이 오면 목록을 다시 읽는다.
export function useFaqSync(refresh: () => void) {
  useSync('faqs', refresh, (e) => e.type === 'faq')
}
