import React, { useEffect, useState } from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Leaderboard from './pages/Leaderboard'
import Orders from './pages/Orders'
import News from './pages/News'
import Groups from './pages/Groups'

function Nav() {
  const navigate = useNavigate()
  const [authed, setAuthed] = useState(!!localStorage.getItem('token'))
  useEffect(() => {
    const onStorage = () => setAuthed(!!localStorage.getItem('token'))
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])
  const logout = () => { localStorage.removeItem('token'); setAuthed(false); navigate('/login') }
  return (
    <nav style={{display:'flex', gap:12, padding:12}}>
      <Link to="/">Dashboard</Link>
      <Link to="/orders">Orders</Link>
      <Link to="/news">News</Link>
      <Link to="/leaderboard">Leaderboard</Link>
      <Link to="/groups">Groups</Link>
      <span style={{marginLeft:'auto'}}>
        {authed ? <button onClick={logout}>Logout</button> : <Link to="/login">Login</Link>}
      </span>
    </nav>
  )
}

export default function App() {
  return (
    <div>
      <Nav />
      <div className="content">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/news" element={<News />} />
          <Route path="/" element={<Dashboard />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/groups" element={<Groups />} />
        </Routes>
      </div>
    </div>
  )
}
