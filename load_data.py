"""
Load the Superstore CSV into a SQLite database (data/superstore.db).

Usage:
    1. Download the dataset from Kaggle:
       https://www.kaggle.com/datasets/vivek468/superstore-dataset-final
    2. Put "Sample - Superstore.csv" in the data/ folder.
    3. Run:  python load_data.py

Two traps in this file, both handled below:
  - Encoding: the file is NOT UTF-8 (names such as "Jorgen" contain special characters),
    so it must be read as latin-1.
  - Dates: they are in US format (month/day/year, e.g. 11/8/2016 = 8 November 2016).
    As text they would sort wrongly, so they are converted to ISO format (2016-11-08).
"""
import sqlite3
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "Sample - Superstore.csv"
DB_PATH = DATA_DIR / "superstore.db"


def main():
    df = pd.read_csv(CSV_PATH, encoding="latin-1")

    # Clean column names: "Sub-Category" -> "sub_category"
    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace(" ", "_").str.replace("-", "_"))

    # US dates -> ISO dates (text that sorts correctly in SQL)
    for col in ("order_date", "ship_date"):
        df[col] = pd.to_datetime(df[col], format="%m/%d/%Y").dt.strftime("%Y-%m-%d")

    if DB_PATH.exists():
        DB_PATH.unlink()  # rebuild from scratch every time
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("orders", conn, index=False)

    print(f"orders: {len(df):,} rows, {df.shape[1]} columns -> {DB_PATH}")
    print(f"order dates from {df.order_date.min()} to {df.order_date.max()}")


if __name__ == "__main__":
    main()
