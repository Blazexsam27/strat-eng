import pandas as pd
from strategies.base_strategy import BaseStrategy
from indicators.sma import SMA


class SMACrossoverStrategy(BaseStrategy):
    def __init__(self, short_window=20, long_window=50):
        self.short = short_window
        self.long = long_window

    def generate_signals(self, df: pd.DataFrame):
        df = df.copy()  # avoid mutating input

        # compute both SMAs (assumes SMA returns df with columns "SMA_{window}")
        df = SMA(df, self.short)
        df = SMA(df, self.long)

        short_col = f"SMA_{self.short}"
        long_col = f"SMA_{self.long}"

        # robust assignment using .loc, handle NaNs
        df["signal"] = 0
        df.loc[df[short_col].notna() & df[long_col].notna() & (df[short_col] > df[long_col]), "signal"] = 1
        df["signal"] = df["signal"].fillna(0).astype(int)

        # marker for changes in signal; fill initial NaN with 0
        df["positions"] = df["signal"].diff().fillna(0).astype(int)

        return df
