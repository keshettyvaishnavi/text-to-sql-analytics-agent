"""Builds a small star schema warehouse in SQLite with synthetic card transactions."""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "warehouse.db"


def build_warehouse(path: Path = DB_PATH, seed: int = 11) -> Path:
    random.seed(seed)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE dim_customer (customer_id INTEGER PRIMARY KEY, segment TEXT, state TEXT);
        CREATE TABLE dim_merchant (merchant_id INTEGER PRIMARY KEY, merchant_name TEXT, category TEXT);
        CREATE TABLE dim_date (date_key TEXT PRIMARY KEY, month TEXT, year INTEGER);
        CREATE TABLE fact_transactions (
            txn_id INTEGER PRIMARY KEY, customer_id INTEGER, merchant_id INTEGER,
            date_key TEXT, amount REAL, channel TEXT, is_fraud INTEGER
        );
        """
    )
    segments, states = ["Retail", "Premier", "Small Business"], ["OH", "MI", "KY", "IL", "FL"]
    con.executemany("INSERT INTO dim_customer VALUES (?,?,?)",
                    [(i, random.choice(segments), random.choice(states)) for i in range(1, 301)])
    merchants = [("FreshMart", "Grocery"), ("QuickFuel", "Gas"), ("ShopOnline", "Ecommerce"),
                 ("CityDine", "Restaurants"), ("TravelNow", "Travel"), ("TechHub", "Electronics")]
    con.executemany("INSERT INTO dim_merchant VALUES (?,?,?)", [(i + 1, n, c) for i, (n, c) in enumerate(merchants)])
    start, days = date(2026, 1, 1), 273
    con.executemany("INSERT INTO dim_date VALUES (?,?,?)",
                    [((start + timedelta(d)).isoformat(), (start + timedelta(d)).strftime("%Y-%m"), 2026) for d in range(days)])
    rows = []
    for t in range(1, 6001):
        m = random.randint(1, 6)
        amt = round(random.lognormvariate(3.6 + (0.9 if m in (5, 6) else 0), 0.6), 2)
        channel = "online" if m == 3 or random.random() < 0.3 else "in_store"
        fraud = 1 if random.random() < (0.04 if channel == "online" else 0.01) else 0
        rows.append((t, random.randint(1, 300), m, (start + timedelta(random.randint(0, days - 1))).isoformat(), amt, channel, fraud))
    con.executemany("INSERT INTO fact_transactions VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print(f"Warehouse created at {build_warehouse()}")
