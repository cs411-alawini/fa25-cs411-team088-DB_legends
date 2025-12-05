import math
import random
from datetime import datetime, timedelta
from ..db import get_conn_cursor


def generate_random_walk(symbol: str, start_price: float, bars: int = 200, minutes: int = 60):
    now = datetime.utcnow()
    price = start_price
    with get_conn_cursor(True) as (_, cur):
        for i in range(bars):
            t = now - timedelta(minutes=(bars - i) * minutes)
            ret = random.gauss(0, 0.002)
            new_price = max(0.01, price * math.exp(ret))
            low = min(price, new_price) * (1 - 0.002)
            high = max(price, new_price) * (1 + 0.002)
            cur.execute(
                """
                INSERT INTO price_bars (ticker, time, open, high, low, close, volume, source)
                VALUES (%(sym)s, %(t)s, %(o)s, %(h)s, %(l)s, %(c)s, %(v)s, 'SIM')
                ON CONFLICT (ticker, time) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    source = EXCLUDED.source
                """,
                {
                    "sym": symbol,
                    "t": t,
                    "o": price,
                    "h": high,
                    "l": low,
                    "c": new_price,
                    "v": 1000,
                },
            )
            price = new_price
