# fa25-cs411-team088-DB_legends

1. Clone the repository

git clone https://github.com/
<ORG>/<REPO>.git
cd <REPO>

🗄️ Backend Setup (Node + Express + PostgreSQL)
2. Install backend dependencies

cd backend
npm install

3. Set up PostgreSQL database

Open psql:

psql -U postgres

Run the following SQL commands:

CREATE DATABASE paper_trading;
CREATE USER paper_user WITH PASSWORD 'paper_pass';
GRANT ALL PRIVILEGES ON DATABASE paper_trading TO paper_user;

\c paper_trading

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO paper_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO paper_user;

CREATE TABLE IF NOT EXISTS "Transactions" (
"transactionID" SERIAL PRIMARY KEY,
"accountID" INT NOT NULL,
"ticker" VARCHAR(10) NOT NULL,
"time" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
"side" VARCHAR(10) NOT NULL,
"quantity" NUMERIC(12,4) NOT NULL,
"price" NUMERIC(12,2) NOT NULL,
"kind" VARCHAR(20) NOT NULL DEFAULT 'ORDER',
"status" VARCHAR(20) NOT NULL DEFAULT 'PENDING',
"requestedBy" INT NOT NULL,
"approvedBy" INT NULL
);

-- Optional seed row
INSERT INTO "Transactions" ("accountID", "ticker", "side", "quantity", "price", "requestedBy")
VALUES (1, 'AAPL', 'BUY', 10, 150.00, 1);

Exit psql:

\q

4. Start backend server

cd backend
npm start

Backend runs at:
http://localhost:3001

🎨 Frontend Setup (React + Vite)
5. Install frontend dependencies

cd ../frontend
npm install

6. Start frontend dev server

npm run dev

Frontend runs at:
http://localhost:5173
