import TaskItem from './TaskItem'
import { useTaskList } from './useTaskList'

// 교사 "할 일" 탭: 추가된 할 일 목록, 체크(done), 수정, 삭제, 미완료 개수
export default function TodosTab() {
  const { tasks, loading, error, replace, remove } = useTaskList('todo')
  const remaining = tasks.filter((t) => t.status === 'added').length

  return (
    <section>
      <div className="eyebrow">MY TO-DO LIST</div>
      <div className="tool-heading">
        <h2>
          오늘의 할 일,
          <br />
          하나씩 체크하세요.
        </h2>
      </div>
      {!loading && !error && <p className="sub">미완료 {remaining}개</p>}
      {loading && <p className="loading">불러오는 중</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {!loading && !error && tasks.length === 0 && (
        <div className="empty">
          <div className="big">☑</div>등록된 할 일이 없어요
        </div>
      )}
      <ul className="plain-list">
        {tasks.map((t) => (
          <TaskItem key={t.id} task={t} variant="todo" onUpdated={replace} onRemoved={remove} />
        ))}
      </ul>
    </section>
  )
}
