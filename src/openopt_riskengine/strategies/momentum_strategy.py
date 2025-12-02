import pandas as pd
from strategies.base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """N-day momentum: long when price change over lookback > threshold."""

    def __init__(self, lookback: int = 20, threshold: float = 0.0):
        self.lookback = lookback
        self.threshold = threshold

    def generate_signals(self, df: pd.DataFrame):
        df = df.copy()
        if "Close" not in df.columns:
            raise KeyError("DataFrame must contain 'Close' column")
        mom_col = f"mom_{self.lookback}"
        df[mom_col] = df["Close"].pct_change(periods=self.lookback)
        df["signal"] = 0
        df.loc[df[mom_col].notna() & (df[mom_col] > self.threshold), "signal"] = 1
        df["signal"] = df["signal"].fillna(0).astype(int)
        return df
