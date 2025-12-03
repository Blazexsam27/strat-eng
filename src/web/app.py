import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import sys


project_src = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
    )
)
if project_src not in sys.path:
    sys.path.insert(0, project_src)

from config import DEFAULT_TICKER, START_DATE, END_DATE
from data.fetcher import fetch_price_data
from backtesting.engine import run_backtest

from strategies.sma_crossover import SMACrossoverStrategy
from strategies.buy_and_hold_strategy import BuyAndHoldStrategy
from strategies.ema_crossover import EMACrossoverStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.rsi_strategy import RSIStrategy

st.set_page_config(
    page_title="OpenOpt RiskEngine", layout="wide", initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown(
    """
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        margin: 10px 0;
    }
    .metric-label {
        font-size: 14px;
        opacity: 0.9;
    }
</style>
""",
    unsafe_allow_html=True,
)


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
    st.sidebar.header("⚙️ Configuration")
    ticker = st.sidebar.text_input("📊 Ticker", value=DEFAULT_TICKER)
    start = st.sidebar.date_input(
        "📅 Start date", pd.to_datetime(START_DATE)
    ).isoformat()
    end = st.sidebar.date_input("📅 End date", pd.to_datetime(END_DATE)).isoformat()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Strategy & Costs")
    strategy_name = st.sidebar.selectbox("Strategy", list(STRATEGIES.keys()))
    capital = st.sidebar.number_input(
        "💰 Starting capital", value=100000.0, step=1000.0, format="%.2f"
    )
    commission_per_trade = st.sidebar.number_input(
        "💳 Commission per trade (USD)", value=1.0, step=0.1, format="%.4f"
    )
    commission_pct = st.sidebar.number_input(
        "📈 Commission % (proportional)", value=0.0005, step=0.0001, format="%.6f"
    )
    run = st.sidebar.button("▶️ Run Backtest", use_container_width=True)
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


def metric_card(label: str, value: str, delta: str = None, col=None):
    """Display a metric card with optional delta."""
    if col is None:
        col = st
    with col:
        if delta:
            col.metric(label, value, delta=delta)
        else:
            col.metric(label, value)


def show_metrics(metrics: dict):
    st.subheader("📊 Performance Summary")

    # Key metrics in cards
    m1, m2, m3, m4 = st.columns(4)

    final_eq = metrics.get("final_equity", 0)
    initial_cap = 100000  # default
    total_ret_pct = metrics.get("total_return_pct", 0)

    m1.metric(
        "💵 Final Equity",
        f"${final_eq:,.0f}",
        delta=f"{total_ret_pct:.2%}",
        delta_color="inverse",
    )
    m2.metric(
        "📈 CAGR",
        f"{metrics.get('cagr', metrics.get('approx_annual_return', 0)):.2%}",
    )
    m3.metric(
        "📉 Max Drawdown",
        f"{metrics.get('max_drawdown', 0):.2%}",
        delta_color="inverse",
    )
    m4.metric(
        "⚡ Sharpe Ratio",
        f"{metrics.get('sharpe', 0):.2f}",
    )

    st.markdown("---")

    # Risk metrics
    r1, r2, r3 = st.columns(3)
    r1.metric("📊 Annualized Vol", f"{metrics.get('annualized_vol', 0):.2%}")
    r2.metric("⚠️ VaR 95%", f"{metrics.get('VaR_95', 0):.2%}")
    r3.metric("⛔ CVaR 95%", f"{metrics.get('CVaR_95', 0):.2%}")

    st.markdown("---")

    # Trade & cost metrics
    t1, t2, t3 = st.columns(3)
    t1.metric("🔄 Number of Trades", f"{int(metrics.get('n_trades', 0))}")
    t2.metric(
        "💳 Total Commissions", f"${metrics.get('total_commission_paid', 0):,.2f}"
    )
    t3.metric("💰 Total Return ($)", f"${metrics.get('total_return', 0):,.0f}")


def plot_results(df_bt: pd.DataFrame):
    st.subheader("📈 Performance Charts")

    # Equity curve with plotly
    st.markdown("**Equity Curve Over Time**")
    if "equity_curve" in df_bt.columns:
        fig_eq = go.Figure()
        fig_eq.add_trace(
            go.Scatter(
                x=df_bt.index,
                y=df_bt["equity_curve"],
                mode="lines",
                name="Equity",
                fill="tozeroy",
                line=dict(color="#1f77b4", width=2),
            )
        )
        fig_eq.update_layout(height=400, hovermode="x unified", margin=dict(t=20, b=20))
        st.plotly_chart(fig_eq, use_container_width=True)
    else:
        st.info("No equity_curve in results")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Price & Indicators**")
        if "Close" in df_bt.columns:
            price_fig = go.Figure()
            price_fig.add_trace(
                go.Scatter(
                    x=df_bt.index,
                    y=df_bt["Close"],
                    mode="lines",
                    name="Close",
                    line=dict(color="#000000", width=2),
                )
            )
            # Add SMA/EMA indicators
            for c in df_bt.columns:
                col_str = str(c)
                if "SMA_" in col_str or "EMA_" in col_str:
                    price_fig.add_trace(
                        go.Scatter(
                            x=df_bt.index,
                            y=df_bt[c],
                            mode="lines",
                            name=col_str,
                            line=dict(dash="dash"),
                        )
                    )
            price_fig.update_layout(
                height=350, hovermode="x unified", margin=dict(t=20, b=20)
            )
            st.plotly_chart(price_fig, use_container_width=True)

    with col2:
        st.markdown("**Daily Returns Distribution**")
        if "net_strategy_returns" in df_bt.columns:
            returns = df_bt["net_strategy_returns"].dropna()
            fig_hist = px.histogram(
                returns,
                nbins=50,
                labels={"value": "Return", "count": "Frequency"},
                title="",
            )
            fig_hist.update_layout(height=350, margin=dict(t=20, b=20))
            st.plotly_chart(fig_hist, use_container_width=True)

    # Drawdown chart
    st.markdown("**Underwater Plot (Drawdown)**")
    if "equity_curve" in df_bt.columns:
        running_max = df_bt["equity_curve"].cummax()
        drawdown = (df_bt["equity_curve"] - running_max) / running_max * 100
        fig_dd = go.Figure()
        fig_dd.add_trace(
            go.Scatter(
                x=df_bt.index,
                y=drawdown,
                mode="lines",
                fill="tozeroy",
                name="Drawdown",
                line=dict(color="#d62728"),
            )
        )
        fig_dd.update_layout(height=300, hovermode="x unified", margin=dict(t=20, b=20))
        st.plotly_chart(fig_dd, use_container_width=True)

    # Trades table
    if "trade_event" in df_bt.columns and df_bt["trade_event"].sum() > 0:
        st.markdown("**Trade Events**")
        trades = df_bt[df_bt["trade_event"] > 0][
            ["Close", "trade_event", "trade_cost"]
        ].copy()
        if not trades.empty:
            st.dataframe(trades.head(50), use_container_width=True)


def main():
    st.title("🚀 OpenOpt RiskEngine — Strategy Dashboard")
    st.markdown("*Advanced backtesting and risk analysis for quantitative strategies*")
    st.markdown("---")

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
        with st.spinner(f"⏳ Fetching {ticker} ({start} → {end})..."):
            try:
                df = cached_fetch(ticker, start, end)
            except Exception as e:
                st.error(f"❌ Error fetching data: {e}")
                return

        st.success(f"✅ Data fetched: {len(df)} rows")

        with st.spinner(f"🔄 Running {strategy_name} backtest..."):
            strat = make_strategy_instance(strategy_name)
            try:
                df_signals = strat.generate_signals(df.copy())
            except Exception as e:
                st.error(f"❌ Error generating signals: {e}")
                return

            try:
                df_bt, metrics = run_backtest(
                    df_signals,
                    capital=float(capital),
                    commission_per_trade=float(commission_per_trade),
                    commission_pct=float(commission_pct),
                )
            except Exception as e:
                st.error(f"❌ Error running backtest: {e}")
                return

        st.success(f"✅ Backtest complete for {strategy_name}")

        show_metrics(metrics)
        plot_results(df_bt)

        # Expandable raw data section
        with st.expander("📋 View raw metrics (JSON)"):
            st.json(metrics)

    else:
        # Landing page / welcome screen
        st.info(
            "👈 Configure parameters in the sidebar and click '▶️ Run Backtest' to begin"
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📚 About OpenOpt RiskEngine")
            st.markdown(
                """
            A modern backtesting and risk analysis platform for quantitative strategies.
            
            **Features:**
            - Multiple trading strategy implementations
            - Transaction cost modeling
            - Advanced risk metrics (VaR, CVaR, Sharpe)
            - Interactive performance dashboards
            - Real-time market data integration
            """
            )

        with col2:
            st.markdown("### 🎯 Quick Start")
            st.markdown(
                """
            1. **Select a ticker** (e.g., GOOGL, AAPL)
            2. **Choose date range** for historical analysis
            3. **Pick a strategy** (SMA, EMA, Momentum, RSI)
            4. **Adjust costs** (commissions, slippage)
            5. **Click Run** to execute backtest
            
            Use the **Dashboard** page for multi-strategy comparison!
            """
            )


if __name__ == "__main__":
    main()
