import streamlit as st
import pandas as pd
import numpy as np
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
from risk.measures import value_at_risk, conditional_value_at_risk
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.buy_and_hold_strategy import BuyAndHoldStrategy
from strategies.ema_crossover import EMACrossoverStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.rsi_strategy import RSIStrategy

st.set_page_config(
    page_title="Risk Report — OpenOpt RiskEngine",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .risk-alert-high { background-color: #ff6b6b; color: white; padding: 15px; border-radius: 8px; }
    .risk-alert-medium { background-color: #ffa500; color: white; padding: 15px; border-radius: 8px; }
    .risk-alert-low { background-color: #4caf50; color: white; padding: 15px; border-radius: 8px; }
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


def get_risk_level(var_95: float, max_dd: float) -> str:
    """Classify risk level based on VaR and max drawdown."""
    if var_95 < -0.05 and max_dd > -0.15:
        return "LOW"
    elif var_95 < -0.10 and max_dd > -0.25:
        return "MEDIUM"
    else:
        return "HIGH"


def calculate_rolling_var(returns: pd.Series, window: int = 60) -> pd.Series:
    """Calculate rolling VaR."""
    return returns.rolling(window).quantile(0.05)


def calculate_rolling_cvar(returns: pd.Series, window: int = 60) -> pd.Series:
    """Calculate rolling CVaR (Expected Shortfall)."""
    return returns.rolling(window).apply(
        lambda x: (
            x[x <= x.quantile(0.05)].mean()
            if len(x[x <= x.quantile(0.05)]) > 0
            else x.min()
        )
    )


def sidebar_config():
    st.sidebar.header("⚙️ Risk Analysis Config")
    ticker = st.sidebar.text_input("📊 Ticker", value=DEFAULT_TICKER)
    start = st.sidebar.date_input(
        "📅 Start date", pd.to_datetime(START_DATE)
    ).isoformat()
    end = st.sidebar.date_input("📅 End date", pd.to_datetime(END_DATE)).isoformat()

    st.sidebar.markdown("---")
    strategy_name = st.sidebar.selectbox("Strategy", list(STRATEGIES.keys()))

    st.sidebar.markdown("---")
    st.sidebar.subheader("Risk Parameters")
    confidence_level = st.sidebar.slider("Confidence Level (%)", 90, 99, 95)
    rolling_window = st.sidebar.slider("Rolling Window (days)", 30, 250, 60)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Backtest Settings")
    capital = st.sidebar.number_input("💰 Capital", value=100000.0, step=1000.0)
    commission_pct = st.sidebar.number_input("Commission %", value=0.0005, step=0.0001)

    run = st.sidebar.button("🔍 Analyze Risk", use_container_width=True)

    return {
        "ticker": ticker,
        "start": start,
        "end": end,
        "strategy": strategy_name,
        "confidence": confidence_level / 100,
        "rolling_window": rolling_window,
        "capital": capital,
        "commission_pct": commission_pct,
        "run": run,
    }


def display_risk_overview(metrics: dict, returns: pd.Series):
    """Display overview risk metrics and alerts."""
    st.subheader("⚠️ Risk Overview")

    var_95 = metrics.get("VaR_95", 0)
    cvar_95 = metrics.get("CVaR_95", 0)
    max_dd = metrics.get("max_drawdown", 0)

    risk_level = get_risk_level(var_95, max_dd)

    # Risk alert box
    if risk_level == "HIGH":
        st.markdown(
            '<div class="risk-alert-high"><strong>🔴 HIGH RISK</strong> — Portfolio exhibits significant downside risk</div>',
            unsafe_allow_html=True,
        )
    elif risk_level == "MEDIUM":
        st.markdown(
            '<div class="risk-alert-medium"><strong>🟡 MEDIUM RISK</strong> — Moderate exposure to adverse movements</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="risk-alert-low"><strong>🟢 LOW RISK</strong> — Risk profile is acceptable</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # Risk metric cards
    r1, r2, r3, r4, r5 = st.columns(5)

    r1.metric("📊 VaR (95%)", f"{var_95:.2%}", help="Worst 5% loss magnitude")
    r2.metric("⛔ CVaR (95%)", f"{cvar_95:.2%}", help="Expected loss in worst 5%")
    r3.metric("📉 Max Drawdown", f"{max_dd:.2%}", help="Largest peak-to-trough decline")
    r4.metric(
        "📈 Volatility",
        f"{metrics.get('annualized_vol', 0):.2%}",
        help="Annualized return volatility",
    )
    r5.metric(
        "⚡ Sharpe Ratio",
        f"{metrics.get('sharpe', 0):.2f}",
        help="Risk-adjusted return",
    )


def display_var_analysis(returns: pd.Series, confidence: float):
    """Display VaR/CVaR analysis."""
    st.subheader("📊 Value at Risk (VaR) Analysis")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**VaR at Different Confidence Levels**")
        confidence_levels = [0.90, 0.95, 0.99]
        var_data = {
            "Confidence": [f"{c:.0%}" for c in confidence_levels],
            "VaR": [
                f"{value_at_risk(returns.dropna().values, c):.4f}"
                for c in confidence_levels
            ],
            "CVaR": [
                f"{conditional_value_at_risk(returns.dropna().values, c):.4f}"
                for c in confidence_levels
            ],
        }
        st.dataframe(pd.DataFrame(var_data), use_container_width=True)

    with col2:
        st.markdown("**Return Distribution**")
        fig_hist = px.histogram(
            returns.dropna(),
            nbins=60,
            labels={"value": "Return", "count": "Frequency"},
            title="Daily Returns Histogram",
        )
        var_95 = value_at_risk(returns.dropna().values, 0.95)
        fig_hist.add_vline(
            x=var_95, line_dash="dash", line_color="red", annotation_text="VaR 95%"
        )
        st.plotly_chart(fig_hist, use_container_width=True)


def display_rolling_risk(df_bt: pd.DataFrame, window: int):
    """Display rolling VaR and CVaR."""
    st.subheader("📈 Rolling Risk Metrics")

    if "net_strategy_returns" in df_bt.columns:
        returns = df_bt["net_strategy_returns"]

        rolling_var = calculate_rolling_var(returns, window=window)
        rolling_cvar = calculate_rolling_cvar(returns, window=window)

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df_bt.index,
                y=rolling_var,
                mode="lines",
                name=f"Rolling VaR ({window}d)",
                line=dict(color="red"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_bt.index,
                y=rolling_cvar,
                mode="lines",
                name=f"Rolling CVaR ({window}d)",
                line=dict(color="darkred", dash="dash"),
            )
        )
        fig.update_layout(
            height=400,
            title="Rolling Value at Risk & Conditional Value at Risk",
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)


def display_drawdown_analysis(df_bt: pd.DataFrame):
    """Display detailed drawdown analysis."""
    st.subheader("📉 Drawdown Analysis")

    if "equity_curve" in df_bt.columns:
        running_max = df_bt["equity_curve"].cummax()
        drawdown = (df_bt["equity_curve"] - running_max) / running_max

        # Find major drawdowns
        col1, col2 = st.columns([2, 1])

        with col1:
            fig_dd = go.Figure()
            fig_dd.add_trace(
                go.Scatter(
                    x=df_bt.index,
                    y=drawdown * 100,
                    fill="tozeroy",
                    name="Drawdown %",
                    line=dict(color="red"),
                )
            )
            fig_dd.update_layout(
                height=350,
                title="Underwater Plot",
                yaxis_title="Drawdown (%)",
                hovermode="x unified",
            )
            st.plotly_chart(fig_dd, use_container_width=True)

        with col2:
            st.markdown("**Drawdown Statistics**")
            max_dd = drawdown.min()
            avg_dd = drawdown[drawdown < 0].mean() if (drawdown < 0).any() else 0
            dd_duration = (drawdown < 0).sum()

            st.metric("Max Drawdown", f"{max_dd:.2%}")
            st.metric("Avg Drawdown", f"{avg_dd:.2%}")
            st.metric("Drawdown Days", f"{int(dd_duration)}")


def display_stress_tests(returns: pd.Series):
    """Display stress test scenarios."""
    st.subheader("⚡ Stress Testing")

    st.markdown("**Scenario Analysis: Portfolio Loss Under Stress**")

    # Define stress scenarios
    scenarios = {
        "Normal (μ ± σ)": {"mean_shift": 0, "vol_mult": 1.0},
        "Mild Stress": {"mean_shift": -0.01, "vol_mult": 1.5},
        "Moderate Stress": {"mean_shift": -0.02, "vol_mult": 2.0},
        "Severe Stress": {"mean_shift": -0.05, "vol_mult": 3.0},
    }

    scenario_results = []
    ret_mean = returns.mean()
    ret_std = returns.std()

    for scenario_name, params in scenarios.items():
        stressed_mean = ret_mean + params["mean_shift"]
        stressed_std = ret_std * params["vol_mult"]
        stressed_var = np.percentile(
            np.random.normal(stressed_mean, stressed_std, 10000), 5
        )
        scenario_results.append(
            {
                "Scenario": scenario_name,
                "Expected Return": f"{stressed_mean:.4f}",
                "Volatility": f"{stressed_std:.4f}",
                "VaR (95%)": f"{stressed_var:.4f}",
            }
        )

    st.dataframe(pd.DataFrame(scenario_results), use_container_width=True)


def display_risk_heatmap(df_bt: pd.DataFrame):
    """Display correlation heatmap of key risk factors."""
    st.subheader("🔥 Risk Factor Correlation")

    if "net_strategy_returns" in df_bt.columns and "Close" in df_bt.columns:
        # Select numeric columns for correlation
        numeric_cols = df_bt.select_dtypes(include=[np.number]).columns
        correlation_matrix = df_bt[numeric_cols].corr()

        fig = px.imshow(
            correlation_matrix,
            labels=dict(color="Correlation"),
            title="Risk Factor Correlation Matrix",
            color_continuous_scale="RdBu",
            zmin=-1,
            zmax=1,
        )
        st.plotly_chart(fig, use_container_width=True)


def main():
    st.title("⚠️ Risk Report — OpenOpt RiskEngine")
    st.markdown("*Comprehensive risk analysis and stress testing dashboard*")
    st.markdown("---")

    config = sidebar_config()

    if config["run"]:
        with st.spinner("📊 Fetching market data..."):
            try:
                df = cached_fetch(config["ticker"], config["start"], config["end"])
            except Exception as e:
                st.error(f"❌ Failed to fetch data: {e}")
                return

        st.success(f"✅ Data loaded: {len(df)} rows")

        with st.spinner("🔄 Running backtest..."):
            strat = make_strategy_instance(config["strategy"])
            try:
                df_signals = strat.generate_signals(df.copy())
                df_bt, metrics = run_backtest(
                    df_signals,
                    capital=float(config["capital"]),
                    commission_pct=float(config["commission_pct"]),
                )
            except Exception as e:
                st.error(f"❌ Backtest failed: {e}")
                return

        st.success(f"✅ Backtest complete for {config['strategy']}")

        # Risk overview
        if "net_strategy_returns" in df_bt.columns:
            returns = df_bt["net_strategy_returns"]
            display_risk_overview(metrics, returns)

            # VaR Analysis
            display_var_analysis(returns, config["confidence"])

            # Rolling risk
            display_rolling_risk(df_bt, config["rolling_window"])

            # Drawdown analysis
            display_drawdown_analysis(df_bt)

            # Stress tests
            display_stress_tests(returns)

            # Risk heatmap
            display_risk_heatmap(df_bt)

            # Raw metrics
            with st.expander("📋 Full Risk Metrics (JSON)"):
                st.json(metrics)
        else:
            st.warning("⚠️ No return data available for risk analysis")

    else:
        st.info("👈 Configure parameters and click '🔍 Analyze Risk' to begin")
        st.markdown(
            """
        ## What This Report Provides:

        - **VaR & CVaR:** Value at Risk and Conditional Value at Risk at multiple confidence levels
        - **Rolling Risk Metrics:** Time-series visualization of risk exposure
        - **Drawdown Analysis:** Peak-to-trough losses and recovery patterns
        - **Stress Testing:** Portfolio behavior under adverse market scenarios
        - **Risk Correlations:** Factor relationships and diversification effectiveness

        Use this report to monitor and manage portfolio risk in real-time.
        """
        )


if __name__ == "__main__":
    main()
