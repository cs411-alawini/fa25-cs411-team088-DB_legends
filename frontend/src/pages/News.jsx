import React, { useEffect, useState } from 'react'
import api from '../api'

export default function News() {
  const [symbol, setSymbol] = useState('AAPL')
  const [sentiment, setSentiment] = useState('')
  const [rows, setRows] = useState([])

  const load = async () => {
    const q = new URLSearchParams()
    if (symbol) q.set('symbol', symbol)
    if (sentiment) q.set('sentiment', sentiment)
    const { data } = await api.get(`/api/news?${q.toString()}`)
    setRows(data)
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h2>News</h2>
      <div style={{display:'flex', gap:8}}>
        <input placeholder="Symbol" value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} />
        <select value={sentiment} onChange={e=>setSentiment(e.target.value)}>
          <option value="">Any sentiment</option>
          <option>positive</option>
          <option>neutral</option>
          <option>negative</option>
        </select>
        <button onClick={load}>Search</button>
      </div>
      <ul>
        {rows.map(n => (
          <li key={n.id}><a href={n.url} target="_blank">{n.title}</a> [{n.sentiment || 'n/a'}]</li>
        ))}
      </ul>
    </div>
  )
}
