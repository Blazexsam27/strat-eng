import pandas as pd
import numpy as np


class Strategy:
    def __init__(self, name):
        self.name = name

    def backtest(self, data):
        raise NotImplementedError("Backtest method must be implemented by subclasses.")


def _extract_close_series(df: pd.DataFrame) -> pd.Series:
    """Return a single price series for Close (handle simple and MultiIndex frames)."""
    if "Close" in df.columns:
        s = df["Close"]
    elif isinstance(df.columns, pd.MultiIndex):
        matches = [col for col in df.columns if any((lvl == "Close") for lvl in col)]
        if not matches:
            matches = [col for col in df.columns if "Close" in str(col)]
        if not matches:
            raise KeyError("No 'Close' column found in DataFrame (including MultiIndex).")
        s = df[matches[0]]
    else:
        raise KeyError("No 'Close' column found in DataFrame.")
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s


class CoveredCall(Strategy):
    def __init__(self, strike_price: float, premium: float):
        super().__init__("Covered Call")
        self.strike_price = float(strike_price)
        self.premium = float(premium)

    def backtest(
        self,
        data: pd.DataFrame,
        capital: float = 10000.0,
        shares: int = 1,
        entry_date=None,
        expiry_date=None,
    ):
        """
        Simple covered-call backtest (single-leg, unrolled):
        - Buy `shares` of underlying at first available close (or entry_date).
        - Sell one call per share, collect `self.premium` upfront.
        - Option is European and settles at expiry_date (defaults to last row).
        - Option payoff is paid at expiry; before expiry we treat option MTM as 0 (simplified).
        Returns augmented df and metrics.
        """
        df = data.copy()
        close = _extract_close_series(df)
        idx = close.index

        if entry_date is None:
            entry_idx = idx[0]
        else:
            entry_idx = pd.to_datetime(entry_date)
            if entry_idx not in idx:
                entry_idx = idx[idx.get_indexer([entry_idx], method="nearest")[0]]

        if expiry_date is None:
            expiry_idx = idx[-1]
        else:
            expiry_idx = pd.to_datetime(expiry_date)
            if expiry_idx not in idx:
                expiry_idx = idx[idx.get_indexer([expiry_idx], method="nearest")[0]]

        # cash: start with capital; buy shares at entry price, receive premium credit
        entry_price = float(close.loc[entry_idx])
        cash = capital - shares * entry_price + shares * self.premium

        # build equity series: before expiry, equity = shares * close + cash
        equity = shares * close + cash

        # at expiry, settle short call: payoff = max(0, S_T - K) * shares (we pay this)
        payoff = max(0.0, float(close.loc[expiry_idx]) - self.strike_price) * shares
        # subtract payoff from cash at/after expiry
        cash_after_expiry = cash - payoff
        # adjust equity for dates >= expiry
        equity.loc[equity.index >= expiry_idx] = shares * close.loc[equity.index >= expiry_idx] + cash_after_expiry

        df = df.assign(equity_curve=equity.values)
        final_equity = float(df["equity_curve"].iloc[-1])
        total_return = final_equity - capital
        total_return_pct = final_equity / capital - 1.0

        running_max = df["equity_curve"].cummax()
        drawdown = (df["equity_curve"] - running_max) / running_max
        max_drawdown = float(drawdown.min())

        metrics = {
            "final_equity": final_equity,
            "total_return": float(total_return),
            "total_return_pct": float(total_return_pct),
            "max_drawdown": max_drawdown,
            "n_trades": 1,  # buy and one option write
            "total_premium_received": float(shares * self.premium),
            "option_payoff_at_expiry": float(payoff),
        }
        return df, metrics


class Straddle(Strategy):
    def __init__(self, strike_price: float, premium_call: float = 0.0, premium_put: float = 0.0):
        super().__init__("Straddle")
        self.strike_price = float(strike_price)
        self.premium_call = float(premium_call)
        self.premium_put = float(premium_put)

    def backtest(
        self,
        data: pd.DataFrame,
        capital: float = 10000.0,
        entry_date=None,
        expiry_date=None,
        contracts: int = 1,
    ):
        """
        Simple long straddle backtest (single purchase, no rolling).
        - Buy `contracts` of 1-call + 1-put at strike; pay premiums upfront.
        - Approximate option MTM by intrinsic value only: call = max(0, S-K), put = max(0, K-S).
          (This ignores time value; good enough for basic behavior checks.)
        - Entry and expiry defaults same as CoveredCall.
        """
        df = data.copy()
        close = _extract_close_series(df)
        idx = close.index

        if entry_date is None:
            entry_idx = idx[0]
        else:
            entry_idx = pd.to_datetime(entry_date)
            if entry_idx not in idx:
                entry_idx = idx[idx.get_indexer([entry_idx], method="nearest")[0]]

        if expiry_date is None:
            expiry_idx = idx[-1]
        else:
            expiry_idx = pd.to_datetime(expiry_date)
            if expiry_idx not in idx:
                expiry_idx = idx[idx.get_indexer([expiry_idx], method="nearest")[0]]

        total_premium = contracts * (self.premium_call + self.premium_put)
        # initial cash after paying premiums
        cash = capital - total_premium

        # intrinsic values per day
        S = close
        call_intrinsic = (S - self.strike_price).clip(lower=0.0)
        put_intrinsic = (self.strike_price - S).clip(lower=0.0)
        option_value = contracts * (call_intrinsic + put_intrinsic)

        # equity: cash + current option intrinsic (we don't hold underlying)
        equity = cash + option_value

        df = df.assign(equity_curve=equity.values, call_intrinsic=call_intrinsic.values, put_intrinsic=put_intrinsic.values)
        final_equity = float(df["equity_curve"].iloc[-1])
        total_return = final_equity - capital
        total_return_pct = final_equity / capital - 1.0

        running_max = df["equity_curve"].cummax()
        drawdown = (df["equity_curve"] - running_max) / running_max
        max_drawdown = float(drawdown.min())

        metrics = {
            "final_equity": final_equity,
            "total_return": float(total_return),
            "total_return_pct": float(total_return_pct),
            "max_drawdown": max_drawdown,
            "n_trades": 1,
            "total_premium_paid": float(total_premium),
        }
        return df, metrics


# Additional strategies can be defined here
