import { useState, useMemo } from 'react'

function detectTable(text) {
  const lines = text.split('\n').filter(l => l.trim())
  if (lines.length < 3) return null
  if (!lines[0].trim().startsWith('|')) return null

  const headers = lines[0].split('|').map(c => c.trim()).filter(Boolean)
  if (headers.length < 2) return null

  const dataRows = []
  for (let i = 2; i < lines.length; i++) {
    if (!lines[i].trim().startsWith('|')) continue
    const cells = lines[i].split('|').map(c => c.trim()).filter(Boolean)
    if (cells.length === headers.length) {
      const row = {}
      headers.forEach((h, j) => {
        const num = parseFloat(cells[j].replace(/[$,%]/g, ''))
        row[h] = isNaN(num) ? cells[j] : num
      })
      dataRows.push(row)
    }
  }

  if (dataRows.length < 2) return null

  const numericCols = headers.filter(h =>
    dataRows.some(r => typeof r[h] === 'number')
  )
  if (numericCols.length === 0) return null

  const labelCol = headers.find(h => !numericCols.includes(h)) || headers[0]
  const valueCol = numericCols[0]
  const values = dataRows.map(r => ({ label: r[labelCol], value: typeof r[valueCol] === 'number' ? r[valueCol] : 0 }))

  return { headers, dataRows, labelCol, valueCol, values }
}

function BarChart({ data, width = 400, height = 200 }) {
  const max = Math.max(...data.map(d => d.value), 1)
  const barWidth = Math.max(20, Math.min(60, (width - 40) / data.length - 4))
  const padding = { top: 10, right: 10, bottom: 30, left: 50 }

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="inline-chart-svg">
      {data.map((d, i) => {
        const x = padding.left + i * (barWidth + 4)
        const barH = (d.value / max) * (height - padding.top - padding.bottom)
        const y = height - padding.bottom - barH
        return (
          <g key={i}>
            <rect
              x={x} y={y} width={barWidth} height={barH}
              fill="var(--primary)" rx="3"
              className="inline-chart-bar"
            >
              <title>{d.label}: {d.value}</title>
            </rect>
            <text x={x + barWidth / 2} y={height - 8} textAnchor="end" transform={`rotate(-45 ${x + barWidth / 2} ${height - 8})`} className="inline-chart-label">
              {d.label}
            </text>
            <text x={x + barWidth / 2} y={y - 4} textAnchor="middle" className="inline-chart-value">
              {d.value}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function InlineChart({ text }) {
  const [show, setShow] = useState(false)

  const tableData = useMemo(() => detectTable(text), [text])

  if (!tableData || tableData.values.length < 2) return null

  return (
    <div className="inline-chart">
      <button className="inline-chart-toggle toolbar-btn" onClick={() => setShow(!show)}>
        {show ? '📊 Hide chart' : '📊 Visualize'}
      </button>
      {show && (
        <div className="inline-chart-container">
          <BarChart data={tableData.values} />
        </div>
      )}
    </div>
  )
}
