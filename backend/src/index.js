const express = require('express');
const cors = require('cors');
const transactionsRouter = require('./routes/transactions');

const app = express();

app.use(cors());
app.use(express.json());

app.get('/', (req, res) => {
  res.send('Paper Trading backend is running');
});

app.use('/api/transactions', transactionsRouter);

const PORT = 3001;
app.listen(PORT, () => {
  console.log(`Backend listening on http://localhost:${PORT}`);
});
