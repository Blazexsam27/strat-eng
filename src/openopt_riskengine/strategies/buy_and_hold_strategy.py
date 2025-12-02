import pandas as pd
from strategies.base_strategy import BaseStrategy


def _extract_close_series(df: pd.DataFrame) -> pd.Series:
    """
    Return a single-close Series from df. Handles simple columns and common MultiIndex forms
    (e.g., yfinance multi-ticker frames). Raises KeyError if no close-like column is found.
    """
    if "Close" in df.columns:
        s = df["Close"]
    elif isinstance(df.columns, pd.MultiIndex):
        # prefer columns where any level == 'Close'
        matches = [col for col in df.columns if any((lvl == "Close") for lvl in col)]
        if not matches:
            # fallback: any column name that contains 'Close' when stringified
            matches = [col for col in df.columns if "Close" in str(col)]
        if matches:
            s = df[matches[0]]
        else:
            raise KeyError("No 'Close' column found in DataFrame (including MultiIndex columns).")
    else:
        raise KeyError("No 'Close' column found in DataFrame.")

    # if we still have a DataFrame (e.g., multiple tickers), take the first column as the price series
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s


class BuyAndHoldStrategy(BaseStrategy):
    """Simple buy-and-hold signal generator: signal=1 whenever Close is available."""

    def generate_signals(self, df: pd.DataFrame):
        df = df.copy()
        close = _extract_close_series(df)
        # create signal column and set to 1 where Close is present
        df["signal"] = 0
        mask = close.notna()
        df.loc[mask, "signal"] = 1
        df["signal"] = df["signal"].astype(int)
        return df
