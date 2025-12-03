import pandas as pd


def SMA(df: pd.DataFrame, period: int = 20):
    df[f"SMA_{period}"] = df["Close"].rolling(period).mean()
    return df
