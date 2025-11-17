import { useEffect, useState } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:3001';

function App() {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  const [ticker, setTicker] = useState('');
  const [side, setSide] = useState('BUY');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');

  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  // load existing transactions on mount
  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        const res = await axios.get(
          `${API_BASE}/api/transactions/account/1`
        );
        setTransactions(res.data);
      } catch (err) {
        console.error(err);
        setError('Failed to load transactions');
      } finally {
        setLoading(false);
      }
    };

    fetchTransactions();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setCreating(true);

    try {
      await axios.post(`${API_BASE}/api/transactions`, {
        ticker,
        side,
        quantity: Number(quantity),
        price: Number(price),
      });

      // reload list
      const res = await axios.get(
        `${API_BASE}/api/transactions/account/1`
      );
      setTransactions(res.data);

      // clear form
      setTicker('');
      setQuantity('');
      setPrice('');
      setSide('BUY');
    } catch (err) {
      console.error(err);
      setError('Failed to create transaction');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem', maxWidth: 900, margin: '0 auto' }}>
      <h1>Paper Trading – Transactions</h1>

      <section style={{ marginBottom: '2rem' }}>
        <h2>Place Trade</h2>
        <form
          onSubmit={handleSubmit}
          style={{ display: 'grid', gap: '0.75rem', maxWidth: 400 }}
        >
          <label>
            Ticker:{' '}
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="AAPL"
              required
            />
          </label>

          <label>
            Side:{' '}
            <select value={side} onChange={(e) => setSide(e.target.value)}>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </label>

          <label>
            Quantity:{' '}
            <input
              type="number"
              min="1"
              step="1"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
          </label>

          <label>
            Price:{' '}
            <input
              type="number"
              min="0"
              step="0.01"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
            />
          </label>

          <button type="submit" disabled={creating}>
            {creating ? 'Placing…' : 'Place Order'}
          </button>

          {error && <p style={{ color: 'red' }}>{error}</p>}
        </form>
      </section>

      <section>
        <h2>Recent Transactions (Account 1)</h2>
        {loading ? (
          <p>Loading…</p>
        ) : transactions.length === 0 ? (
          <p>No transactions yet. Place a trade above.</p>
        ) : (
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              marginTop: '1rem',
            }}
          >
            <thead>
              <tr>
                <th style={{ borderBottom: '1px solid #ccc', textAlign: 'left' }}>Time</th>
                <th style={{ borderBottom: '1px solid #ccc', textAlign: 'left' }}>Ticker</th>
                <th style={{ borderBottom: '1px solid #ccc', textAlign: 'left' }}>Side</th>
                <th style={{ borderBottom: '1px solid #ccc', textAlign: 'right' }}>Qty</th>
                <th style={{ borderBottom: '1px solid #ccc', textAlign: 'right' }}>Price</th>
                <th style={{ borderBottom: '1px solid #ccc', textAlign: 'left' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.transactionID}>
                  <td style={{ padding: '0.25rem 0.5rem' }}>
                    {new Date(t.time).toLocaleString()}
                  </td>
                  <td style={{ padding: '0.25rem 0.5rem' }}>{t.ticker}</td>
                  <td style={{ padding: '0.25rem 0.5rem' }}>{t.side}</td>
                  <td style={{ padding: '0.25rem 0.5rem', textAlign: 'right' }}>
                    {Number(t.quantity)}
                  </td>
                  <td style={{ padding: '0.25rem 0.5rem', textAlign: 'right' }}>
                    {Number(t.price).toFixed(2)}
                  </td>
                  <td style={{ padding: '0.25rem 0.5rem' }}>{t.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default App;
