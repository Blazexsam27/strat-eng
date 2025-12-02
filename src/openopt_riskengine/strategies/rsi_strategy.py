import pandas as pd
from strategies.base_strategy import BaseStrategy


class RSIStrategy(BaseStrategy):
    """RSI-based long-only strategy.
    - buys when RSI <= oversold (default 30)
    - exits when RSI >= overbought (default 70)
    """

    def __init__(self, period: int = 14, oversold: int = 30, overbought: int = 70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, df: pd.DataFrame):
        df = df.copy()
        if "Close" not in df.columns:
            raise KeyError("DataFrame must contain 'Close' column")

        delta = df["Close"].diff()
        gain = delta.clip(lower=0.0)
        loss = -delta.clip(upper=0.0)

        # Wilder's smoothing via ewm with alpha = 1/period (common RSI implementation)
        avg_gain = gain.ewm(alpha=1.0 / self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / self.period, adjust=False).mean()

        rs = avg_gain / (avg_loss.replace(0, pd.NA))
        df["rsi"] = 100 - 100 / (1 + rs)
        df["rsi"] = df["rsi"].fillna(50.0)  # neutral where not computable

        df["signal"] = 0
        df.loc[df["rsi"] <= self.oversold, "signal"] = 1
        # keep 0 when RSI in (oversold, overbought); you can add short signals if desired
        df["signal"] = df["signal"].fillna(0).astype(int)
        return df
