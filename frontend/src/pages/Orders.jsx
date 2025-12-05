import React, { useEffect, useState } from 'react'
import api from '../api'

export default function Orders() {
  const [accounts, setAccounts] = useState([])
  const [orders, setOrders] = useState([])
  const [openOnly, setOpenOnly] = useState(true)

  useEffect(() => {
    api.get('/api/accounts').then(r => setAccounts(r.data))
  }, [])

  useEffect(() => {
    if (accounts[0]) {
      const qs = openOnly ? '?status=open' : ''
      api.get(`/api/accounts/${accounts[0].id}/orders${qs}`).then(r => setOrders(r.data))
    }
  }, [accounts, openOnly])

  const cancel = async (id) => {
    await api.post(`/api/orders/${id}/cancel`)
    setOrders(orders.filter(o => o.id !== id))
  }

  const approve = async (id) => {
    await api.post(`/api/orders/${id}/approve`)
    setOrders(orders.filter(o => o.id !== id))
  }

  const downloadCsv = async () => {
    if (!accounts[0]) return
    const aid = accounts[0].id
    const res = await api.get(`/api/exports/trades?account_id=${aid}` , { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `trades_account_${aid}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  }

  const badgeClass = (status) => `status-badge status-${String(status || '').toLowerCase()}`

  return (
    <div className="card">
      <h2>Orders</h2>
      {accounts[0] && (
        <div className="toolbar">
          <button onClick={downloadCsv}>Download Trades CSV</button>
          <label className="muted" style={{display:'flex', alignItems:'center', gap:6}}>
            <input type="checkbox" checked={openOnly} onChange={e=>setOpenOnly(e.target.checked)} />
            Open only
          </label>
          <span className="muted" style={{marginLeft:'auto'}}>{orders.length} rows</span>
        </div>
      )}
      <table className="table">
        <thead>
          <tr>
            <th>Id</th>
            <th>Symbol</th>
            <th>Side</th>
            <th className="num">Qty</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {orders.map(o => (
            <tr key={o.id}>
              <td>{o.id}</td>
              <td>{o.ticker}</td>
              <td>{o.side}</td>
              <td className="num">{o.qty}</td>
              <td><span className={badgeClass(o.status)}>{o.status}</span></td>
              <td>
                {(['NEW','PENDING_APPROVAL','APPROVED'].includes(o.status)) && (
                  <button onClick={()=>cancel(o.id)}>Cancel</button>
                )}
                {o.status === 'PENDING_APPROVAL' && (
                  <button onClick={()=>approve(o.id)} style={{marginLeft:8}} className="btn-primary">Approve</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
