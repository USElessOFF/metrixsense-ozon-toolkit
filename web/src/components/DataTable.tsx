import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { downloadCsv } from '../lib/csv'
import { Empty } from './ui'

export interface Column<T> {
  key: string
  title: string
  render?: (row: T) => ReactNode
  value?: (row: T) => string | number | null
  align?: 'right' | 'left'
}

interface Props<T> {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T, index: number) => string | number
  filter?: (row: T, query: string) => boolean
  csvName?: string
  expanded?: (row: T) => ReactNode
  emptyText?: string
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  filter,
  csvName,
  expanded,
  emptyText = 'Нет данных',
}: Props<T>) {
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null)
  const [openKey, setOpenKey] = useState<string | number | null>(null)

  const visible = useMemo(() => {
    let out = rows
    if (filter && query.trim()) {
      const q = query.trim().toLowerCase()
      out = out.filter(r => filter(r, q))
    }
    if (sort) {
      const col = columns.find(c => c.key === sort.key)
      if (col?.value) {
        out = [...out].sort((a, b) => {
          const va = col.value!(a)
          const vb = col.value!(b)
          if (va === null) return 1
          if (vb === null) return -1
          if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * sort.dir
          return String(va).localeCompare(String(vb), 'ru') * sort.dir
        })
      }
    }
    return out
  }, [rows, columns, filter, query, sort])

  const toggleSort = (key: string) =>
    setSort(s => (s?.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }))

  const exportCsv = () => {
    if (!csvName) return
    downloadCsv(
      csvName,
      columns.map(c => c.title),
      visible.map(r => columns.map(c => (c.value ? c.value(r) : ''))),
    )
  }

  if (rows.length === 0) return <Empty text={emptyText} />

  return (
    <div className="datatable">
      {(filter || csvName) && (
        <div className="datatable-tools">
          {filter && (
            <input
              className="input"
              placeholder="Поиск…"
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          )}
          {csvName && (
            <button className="btn ghost" onClick={exportCsv}>
              CSV
            </button>
          )}
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {expanded && <th />}
              {columns.map(c => (
                <th
                  key={c.key}
                  className={c.align === 'right' ? 'num' : undefined}
                  onClick={() => c.value && toggleSort(c.key)}
                  title={c.value ? 'Сортировать' : undefined}
                >
                  {c.title}
                  {sort?.key === c.key && (sort.dir === 1 ? ' ↑' : ' ↓')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={columns.length + (expanded ? 1 : 0)} className="state">
                  Ничего не найдено
                </td>
              </tr>
            )}
            {visible.map((row, idx) => {
              const key = rowKey(row, idx)
              return (
                <FragmentRow
                  key={key}
                  open={expanded ? openKey === key : false}
                  onToggle={expanded ? () => setOpenKey(k => (k === key ? null : key)) : undefined}
                  columns={columns}
                  row={row}
                  extra={expanded ? expanded(row) : null}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function FragmentRow<T>({
  open,
  onToggle,
  columns,
  row,
  extra,
}: {
  open: boolean
  onToggle?: () => void
  columns: Column<T>[]
  row: T
  extra: ReactNode
}) {
  return (
    <>
      <tr className={open ? 'opened' : undefined}>
        {onToggle && (
          <td>
            <button className="btn ghost tiny" onClick={onToggle} aria-label="Развернуть">
              {open ? '−' : '+'}
            </button>
          </td>
        )}
        {columns.map(c => (
          <td key={c.key} className={c.align === 'right' ? 'num' : undefined}>
            {c.render ? c.render(row) : c.value ? c.value(row) : ''}
          </td>
        ))}
      </tr>
      {open && extra && (
        <tr className="extra-row">
          <td colSpan={columns.length + 1}>{extra}</td>
        </tr>
      )}
    </>
  )
}
