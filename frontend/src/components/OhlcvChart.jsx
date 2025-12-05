import React, { useEffect, useMemo, useState } from 'react'
import api from '../api'

// Professional trading chart with live updates
export default function OhlcvChart({ symbol, height = 220, width = 480, limit = 100, live = false, onNewPrice }) {
  const [rows, setRows] = useState([])

  useEffect(() => {
    let alive = true
    api.get(`/api/market/tickers/${symbol}/ohlcv?limit=${limit}`)
      .then(r => { if (alive) setRows(r.data || []) })
      .catch(() => { if (alive) setRows([]) })
    return () => { alive = false }
  }, [symbol, limit])

  useEffect(() => {
    if (!live) return
    const id = setInterval(async () => {
      try {
        const sim = await api.post(`/api/market/tickers/${symbol}/simulate`)
        const bar = sim.data
        setRows(prev => {
          const next = [...prev, bar]
          if (next.length > limit) next.shift()
          return next
        })
        // Notify parent of new price
        if (onNewPrice) onNewPrice(bar)
      } catch {}
    }, 2000)
    return () => clearInterval(id)
  }, [live, symbol, limit, onNewPrice])

  const path = useMemo(() => {
    if (!rows.length) return ''
    const closes = rows.map(r => r.close)
    const min = Math.min(...closes)
    const max = Math.max(...closes)
    const pad = (max - min) * 0.1 || 1
    const yMin = min - pad
    const yMax = max + pad
    const n = rows.length
    const xFor = (i) => (i / (n - 1)) * (width - 40) + 20 // padding
    const yFor = (v) => height - 20 - ((v - yMin) / (yMax - yMin)) * (height - 40)
    let d = `M ${xFor(0)} ${yFor(closes[0])}`
    for (let i = 1; i < n; i++) {
      d += ` L ${xFor(i)} ${yFor(closes[i])}`
    }
    return d
  }, [rows, height, width])

  return (
    <div>
      <div className="chart-header">
        <div className="chart-title">
          <span className="symbol-badge">{symbol}</span>
          <span className="chart-label">Price Chart</span>
        </div>
        <div className="chart-stats">
          {rows.length > 0 && (
            <span className="stat-item">
              ${rows[rows.length - 1]?.close?.toFixed(2) ?? '—'}
            </span>
          )}
          <span className="points-badge">{rows.length}</span>
          {live && <span className="live-indicator">● LIVE</span>}
        </div>
      </div>
      <div className="chart-container">
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet" className="price-chart">
          <defs>
            <linearGradient id="chartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.3"/>
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          <rect x="0" y="0" width={width} height={height} fill="transparent" />
          {/* Grid lines */}
          {[...Array(5)].map((_, i) => (
            <line
              key={i}
              x1="0"
              y1={i * height / 4}
              x2={width}
              y2={i * height / 4}
              stroke="var(--border)"
              strokeOpacity="0.2"
              strokeDasharray="2,4"
            />
          ))}
          {/* Area fill */}
          <path d={path + ` L ${width - 20} ${height - 20} L 20 ${height - 20} Z`} fill="url(#chartGradient)" opacity="0.5" />
          {/* Price line */}
          <path d={path} stroke="var(--accent)" strokeWidth="2.5" fill="none" filter="url(#glow)" />
        </svg>
      </div>
    </div>
  )
}
