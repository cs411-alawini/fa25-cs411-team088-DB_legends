import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'

export default function Login() {
  const nav = useNavigate()
  const [isRegister, setIsRegister] = useState(false)
  const [email, setEmail] = useState('alice@example.com')
  const [password, setPassword] = useState('password')
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const url = isRegister ? '/api/auth/register' : '/api/auth/login'
      const { data } = await api.post(url, { email, password })
      localStorage.setItem('token', data.token)
      nav('/')
    } catch (e) {
      setError(e.response?.data?.error || e.message)
    }
  }

  return (
    <div style={{maxWidth:360}}>
      <h2>{isRegister ? 'Register' : 'Login'}</h2>
      <form onSubmit={submit}>
        <div>
          <label>Email</label>
          <input value={email} onChange={e=>setEmail(e.target.value)} />
        </div>
        <div>
          <label>Password</label>
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)} />
        </div>
        {error && <div style={{color:'red'}}>{error}</div>}
        <button type="submit">Submit</button>
      </form>
      <button onClick={()=>setIsRegister(!isRegister)} style={{marginTop:12}}>
        {isRegister ? 'Have an account? Login' : 'Create account'}
      </button>
    </div>
  )
}
