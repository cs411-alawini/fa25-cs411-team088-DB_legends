import React, { useEffect, useState } from 'react'
import api from '../api'
import OrderForm from '../components/OrderForm'
import Watchlist from '../components/Watchlist'
import NewsFeed from '../components/NewsFeed'
import OhlcvChart from '../components/OhlcvChart'

export default function Dashboard() {
  const [accounts, setAccounts] = useState([])
  const [accountId, setAccountId] = useState(null)
  const [groups, setGroups] = useState([])
  const [selectedGroup, setSelectedGroup] = useState('') // '' = Individual
  const [symbol, setSymbol] = useState('AAPL')
  const [latest, setLatest] = useState(null)
  const [news, setNews] = useState([])
  const [positions, setPositions] = useState([])
  const [pnl, setPnl] = useState(null)
  const [live, setLive] = useState(false)

  // Use the group's dedicated account when a group is selected; otherwise use the user's individual account
  const activeAccountId = (selectedGroup && groups.find(g => String(g.id) === String(selectedGroup))?.account_id) || accountId
  const activeAccountLabel = selectedGroup
    ? `Group: ${groups.find(g => String(g.id) === String(selectedGroup))?.name || 'Group'}`
    : 'Individual'

  useEffect(() => {
    api.get('/api/accounts')
      .then(r => {
        console.log('Accounts loaded:', r.data)
        setAccounts(r.data || [])
        if (!accountId && r.data?.length) setAccountId(r.data[0].id)
      })
      .catch(err => {
        console.error('Failed to load accounts:', err)
        setAccounts([])
      })
    api.get('/api/groups')
      .then(r => setGroups(r.data || []))
      .catch(()=>setGroups([]))
  }, [])

  const fetchLatestPrice = async () => {
    try {
      const res = await api.get(`/api/market/tickers/${symbol}/latest`)
      setLatest(res.data)
      return res.data
    } catch {
      setLatest(null)
      return null
    }
  }

  useEffect(() => {
    fetchLatestPrice()
    api.get(`/api/news?symbol=${symbol}&limit=5`).then(r => setNews(r.data)).catch(()=>setNews([]))
  }, [symbol])

  // Poll latest price continuously to sync with server-simulated prices
  useEffect(() => {
    const interval = setInterval(fetchLatestPrice, 2000)
    return () => clearInterval(interval)
  }, [symbol])

  // Poll account data (positions & PnL) continuously to keep in sync for the active account
  useEffect(() => {
    if (!activeAccountId) return
    const interval = setInterval(() => {
      refreshAccount(activeAccountId)
    }, 2000)
    return () => clearInterval(interval)
  }, [activeAccountId])

  const refreshAccount = async (aid) => {
    try {
      const [pos, pnlRes] = await Promise.all([
        api.get(`/api/metrics/positions/${aid}`),
        api.get(`/api/metrics/pnl/${aid}`),
      ])
      setPositions(pos.data)
      setPnl(pnlRes.data)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (activeAccountId) {
      refreshAccount(activeAccountId)
    }
  }, [activeAccountId])

  return (
    <div>
      <h2>Dashboard</h2>
      <div style={{display:'flex', gap:16, marginBottom:24, alignItems:'flex-start'}}>
        {/* Left Column - Main Trading Panel */}
        <div className="card" style={{flex:'1 1 auto', minWidth:500, maxWidth:580}}>
          <div>
            <label>Symbol</label>
            <input value={symbol} onChange={e=>setSymbol(e.target.value.toUpperCase())} />
          </div>
          <div style={{display:'flex', gap:8, alignItems:'center', marginTop:8}}>
            <label>Trade As</label>
            <select value={selectedGroup} onChange={e=>setSelectedGroup(e.target.value)}>
              <option value="">Individual</option>
              {groups.map(g => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>
          
          {latest ? (
            <div style={{marginTop:8}}>
              <div><b>{symbol}</b> latest: ${latest.close?.toFixed?.(2) ?? latest.close}</div>
              <div>time: {latest.time}</div>
            </div>
          ) : <div>No price</div>}
          <div style={{marginTop:12}}>
            <OhlcvChart 
              symbol={symbol} 
              width={480} 
              height={220} 
              onNewPrice={(price) => setLatest(price)}
            />
          </div>
          {accounts.length > 0 ? (
            <div style={{marginTop:16}}>
              <OrderForm
                accountId={activeAccountId || accounts[0]?.id}
                defaultSymbol={symbol}
                groupId={selectedGroup || null}
                onPlaced={() => refreshAccount(activeAccountId || accounts[0]?.id)}
              />
            </div>
          ) : (
            <div style={{marginTop:16, padding:12, border:'1px solid #374151', borderRadius:8}}>
              <p>No trading account found. Log out and back in to auto-create one.</p>
            </div>
          )}
        </div>
        
        {/* Right Column - Critical Info */}
        <div style={{flex:'0 0 420px', minWidth:360, display:'flex', flexDirection:'column', gap:16}}>
          {/* Positions & Account Summary */}
          {accountId && (
          <div className="card">
            <h3 style={{marginBottom:12, flexShrink:0}}>Positions</h3>
            {positions.length === 0 ? (
              <div>No positions</div>
            ) : (
              <div style={{maxHeight:260, overflowY:'auto'}}>
                {/* Group positions by individual vs group */}
                {(() => {
                  const individual = positions.filter(p => !p.group_id)
                  const grouped = positions.filter(p => p.group_id)
                  const groupMap = {}
                  grouped.forEach(p => {
                    if (!groupMap[p.group_id]) groupMap[p.group_id] = []
                    groupMap[p.group_id].push(p)
                  })
                  
                  return (
                    <>
                      {individual.length > 0 && (
                        <div style={{marginBottom:16}}>
                          <h5 style={{fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase'}}>Individual</h5>
                          <table className="table" style={{fontSize:13}}>
                            <thead>
                              <tr>
                                <th>Ticker</th>
                                <th className="num">Qty</th>
                                <th className="num">Last</th>
                                <th className="num">Value</th>
                              </tr>
                            </thead>
                            <tbody>
                              {individual.map(p => (
                                <tr key={`ind-${p.ticker}`}>
                                  <td style={{fontWeight:600, fontFamily:'Inter, sans-serif'}}>{p.ticker}</td>
                                  <td className="num" style={{fontFamily:'Roboto Mono, monospace', fontSize:13}}>{p.qty?.toFixed?.(2) ?? p.qty}</td>
                                  <td className="num" style={{fontFamily:'Roboto Mono, monospace', fontSize:13}}>${p.last?.toFixed?.(2) ?? p.last}</td>
                                  <td className="num" style={{fontWeight:600, fontFamily:'Inter, sans-serif'}}>${p.market_value?.toFixed?.(2) ?? p.market_value}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                      
                      {Object.entries(groupMap).map(([groupId, groupPositions]) => (
                        <div key={`group-${groupId}`} style={{marginBottom:16}}>
                          <h5 style={{fontSize:12, color:'var(--muted)', marginBottom:8, textTransform:'uppercase'}}>
                            Group: {groupPositions[0]?.group_name || `Group ${groupId}`}
                          </h5>
                          <table className="table" style={{fontSize:13}}>
                            <thead>
                              <tr>
                                <th>Ticker</th>
                                <th className="num">Qty</th>
                                <th className="num">Last</th>
                                <th className="num">Value</th>
                              </tr>
                            </thead>
                            <tbody>
                              {groupPositions.map(p => (
                                <tr key={`grp-${groupId}-${p.ticker}`}>
                                  <td style={{fontWeight:600, fontFamily:'Inter, sans-serif'}}>{p.ticker}</td>
                                  <td className="num" style={{fontFamily:'Roboto Mono, monospace', fontSize:13}}>{p.qty?.toFixed?.(2) ?? p.qty}</td>
                                  <td className="num" style={{fontFamily:'Roboto Mono, monospace', fontSize:13}}>${p.last?.toFixed?.(2) ?? p.last}</td>
                                  <td className="num" style={{fontWeight:600, fontFamily:'Inter, sans-serif'}}>${p.market_value?.toFixed?.(2) ?? p.market_value}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ))}
                    </>
                  )
                })()}
              </div>
            )}
            {pnl && (
              <div style={{marginTop:16, padding:16, background:'rgba(30,41,59,0.3)', borderRadius:12}}>
                <h4 style={{marginBottom:12, color:'var(--text)', fontSize:16}}>Account Summary</h4>
                <div style={{display:'grid', gap:8, fontSize:14}}>
                  <div style={{display:'flex', justifyContent:'space-between'}}>
                    <span className="muted">Starting Cash:</span>
                    <span style={{fontWeight:600, fontSize:14}}>${pnl.starting_cash?.toFixed?.(2) ?? pnl.starting_cash}</span>
                  </div>
                  <div style={{display:'flex', justifyContent:'space-between'}}>
                    <span className="muted">Cash Flow:</span>
                    <span style={{fontWeight:600, fontSize:14, color: pnl.net_cash_flow >= 0 ? 'var(--success)' : 'var(--danger)'}}>${pnl.net_cash_flow?.toFixed?.(2) ?? pnl.net_cash_flow}</span>
                  </div>
                  <div style={{display:'flex', justifyContent:'space-between'}}>
                    <span className="muted">Current Cash:</span>
                    <span style={{fontWeight:600, fontSize:14}}>${pnl.current_cash?.toFixed?.(2) ?? pnl.current_cash}</span>
                  </div>
                  <div style={{height:1, background:'var(--border)', margin:'4px 0'}}></div>
                  <div style={{display:'flex', justifyContent:'space-between'}}>
                    <span className="muted">Position Value:</span>
                    <span style={{fontWeight:600, fontSize:14}}>${pnl.mtm_positions?.toFixed?.(2) ?? pnl.mtm_positions}</span>
                  </div>
                  <div style={{display:'flex', justifyContent:'space-between'}}>
                    <span className="muted">Unrealized P&L:</span>
                    <span style={{fontWeight:600, fontSize:14, color: pnl.unrealized_pnl >= 0 ? 'var(--success)' : 'var(--danger)'}}>${pnl.unrealized_pnl?.toFixed?.(2) ?? pnl.unrealized_pnl}</span>
                  </div>
                  <div style={{height:1, background:'var(--border)', margin:'4px 0'}}></div>
                  <div style={{display:'flex', justifyContent:'space-between', fontWeight:600, fontSize:16}}>
                    <span>Total Value:</span>
                    <span style={{fontWeight:700, fontSize:15}}>${pnl.account_value?.toFixed?.(2) ?? pnl.account_value}</span>
                  </div>
                  <div style={{display:'flex', justifyContent:'space-between', fontWeight:600, fontSize:16}}>
                    <span>Total P&L:</span>
                    <span style={{fontWeight:700, fontSize:15, color: pnl.pnl >= 0 ? 'var(--success)' : 'var(--danger)'}}>${pnl.pnl?.toFixed?.(2) ?? pnl.pnl}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
          )}
          
          {/* Watchlist */}
          <div className="card" style={{maxHeight:200, overflowY:'auto'}}>
            <Watchlist />
          </div>
        </div>
        
        {/* Third Column - News */}
        <div style={{flex:'0 0 400px', minWidth:340, display:'flex', flexDirection:'column', gap:16}}>
          <div className="card" style={{maxHeight:300}}>
            <h3 style={{marginBottom:12}}>Market News</h3>
            <div style={{overflowY:'auto', maxHeight:250, fontSize:14}}>
              {news.length > 0 ? (
                <ul style={{margin:0, paddingLeft:18}}>
                  {news.map(n => (
                    <li key={n.id} style={{marginBottom:8}}>
                      <a href={n.url} target="_blank" style={{fontSize:13}}>{n.title}</a>
                      <span style={{marginLeft:8, fontSize:12}} className="muted">[{n.sentiment || 'n/a'}]</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="muted">No news available</div>
              )}
            </div>
          </div>
          
          <div className="card" style={{flex:1}}>
            <NewsFeed />
          </div>
        </div>
      </div>
    </div>
  )
}

