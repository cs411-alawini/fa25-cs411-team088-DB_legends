import React, { useEffect, useState } from 'react'
import api from '../api'

export default function Watchlist() {
  const [items, setItems] = useState([])
  const [ticker, setTicker] = useState('AAPL')
  const [err, setErr] = useState('')

  const load = async () => {
    try {
      const { data } = await api.get('/api/watchlist')
      setItems(data)
    } catch (e) { setItems([]) }
  }

  useEffect(() => { load() }, [])

  const add = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await api.post('/api/watchlist', { ticker })
      setTicker('')
      load()
    } catch (e) { setErr(e.response?.data?.error || e.message) }
  }

  const remove = async (sym) => {
    await api.delete(`/api/watchlist/${sym}`)
    load()
  }

  return (
    <div>
      <h3>Watchlist</h3>
      <form onSubmit={add} style={{display:'flex', gap:8}}>
        <input placeholder="Ticker" value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())} />
        <button type="submit">Add</button>
      </form>
      {err && <div style={{color:'red'}}>{err}</div>}
      <ul>
        {items.map(i => (
          <li key={i.ticker}>
            {i.ticker} <small>({i.added_at})</small>
            <button style={{marginLeft:8}} onClick={()=>remove(i.ticker)}>x</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
