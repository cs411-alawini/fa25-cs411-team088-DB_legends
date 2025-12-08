import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'

export default function Groups() {
  const nav = useNavigate()
  const [groups, setGroups] = useState([])
  const [name, setName] = useState('')
  const [selected, setSelected] = useState(null)
  const [orders, setOrders] = useState([])
  const [err, setErr] = useState('')
  const [discover, setDiscover] = useState([])
  const [q, setQ] = useState('')
  const [includeMine, setIncludeMine] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [renameName, setRenameName] = useState('')

  const handleAuthError = (e) => {
    const status = e?.response?.status
    if (status === 401 || status === 422) {
      setErr('Please login to manage groups.')
      setTimeout(() => nav('/login'), 500)
      return true
    }
    return false
  }

  const startRename = (g) => {
    setErr('')
    setEditingId(g.id)
    setRenameName(g.name || '')
  }

  const cancelRename = () => {
    setEditingId(null)
    setRenameName('')
  }

  const saveRename = async (g) => {
    setErr('')
    const n = renameName.trim()
    if (!n) { setErr('Name is required'); return }
    try {
      await api.put(`/api/groups/${g.id}`, { name: n })
      await load()
      if (selected?.id === g.id) setSelected({ ...g, name: n })
      cancelRename()
      await loadDiscover()
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }

  const processOrder = async (orderId) => {
    setErr('')
    try {
      await api.post(`/api/orders/${orderId}/process`)
      if (selected) await loadOrders(selected)
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }

  const load = async () => {
    setErr('')
    try {
      const { data } = await api.get('/api/groups')
      setGroups(data)
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }

  useEffect(() => { load() }, [])

  const loadDiscover = async () => {
    setErr('')
    try {
      const params = new URLSearchParams()
      if (q.trim()) params.set('q', q.trim())
      if (includeMine) params.set('include_mine', '1')
      const { data } = await api.get(`/api/groups/discover?${params.toString()}`)
      setDiscover(data)
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }
  useEffect(() => { loadDiscover() }, [])
  useEffect(() => { loadDiscover() }, [includeMine])

  const create = async (e) => {
    e.preventDefault()
    setErr('')
    if (!name.trim()) { setErr('Group name is required'); return }
    try {
      await api.post('/api/groups', { name })
      setName('')
      await load()
      await loadDiscover()
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }

  const join = async (id) => {
    setErr('')
    try {
      await api.post(`/api/groups/${id}/join`)
      await load()
      await loadDiscover()
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }

  const leave = async (id) => {
    setErr('')
    try {
      await api.post(`/api/groups/${id}/leave`)
      await load()
      await loadDiscover()
      if (selected && selected.id === id) {
        setSelected(null)
        setOrders([])
      }
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }

  const loadOrders = async (g) => {
    setErr('')
    setSelected(g)
    try {
      const { data } = await api.get(`/api/groups/${g.id}/orders?status=open`)
      setOrders(data)
    } catch (e) {
      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
    }
  }

  return (
    <div className="dashboard">
      <div className="card">
        <h2>Groups</h2>
        <form onSubmit={create} style={{display:'flex', gap:8, margin:'12px 0'}}>
          <input value={name} onChange={e=>setName(e.target.value)} placeholder="New group name" />
          <button className="btn-primary" type="submit">Create</button>
        </form>
        {err && <div style={{color:'#fca5a5', marginBottom:8}}>{err}</div>}
        <h3>My Groups</h3>
        <ul>
          {groups.map(g => (
            <li key={g.id}>
              <button onClick={()=>loadOrders(g)} style={{marginRight:8}}>{g.name}</button>
              <small>role: {g.role}</small>
              {(g.role === 'owner' || g.role === 'manager') && (
                editingId === g.id ? (
                  <span style={{marginLeft:8, display:'inline-flex', gap:6, alignItems:'center'}}>
                    <input value={renameName} onChange={e=>setRenameName(e.target.value)} placeholder="New name" />
                    <button onClick={()=>saveRename(g)}>Save</button>
                    <button onClick={cancelRename}>Cancel</button>
                  </span>
                ) : (
                  <button onClick={()=>startRename(g)} style={{marginLeft:8}}>Rename</button>
                )
              )}
              {g.role === 'owner' ? (
                <button
                  style={{marginLeft:8}}
                  onClick={async ()=>{
                    if (!confirm('Delete this group?')) return
                    setErr('')
                    try {
                      await api.delete(`/api/groups/${g.id}`)
                      if (selected?.id === g.id) { setSelected(null); setOrders([]) }
                      await load()
                      await loadDiscover()
                    } catch (e) {
                      if (!handleAuthError(e)) setErr(e.response?.data?.error || e.message)
                    }
                  }}
                >Delete</button>
              ) : (
                <button onClick={()=>leave(g.id)} style={{marginLeft:8}}>Leave</button>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div className="card">
        <h3>Group Orders {selected ? `for ${selected.name}` : ''}</h3>
        {selected && orders.length === 0 && <div>No open orders.</div>}
        {orders.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th>Id</th>
                <th>Account</th>
                <th>Ticker</th>
                <th>Side</th>
                <th>Qty</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map(o => (
                <tr key={o.id}>
                  <td>{o.id}</td>
                  <td>{o.account_id}</td>
                  <td>{o.ticker}</td>
                  <td>{o.side}</td>
                  <td>{o.qty}</td>
                  <td>{o.status}</td>
                  <td>
                    <button onClick={()=>processOrder(o.id)}>Process</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <div className="card">
        <h3>Discover</h3>
        <div style={{display:'flex', gap:8, margin:'12px 0', alignItems:'center'}}>
          <input placeholder="Search groups" value={q} onChange={e=>setQ(e.target.value)} />
          <button onClick={loadDiscover}>Search</button>
          <label style={{marginLeft:12, display:'flex', alignItems:'center', gap:6}}>
            <input type="checkbox" checked={includeMine} onChange={e=>setIncludeMine(e.target.checked)} />
            Include my groups
          </label>
        </div>
        {discover.length === 0 ? (
          <div>No groups to join.</div>
        ) : (
          <ul>
            {discover.map(g => (
              <li key={g.id}>
                <span style={{marginRight:8}}>{g.name}</span>
                {g.my_role ? (
                  <small>role: {g.my_role}</small>
                ) : (
                  <button onClick={()=>join(g.id)}>Join</button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
