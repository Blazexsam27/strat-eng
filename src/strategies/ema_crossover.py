import pandas as pd
from strategies.base_strategy import BaseStrategy


class EMACrossoverStrategy(BaseStrategy):
    """EMA crossover (short/long). Long-only: signal=1 when short EMA > long EMA."""

    def __init__(self, short_window: int = 12, long_window: int = 26):
        self.short = short_window
        self.long = long_window

    def generate_signals(self, df: pd.DataFrame):
        df = df.copy()
        if "Close" not in df.columns:
            raise KeyError("DataFrame must contain 'Close' column")
        short_col = f"EMA_{self.short}"
        long_col = f"EMA_{self.long}"
        df[short_col] = df["Close"].ewm(span=self.short, adjust=False).mean()
        df[long_col] = df["Close"].ewm(span=self.long, adjust=False).mean()
        df["signal"] = 0
        df.loc[
            df[short_col].notna()
            & df[long_col].notna()
            & (df[short_col] > df[long_col]),
            "signal",
        ] = 1
        df["signal"] = df["signal"].fillna(0).astype(int)
        return df
