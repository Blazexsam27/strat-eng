import os
import yfinance as yf
from config import DATA_DIR


def fetch_price_data(ticker: str, start: str, end: str, save: bool = True):
    df = yf.download(ticker, start=start, end=end)

    if df.empty:
        raise ValueError(
            f"No data found for ticker {ticker} between {start} and {end}."
        )

    if save:
        os.makedirs(DATA_DIR, exist_ok=True)
        file_path = os.path.join(DATA_DIR, f"{ticker}_price_data.csv")
        df.to_csv(file_path)
        print(f"Data saved to {file_path}")

    return df


# df = fetch_price_data(DEFAULT_TICKER, "2015-01-01", "2025-01-01")
# print(df.head())
