import pandas as pd


def EMA(df: pd.DataFrame, period: int = 20):
    df[f"EMA_{period}"] = df["Close"].ewm(span=period, adjust=False).mean()
    return df
