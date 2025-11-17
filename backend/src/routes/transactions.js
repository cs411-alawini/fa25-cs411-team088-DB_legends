const express = require('express');
const router = express.Router();
const db = require('../db');

router.get('/account/:accountID', async (req, res) => {
  const { accountID } = req.params;

  try {
    const result = await db.query(
      `
      SELECT "transactionID",
             "accountID",
             "ticker",
             "time",
             "side",
             "quantity",
             "price",
             "kind",
             "status",
             "requestedBy",
             "approvedBy"
      FROM "Transactions"
      WHERE "accountID" = $1
      ORDER BY "time" DESC, "transactionID" DESC
      LIMIT 50;
      `,
      [accountID]
    );

    res.json(result.rows);
  } catch (err) {
    console.error('Error fetching transactions:', err);
    res.status(500).json({ error: 'Failed to fetch transactions' });
  }
});

// POST /api/transactions
router.post('/', async (req, res) => {
  const { ticker, side, quantity, price } = req.body;

  const accountID = 1;
  const requestedBy = 1;

  if (!ticker || !side || !quantity || !price) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    const result = await db.query(
      `
      INSERT INTO "Transactions" (
        "accountID",
        "ticker",
        "side",
        "quantity",
        "price",
        "kind",
        "status",
        "requestedBy",
        "approvedBy"
      )
      VALUES ($1, $2, $3, $4, $5, 'ORDER', 'PENDING', $6, NULL)
      RETURNING "transactionID", "time";
      `,
      [accountID, ticker, side, quantity, price, requestedBy]
    );

    const row = result.rows[0];

    res.status(201).json({
      transactionID: row.transactionID,
      accountID,
      ticker,
      side,
      quantity,
      price,
      time: row.time,
      kind: 'ORDER',
      status: 'PENDING',
      requestedBy,
      approvedBy: null
    });
  } catch (err) {
    console.error('Error creating transaction:', err);
    res.status(500).json({ error: 'Failed to create transaction' });
  }
});

module.exports = router;
