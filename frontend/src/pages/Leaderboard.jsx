import React, { useEffect, useState } from 'react'
import api from '../api'

export default function Leaderboard() {
  const [rows, setRows] = useState([])
  const [limit, setLimit] = useState(10)

  const load = async () => {
    const { data } = await api.get(`/api/metrics/leaderboard?limit=${limit}`)
    setRows(data)
  }

  useEffect(() => { load() }, [])

  const numClass = (v) => `num ${v > 0 ? 'num-pos' : v < 0 ? 'num-neg' : ''}`
  const fmt = (v, d=2) => (v ?? v === 0) ? Number(v).toFixed(d) : '—'

  return (
    <div className="card">
      <h2>Leaderboard</h2>
      <div className="toolbar">
        <input type="number" value={limit} onChange={e=>setLimit(Number(e.target.value))} />
        <button className="btn-primary" onClick={load}>Refresh</button>
        <span className="muted" style={{marginLeft:'auto'}}>{rows.length} rows</span>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Account</th>
            <th className="num">Starting</th>
            <th className="num">Current Cash</th>
            <th className="num">Total Value</th>
            <th className="num">PnL</th>
            <th className="num">Return</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.account_id}>
              <td>{r.name}</td>
              <td className="num">${fmt(r.starting_cash)}</td>
              <td className="num">${fmt(r.current_cash)}</td>
              <td className="num">${fmt(r.account_value)}</td>
              <td className={numClass(r.pnl)}>${fmt(r.pnl)}</td>
              <td className={numClass(r.return)}>{r.return != null ? (r.return*100).toFixed(2)+ '%' : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
