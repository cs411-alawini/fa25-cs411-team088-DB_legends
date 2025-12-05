import React, { useEffect, useState } from 'react'
import api from '../api'

export default function NewsFeed() {
  const [rows, setRows] = useState([])
  const [sentiment, setSentiment] = useState('')
  const [limit, setLimit] = useState(10)

  const load = async () => {
    const q = new URLSearchParams()
    if (sentiment) q.set('sentiment', sentiment)
    q.set('limit', String(limit))
    const { data } = await api.get(`/api/watchlist/news/feed?${q.toString()}`)
    setRows(data)
  }

  useEffect(() => { load() }, [])

  return (
    <div>
      <h3>My News Feed</h3>
      <div style={{display:'flex', gap:6, marginBottom:8, flexWrap:'wrap', alignItems:'center'}}>
        <select value={sentiment} onChange={e=>setSentiment(e.target.value)} style={{flex:'1 1 100px', minWidth:80}}>
          <option value="">Any</option>
          <option>positive</option>
          <option>neutral</option>
          <option>negative</option>
        </select>
        <input type="number" min={1} value={limit} onChange={e=>setLimit(Number(e.target.value))} style={{width:60}} />
        <button onClick={load} style={{flexShrink:0}}>Refresh</button>
      </div>
      <ul style={{margin:0, paddingLeft:18, fontSize:13}}>
        {rows.map(n => (
          <li key={`${n.id}-${n.ticker}`} style={{marginBottom:6}}>
            <a href={n.url} target="_blank" style={{fontSize:13}}>{n.title}</a>
            {n.sentiment ? <span className="muted" style={{fontSize:11}}> [{n.sentiment}]</span> : ''}
            {n.published_at ? <span className="muted" style={{fontSize:11}}> — {n.published_at}</span> : ''}
          </li>
        ))}
      </ul>
    </div>
  )
}
