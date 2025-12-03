import streamlit as st
import pandas as pd

from config import DEFAULT_TICKER, START_DATE, END_DATE
from data.fetcher import fetch_price_data
from backtesting.engine import run_backtest

from strategies.sma_crossover import SMACrossoverStrategy
from strategies.buy_and_hold_strategy import BuyAndHoldStrategy
from strategies.ema_crossover import EMACrossoverStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.rsi_strategy import RSIStrategy

st.set_page_config(page_title="OpenOpt RiskEngine — Strategy Dashboard", layout="wide")


@st.cache_data(ttl=60 * 60)
def cached_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    return fetch_price_data(ticker, start, end)


STRATEGIES = {
    "SMA Crossover (20/50)": SMACrossoverStrategy,
    "Buy & Hold": BuyAndHoldStrategy,
    "EMA Crossover (12/26)": EMACrossoverStrategy,
    "Momentum (20)": MomentumStrategy,
    "RSI (14)": RSIStrategy,
}


def make_strategy_instance(name: str):
    cls = STRATEGIES.get(name)
    if cls is SMACrossoverStrategy:
        return cls(short_window=20, long_window=50)
    if cls is EMACrossoverStrategy:
        return cls(short_window=12, long_window=26)
    if cls is MomentumStrategy:
        return cls(lookback=20)
    if cls is RSIStrategy:
        return cls(period=14)
    return cls()


def sidebar_inputs():
    st.sidebar.header("Data & Backtest")
    ticker = st.sidebar.text_input("Ticker", value=DEFAULT_TICKER)
    start = st.sidebar.date_input("Start date", pd.to_datetime(START_DATE)).isoformat()
    end = st.sidebar.date_input("End date", pd.to_datetime(END_DATE)).isoformat()

    st.sidebar.markdown("---")
    strategy_name = st.sidebar.selectbox("Strategy", list(STRATEGIES.keys()))
    capital = st.sidebar.number_input(
        "Starting capital", value=100000.0, step=1000.0, format="%.2f"
    )
    commission_per_trade = st.sidebar.number_input(
        "Commission per trade (USD)", value=1.0, step=0.1, format="%.4f"
    )
    commission_pct = st.sidebar.number_input(
        "Commission % (proportional)", value=0.0005, step=0.0001, format="%.6f"
    )
    run = st.sidebar.button("Run backtest")
    return (
        ticker,
        start,
        end,
        strategy_name,
        capital,
        commission_per_trade,
        commission_pct,
        run,
    )


def show_metrics(metrics: dict):
    st.subheader("Summary Metrics")
    # convert to user-friendly table
    table = {
        "Final Equity": metrics.get("final_equity"),
        "Total Return ($)": metrics.get("total_return"),
        "Total Return (%)": metrics.get("total_return_pct"),
        "CAGR / Approx Annual Return": metrics.get(
            "cagr", metrics.get("approx_annual_return")
        ),
        "Annualized Vol": metrics.get("annualized_vol"),
        "Sharpe": metrics.get("sharpe"),
        "Max Drawdown": metrics.get("max_drawdown"),
        "VaR 95%": metrics.get("VaR_95"),
        "CVaR 95%": metrics.get("CVaR_95"),
        "Number of Trades": metrics.get("n_trades", metrics.get("n_trades", 0)),
        "Total Commissions Paid": metrics.get(
            "total_commission_paid", metrics.get("total_commission_paid", 0.0)
        ),
    }
    dfm = pd.Series(table, name="Value").to_frame()
    st.table(dfm)


def plot_results(df_bt: pd.DataFrame):
    st.subheader("Charts")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("Equity curve")
        if "equity_curve" in df_bt.columns:
            st.line_chart(df_bt["equity_curve"])
        else:
            st.info("No equity_curve in results")

        st.markdown("Price and signals")
        price_df = pd.DataFrame({"Close": df_bt["Close"]})
        # overlay SMA/EMA or signals if present
        for c in df_bt.columns:
            if (
                c.startswith("SMA_")
                or c.startswith("EMA_")
                or c == "rsi"
                or c.startswith("mom_")
            ):
                price_df[c] = df_bt[c]
        st.line_chart(price_df)

    with col2:
        st.markdown("Return distribution")
        if "net_strategy_returns" in df_bt.columns:
            st.bar_chart(df_bt["net_strategy_returns"].fillna(0.0).tail(252))
        else:
            st.info("No returns to show")

    # show trade table if available
    if "trade_event" in df_bt.columns:
        trades = df_bt[df_bt["trade_event"] > 0][
            ["Close", "trade_event", "trade_cost"]
        ].copy()
        if not trades.empty:
            st.subheader("Trade events (sample)")
            st.dataframe(trades.head(50))


def main():
    st.title("OpenOpt RiskEngine — Strategy Dashboard")
    (
        ticker,
        start,
        end,
        strategy_name,
        capital,
        commission_per_trade,
        commission_pct,
        run,
    ) = sidebar_inputs()

    if run:
        with st.spinner(f"Fetching {ticker} ({start} → {end})"):
            try:
                df = cached_fetch(ticker, start, end)
            except Exception as e:
                st.error(f"Error fetching data: {e}")
                return

        st.success(f"Data fetched: {len(df)} rows")

        strat = make_strategy_instance(strategy_name)
        try:
            df_signals = strat.generate_signals(df.copy())
        except Exception as e:
            st.error(f"Error generating signals: {e}")
            return

        try:
            df_bt, metrics = run_backtest(
                df_signals,
                capital=float(capital),
                commission_per_trade=float(commission_per_trade),
                commission_pct=float(commission_pct),
            )
        except Exception as e:
            st.error(f"Error running backtest: {e}")
            return

        show_metrics(metrics)
        plot_results(df_bt)

        st.subheader("Full metrics (raw)")
        st.json(metrics)


if __name__ == "__main__":
    main()
