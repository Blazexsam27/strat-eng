import pandas as pd
import numpy as np
from risk.measures import value_at_risk, conditional_value_at_risk


def run_backtest(
    df: pd.DataFrame,
    capital: float = 10000.0,
    commission_per_trade: float = 0.0,
    commission_pct: float = 0.0,
    periods_per_year: int = 252,
):
    """
    Vectorized backtest with simple transaction-costs.

    Changes vs. previous version:
    - Aligns executed exposure = signal.shift(1) (same as before).
    - Detects trades and applies two simple cost models:
        * commission_per_trade: flat cost per executed trade
        * commission_pct: proportional cost applied to approximate trade value
      These are applied as an approximate deduction from returns (see note).
    - Returns same dataframe augmented with returns, strategy_returns, net_strategy_returns,
      equity_curve (post-costs), trade markers, and a richer metrics dict.

    Notes / approximations:
    - commission_pct is proportional to an approximate trade value = capital * abs(change_in_position).
      This is a simple approximation (no per-share sizing). For precise P/L you'd need position sizing/shares.
    - Costs are converted to an equivalent return headwind relative to starting capital for vectorized simplicity.
    """

    df = df.copy()

    if "Close" not in df.columns or "signal" not in df.columns:
        raise KeyError("DataFrame must contain 'Close' and 'signal' columns")

    # price returns; treat first-period return as 0
    df["returns"] = df["Close"].pct_change().fillna(0.0)

    # desired position (0/1/-1) and executed exposure (use prior day's signal)
    position = df["signal"].fillna(0).astype(float)
    executed_pos = position.shift(1).fillna(0.0)

    # gross strategy returns (before costs)
    df["strategy_returns"] = df["returns"] * executed_pos

    # detect executed trades:
    # change in desired position occurs at day t; execution happens at t+1 in this scheme,
    # so shift the position change forward to align with execution day.
    pos_change = position.diff().fillna(0.0)
    executed_change = pos_change.shift(1).fillna(0.0)  # change that is executed today
    df["trade"] = executed_change.abs()  # 1 for any change, 2 if from -1 to 1 etc.

    # approximate trade value = capital * abs(executed_change)
    trade_value = capital * df["trade"]

    # absolute number-of-trades (count any non-zero executed change as a trade event)
    df["trade_event"] = (df["trade"] > 0).astype(int)

    # compute cost per row (absolute dollar)
    df["trade_cost"] = (
        df["trade_event"] * commission_per_trade + commission_pct * trade_value
    )

    # convert cost to equivalent return headwind relative to starting capital (approximation)
    df["cost_return"] = df["trade_cost"] / capital

    # net strategy returns after costs (approx)
    df["net_strategy_returns"] = df["strategy_returns"] - df["cost_return"]

    # equity curve starting from capital using net returns
    df["equity_curve"] = capital * (1.0 + df["net_strategy_returns"]).cumprod()

    # basic metrics
    final_equity = float(df["equity_curve"].iloc[-1])
    total_return = final_equity - capital
    total_return_pct = final_equity / capital - 1.0

    # max drawdown
    running_max = df["equity_curve"].cummax()
    drawdown = (df["equity_curve"] - running_max) / running_max
    max_drawdown = float(drawdown.min())

    # diagnostic stats (annualized)
    # use net_strategy_returns for vol/sharpe
    ann_vol = float(df["net_strategy_returns"].std() * np.sqrt(periods_per_year))
    ann_return = (
        (1.0 + total_return_pct) ** (periods_per_year / max(len(df), 1)) - 1.0
        if len(df) > 0
        else 0.0
    )
    # approximate Sharpe (risk-free ~0)
    sharpe = float(
        (df["net_strategy_returns"].mean() * periods_per_year)
        / (ann_vol if ann_vol > 0 else np.nan)
    )

    # Risk measures (VaR/CVaR) on the return series
    returns_arr = df["net_strategy_returns"].dropna().to_numpy()
    try:
        var_95 = float(value_at_risk(returns_arr, confidence_level=0.95))
        cvar_95 = float(conditional_value_at_risk(returns_arr, confidence_level=0.95))
    except Exception:
        var_95 = float("nan")
        cvar_95 = float("nan")

    metrics = {
        "final_equity": final_equity,
        "total_return": float(total_return),
        "total_return_pct": float(total_return_pct),
        "max_drawdown": max_drawdown,
        "annualized_vol": ann_vol,
        "approx_annual_return": ann_return,
        "sharpe": sharpe,
        "n_trades": int(df["trade_event"].sum()),
        "total_commission_paid": float(df["trade_cost"].sum()),
        "VaR_95": var_95,
        "CVaR_95": cvar_95,
    }

    return df, metrics
