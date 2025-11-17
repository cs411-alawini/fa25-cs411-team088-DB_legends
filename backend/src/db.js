const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5432,
  user: 'paper_user',      
  password: 'paper_pass',
  database: 'paper_trading'
});

module.exports = pool;
