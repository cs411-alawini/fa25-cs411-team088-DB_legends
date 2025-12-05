import React, { useState, useEffect } from 'react'
import api from '../api'

export default function OrderForm({ accountId, defaultSymbol='AAPL', groupId=null, live=false, latestPrice=null, onPlaced }) {
  const [symbol, setSymbol] = useState(defaultSymbol)
  const [side, setSide] = useState('BUY')
  const [qty, setQty] = useState(10)
  const [kind, setKind] = useState('MARKET')
  const [price, setPrice] = useState('')
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)
  const [last, setLast] = useState(null)

  const loadLast = async (sym) => {
    try {
      const { data } = await api.get(`/api/market/tickers/${sym}/latest`)
      setLast(Number(data.close))
    } catch { setLast(null) }
  }

  const onSymbol = (v) => {
    const s = (v || '').toUpperCase()
    setSymbol(s)
    if (s) loadLast(s)
  }

  useEffect(() => {
    if (defaultSymbol) {
      const s = (defaultSymbol || '').toUpperCase()
      setSymbol(s)
      loadLast(s)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultSymbol])

  // Update last price from parent when live mode is on
  useEffect(() => {
    if (live && latestPrice != null) {
      setLast(latestPrice)
    }
  }, [live, latestPrice])

  // Poll latest price when live mode is active
  useEffect(() => {
    if (!live || !symbol) return
    const interval = setInterval(() => loadLast(symbol), 2000)
    return () => clearInterval(interval)
  }, [live, symbol])

  const notional = (() => {
    const q = Number(qty) || 0
    const px = kind === 'MARKET' ? (last ?? 0) : (Number(price) || (last ?? 0))
    return q * px
  })()

  const submit = async (e) => {
    e.preventDefault()
    setMsg('')
    setLoading(true)
    // Refresh price right before submit if live
    if (live) await loadLast(symbol)
    try {
      const payload = { symbol, side, qty: Number(qty), kind }
      if (kind !== 'MARKET' && price) payload.price = Number(price)
      if (groupId && groupId !== '') payload.group_id = Number(groupId)
      const { data } = await api.post(`/api/accounts/${accountId}/orders`, payload)
      const fillPrice = data.price
      setMsg(`Order ${data.id} created (${data.status}) at $${fillPrice}`)
      onPlaced && onPlaced(data)
    } catch (e) {
      setMsg(e.response?.data?.error || e.message)
    } finally {
      setLoading(false)
    }
  }

  const priceNeeded = kind !== 'MARKET'
  const canSubmit = !!accountId && symbol && Number(qty) > 0 && (!priceNeeded || Number(price) > 0) && !loading
  const msgColor = /error|invalid|forbidden|cannot/i.test(msg) ? '#fca5a5' : '#86efac'

  return (
    <form onSubmit={submit} style={{display:'grid', gap:8, width:'100%'}}>
      <h3>Quick Order</h3>
      <div style={{display:'flex', gap:8, flexWrap:'wrap'}}>
        <input value={symbol} onChange={e=>onSymbol(e.target.value)} placeholder="Symbol" style={{flex:'1 1 100px', minWidth:80}} />
        <select value={side} onChange={e=>setSide(e.target.value)} style={{flex:'0 0 80px'}}>
          <option>BUY</option>
          <option>SELL</option>
        </select>
        <input type="number" value={qty} onChange={e=>setQty(e.target.value)} min={0} step={1} placeholder="Qty" style={{flex:'1 1 80px', minWidth:60}} />
      </div>
      <div style={{display:'flex', gap:8, alignItems:'center', flexWrap:'wrap'}}>
        <select value={kind} onChange={e=>setKind(e.target.value)} style={{flex:'0 0 90px'}}>
          <option>MARKET</option>
          <option>LIMIT</option>
          <option>STOP</option>
        </select>
        {priceNeeded && (
          <input type="number" placeholder="Price" value={price} onChange={e=>setPrice(e.target.value)} min={0} step={0.01} style={{flex:'1 1 100px'}} />
        )}
        <span className="muted" style={{marginLeft:'auto', flexShrink:0}}>
          Last: ${last?.toFixed?.(2) ?? last ?? '—'}
          {live && ' 🔴'}
        </span>
      </div>
      <div className="muted">Notional: ${Number.isFinite(notional) ? notional.toFixed(2) : '—'}</div>
      <button type="submit" className="btn-primary" disabled={!canSubmit}>{loading ? 'Placing...' : 'Place Order'}</button>
      {msg && <div style={{color: msgColor}}>{msg}</div>}
    </form>
  )
}
