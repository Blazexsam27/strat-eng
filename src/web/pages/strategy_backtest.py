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

from strategies.sma_crossover import SMACrossoverStrategy
from strategies.buy_and_hold_strategy import BuyAndHoldStrategy
from strategies.ema_crossover import EMACrossoverStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.rsi_strategy import RSIStrategy

st.set_page_config(
    page_title="Strategy Backtest — OpenOpt RiskEngine",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .strategy-winner { background: linear-gradient(135deg, #4caf50, #45a049); color: white; padding: 20px; border-radius: 10px; }
    .strategy-card { background: #f9f9f9; padding: 15px; border-radius: 8px; border-left: 4px solid #2196F3; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60 * 60)
def cached_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    return fetch_price_data(ticker, start, end)


STRATEGIES = {
    "SMA Crossover": ("SMACrossover", SMACrossoverStrategy),
    "EMA Crossover": ("EMACrossover", EMACrossoverStrategy),
    "Momentum": ("Momentum", MomentumStrategy),
    "RSI": ("RSI", RSIStrategy),
    "Buy & Hold": ("BuyAndHold", BuyAndHoldStrategy),
}


def make_strategy(name: str, params: dict):
    """Factory function to create strategy instances with custom parameters."""
    cls = STRATEGIES[name][1]
    
    if cls is SMACrossoverStrategy:
        return cls(
            short_window=int(params.get("sma_short", 20)),
            long_window=int(params.get("sma_long", 50)),
        )
    elif cls is EMACrossoverStrategy:
        return cls(
            short_window=int(params.get("ema_short", 12)),
            long_window=int(params.get("ema_long", 26)),
        )
    elif cls is MomentumStrategy:
        return cls(
            lookback=int(params.get("mom_lookback", 20)),
            threshold=float(params.get("mom_threshold", 0.0)),
        )
    elif cls is RSIStrategy:
        return cls(
            period=int(params.get("rsi_period", 14)),
            oversold=int(params.get("rsi_oversold", 30)),
            overbought=int(params.get("rsi_overbought", 70)),
        )
    else:
        return cls()


def sidebar_config():
    """Configure backtest parameters via sidebar."""
    st.sidebar.header("⚙️ Backtest Configuration")
    
    ticker = st.sidebar.text_input("📊 Ticker", value=DEFAULT_TICKER)
    start = st.sidebar.date_input("📅 Start date", pd.to_datetime(START_DATE)).isoformat()
    end = st.sidebar.date_input("📅 End date", pd.to_datetime(END_DATE)).isoformat()
    
    st.sidebar.markdown("---")
    
    # Strategy selection
    selected_strategies = st.sidebar.multiselect(
        "Select strategies",
        list(STRATEGIES.keys()),
        default=["SMA Crossover", "Buy & Hold"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Strategy Parameters")
    
    params_per_strategy = {}
    
    # SMA Crossover params
    if "SMA Crossover" in selected_strategies:
        st.sidebar.caption("**SMA Crossover**")
        params_per_strategy["SMA Crossover"] = {
            "sma_short": st.sidebar.slider("SMA short window", 5, 100, 20, key="sma_short"),
            "sma_long": st.sidebar.slider("SMA long window", 20, 300, 50, key="sma_long"),
        }
    
    # EMA Crossover params
    if "EMA Crossover" in selected_strategies:
        st.sidebar.caption("**EMA Crossover**")
        params_per_strategy["EMA Crossover"] = {
            "ema_short": st.sidebar.slider("EMA short window", 5, 100, 12, key="ema_short"),
            "ema_long": st.sidebar.slider("EMA long window", 20, 300, 26, key="ema_long"),
        }
    
    # Momentum params
    if "Momentum" in selected_strategies:
        st.sidebar.caption("**Momentum**")
        params_per_strategy["Momentum"] = {
            "mom_lookback": st.sidebar.slider("Lookback period", 2, 252, 20, key="mom_lookback"),
            "mom_threshold": st.sidebar.number_input(
                "Threshold (%)", value=0.0, step=0.001, key="mom_thr"
            ),
        }
    
    # RSI params
    if "RSI" in selected_strategies:
        st.sidebar.caption("**RSI**")
        params_per_strategy["RSI"] = {
            "rsi_period": st.sidebar.slider("RSI period", 5, 50, 14, key="rsi_period"),
            "rsi_oversold": st.sidebar.slider("Oversold level", 10, 40, 30, key="rsi_oversold"),
            "rsi_overbought": st.sidebar.slider("Overbought level", 60, 90, 70, key="rsi_overbought"),
        }
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("💰 Backtest Settings")
    
    capital = st.sidebar.number_input("Starting capital ($)", value=100000.0, step=1000.0)
    commission_per_trade = st.sidebar.number_input(
        "Commission per trade ($)", value=1.0, step=0.1, format="%.4f"
    )
    commission_pct = st.sidebar.number_input(
        "Commission (% per trade)", value=0.0005, step=0.0001, format="%.6f"
    )
    
    st.sidebar.markdown("---")
    run = st.sidebar.button("▶️ Run Backtest", use_container_width=True)
    
    return {
        "ticker": ticker,
        "start": start,
        "end": end,
        "selected_strategies": selected_strategies,
        "params_per_strategy": params_per_strategy,
        "capital": capital,
        "commission_per_trade": commission_per_trade,
        "commission_pct": commission_pct,
        "run": run,
    }


def display_metric_cards(metrics: dict, strategy_name: str):
    """Display key metrics in a card layout."""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    final_eq = metrics.get("final_equity", 0)
    total_ret = metrics.get("total_return", 0)
    total_ret_pct = metrics.get("total_return_pct", 0)
    cagr = metrics.get("cagr", metrics.get("approx_annual_return", 0))
    max_dd = metrics.get("max_drawdown", 0)
    
    col1.metric("Final Equity", f"${final_eq:,.0f}", delta=f"{total_ret_pct:.2%}", delta_color="inverse")
    col2.metric("Total Return", f"${total_ret:,.0f}")
    col3.metric("CAGR", f"{cagr:.2%}")
    col4.metric("Max Drawdown", f"{max_dd:.2%}", delta_color="inverse")
    col5.metric("Sharpe Ratio", f"{metrics.get('sharpe', 0):.2f}")


def display_comparison_table(results: dict):
    """Display metrics comparison table across all strategies."""
    st.subheader("📊 Strategy Comparison Table")
    
    comparison_data = []
    for name, res in results.items():
        m = res["metrics"]
        comparison_data.append({
            "Strategy": name,
            "Final Equity": f"${m.get('final_equity', 0):,.0f}",
            "Total Return": f"{m.get('total_return_pct', 0):.2%}",
            "CAGR": f"{m.get('cagr', m.get('approx_annual_return', 0)):.2%}",
            "Sharpe": f"{m.get('sharpe', 0):.2f}",
            "Max DD": f"{m.get('max_drawdown', 0):.2%}",
            "Volatility": f"{m.get('annualized_vol', 0):.2%}",
            "Trades": int(m.get("n_trades", 0)),
            "Commissions": f"${m.get('total_commission_paid', 0):,.2f}",
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)


def plot_equity_curves(results: dict):
    """Plot equity curves for all strategies."""
    st.subheader("📈 Equity Curves Comparison")
    
    fig = go.Figure()
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    
    for i, (name, res) in enumerate(results.items()):
        df_bt = res["df"]
        if "equity_curve" in df_bt.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_bt.index,
                    y=df_bt["equity_curve"],
                    mode="lines",
                    name=name,
                    line=dict(width=2, color=colors[i % len(colors)]),
                    hovertemplate="%{x|%Y-%m-%d}: $%{y:,.2f}<extra></extra>",
                )
            )
    
    fig.update_layout(
        height=450,
        title="Strategy Performance Over Time",
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=50),
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_returns_distribution(results: dict):
    """Plot daily returns distribution."""
    st.subheader("📊 Returns Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Cumulative Returns by Strategy**")
        fig_cum = go.Figure()
        
        for name, res in results.items():
            df_bt = res["df"]
            if "net_strategy_returns" in df_bt.columns:
                cumulative_returns = (1 + df_bt["net_strategy_returns"]).cumprod() - 1
                fig_cum.add_trace(
                    go.Scatter(
                        x=df_bt.index,
                        y=cumulative_returns * 100,
                        mode="lines",
                        name=name,
                        hovertemplate="%{x|%Y-%m-%d}: %{y:.2f}%<extra></extra>",
                    )
                )
        
        fig_cum.update_layout(
            height=350,
            yaxis_title="Cumulative Return (%)",
            hovermode="x unified",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig_cum, use_container_width=True)
    
    with col2:
        st.markdown("**Daily Returns Distribution (First Strategy)**")
        if results:
            first_strategy = list(results.values())[0]
            df_first = first_strategy["df"]
            
            if "net_strategy_returns" in df_first.columns:
                returns = df_first["net_strategy_returns"].dropna()
                fig_hist = px.histogram(
                    returns * 100,
                    nbins=60,
                    labels={"value": "Daily Return (%)", "count": "Frequency"},
                    title="",
                )
                fig_hist.update_layout(height=350, margin=dict(t=20, b=20))
                st.plotly_chart(fig_hist, use_container_width=True)


def plot_drawdowns(results: dict):
    """Plot drawdown charts for each strategy."""
    st.subheader("📉 Drawdown Analysis")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig_dd = go.Figure()
        
        for name, res in results.items():
            df_bt = res["df"]
            if "equity_curve" in df_bt.columns:
                running_max = df_bt["equity_curve"].cummax()
                drawdown = (df_bt["equity_curve"] - running_max) / running_max * 100
                fig_dd.add_trace(
                    go.Scatter(
                        x=df_bt.index,
                        y=drawdown,
                        mode="lines",
                        name=name,
                        fill="tozeroy",
                        hovertemplate="%{x|%Y-%m-%d}: %{y:.2f}%<extra></extra>",
                    )
                )
        
        fig_dd.update_layout(
            height=350,
            title="Drawdown Over Time",
            yaxis_title="Drawdown (%)",
            hovermode="x unified",
            margin=dict(t=30, b=20),
        )
        st.plotly_chart(fig_dd, use_container_width=True)
    
    with col1:
        st.markdown("**Max Drawdown Stats**")
        dd_stats = []
        for name, res in results.items():
            df_bt = res["df"]
            if "equity_curve" in df_bt.columns:
                running_max = df_bt["equity_curve"].cummax()
                drawdown = (df_bt["equity_curve"] - running_max) / running_max
                max_dd = drawdown.min()
                dd_duration = (drawdown < 0).sum()
                dd_stats.append({
                    "Strategy": name,
                    "Max DD": f"{max_dd:.2%}",
                    "Avg DD": f"{drawdown[drawdown < 0].mean():.2%}",
                    "Duration (days)": int(dd_duration),
                })
        
        if dd_stats:
            st.dataframe(pd.DataFrame(dd_stats), use_container_width=True, hide_index=True)


def plot_risk_metrics(results: dict):
    """Plot risk metrics comparison."""
    st.subheader("⚠️ Risk Metrics Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Volatility vs Sharpe**")
        risk_data = []
        for name, res in results.items():
            m = res["metrics"]
            risk_data.append({
                "Strategy": name,
                "Volatility": m.get("annualized_vol", 0),
                "Sharpe": m.get("sharpe", 0),
            })
        
        if risk_data:
            df_risk = pd.DataFrame(risk_data)
            fig_risk = px.scatter(
                df_risk,
                x="Volatility",
                y="Sharpe",
                hover_data={"Strategy": True},
                size_max=500,
                title="Risk-Return Profile",
            )
            fig_risk.update_traces(marker=dict(size=12))
            st.plotly_chart(fig_risk, use_container_width=True)
    
    with col2:
        st.markdown("**VaR & CVaR Comparison**")
        var_data = []
        for name, res in results.items():
            m = res["metrics"]
            var_data.append({
                "Strategy": name,
                "VaR 95%": m.get("VaR_95", 0) * 100,
                "CVaR 95%": m.get("CVaR_95", 0) * 100,
            })
        
        if var_data:
            df_var = pd.DataFrame(var_data)
            fig_var = go.Figure()
            
            fig_var.add_trace(
                go.Bar(name="VaR 95%", x=df_var["Strategy"], y=df_var["VaR 95%"])
            )
            fig_var.add_trace(
                go.Bar(name="CVaR 95%", x=df_var["Strategy"], y=df_var["CVaR 95%"])
            )
            
            fig_var.update_layout(
                barmode="group",
                title="Value at Risk Comparison",
                yaxis_title="Return (%)",
                height=350,
            )
            st.plotly_chart(fig_var, use_container_width=True)


def plot_trade_analysis(results: dict):
    """Display trade frequency and analysis."""
    st.subheader("🔄 Trade Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    trade_stats = []
    for name, res in results.items():
        m = res["metrics"]
        n_trades = int(m.get("n_trades", 0))
        total_comm = m.get("total_commission_paid", 0)
        avg_comm = total_comm / max(n_trades, 1)
        
        trade_stats.append({
            "Strategy": name,
            "Total Trades": n_trades,
            "Total Commissions": f"${total_comm:,.2f}",
            "Avg Commission/Trade": f"${avg_comm:,.2f}",
        })
    
    if trade_stats:
        df_trades = pd.DataFrame(trade_stats)
        st.dataframe(df_trades, use_container_width=True, hide_index=True)
    
    # Trade frequency chart
    with col1:
        st.markdown("**Trade Count**")
        trade_counts = [int(results[name]["metrics"].get("n_trades", 0)) for name in results.keys()]
        fig_trades = go.Figure(data=[
            go.Bar(x=list(results.keys()), y=trade_counts, marker_color="steelblue")
        ])
        fig_trades.update_layout(height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig_trades, use_container_width=True)
    
    with col2:
        st.markdown("**Commission Cost**")
        comm_costs = [results[name]["metrics"].get("total_commission_paid", 0) for name in results.keys()]
        fig_comm = go.Figure(data=[
            go.Bar(x=list(results.keys()), y=comm_costs, marker_color="coral")
        ])
        fig_comm.update_layout(height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig_comm, use_container_width=True)
    
    with col3:
        st.markdown("**Return per Trade**")
        ret_per_trade = []
        for name in results.keys():
            total_ret = results[name]["metrics"].get("total_return", 0)
            n_trades = max(int(results[name]["metrics"].get("n_trades", 0)), 1)
            ret_per_trade.append(total_ret / n_trades)
        
        fig_ret = go.Figure(data=[
            go.Bar(x=list(results.keys()), y=ret_per_trade, marker_color="lightgreen")
        ])
        fig_ret.update_layout(height=300, margin=dict(t=20, b=20))
        st.plotly_chart(fig_ret, use_container_width=True)


def main():
    st.title("🎯 Strategy Backtest — OpenOpt RiskEngine")
    st.markdown("*Comprehensive backtesting and strategy comparison*")
    st.markdown("---")
    
    config = sidebar_config()
    
    if not config["selected_strategies"]:
        st.info("👈 Select at least one strategy in the sidebar")
        return
    
    if config["run"]:
        with st.spinner(f"📊 Fetching {config['ticker']} data..."):
            try:
                df = cached_fetch(config["ticker"], config["start"], config["end"])
            except Exception as e:
                st.error(f"❌ Failed to fetch data: {e}")
                return
        
        st.success(f"✅ Data loaded: {len(df)} rows | {config['ticker']}")
        
        results = {}
        
        # Run backtests
        progress_bar = st.progress(0)
        total_strats = len(config["selected_strategies"])
        
        for idx, strategy_name in enumerate(config["selected_strategies"]):
            with st.spinner(f"🔄 Backtesting {strategy_name}..."):
                try:
                    strat = make_strategy(strategy_name, config["params_per_strategy"].get(strategy_name, {}))
                    df_signals = strat.generate_signals(df.copy())
                    df_bt, metrics = run_backtest(
                        df_signals,
                        capital=float(config["capital"]),
                        commission_per_trade=float(config["commission_per_trade"]),
                        commission_pct=float(config["commission_pct"]),
                    )
                    results[strategy_name] = {"df": df_bt, "metrics": metrics}
                except Exception as e:
                    st.error(f"❌ Backtest failed for {strategy_name}: {e}")
            
            progress_bar.progress((idx + 1) / total_strats)
        
        st.success(f"✅ Completed {len(results)} backtest(s)")
        st.markdown("---")
        
        # Display results
        if len(results) == 1:
            # Single strategy - detailed view
            strategy_name = list(results.keys())[0]
            st.subheader(f"📊 {strategy_name} Performance Metrics")
            display_metric_cards(results[strategy_name]["metrics"], strategy_name)
            st.markdown("---")
        else:
            # Multiple strategies - comparison view
            st.subheader("🏆 Strategy Comparison")
            display_comparison_table(results)
            st.markdown("---")
        
        # Performance charts
        plot_equity_curves(results)
        plot_returns_distribution(results)
        plot_drawdowns(results)
        plot_risk_metrics(results)
        plot_trade_analysis(results)
        
        # Detailed metrics
        with st.expander("📋 Full Metrics"):
            for name, res in results.items():
                st.markdown(f"### {name}")
                st.json(res["metrics"])
    
    else:
        st.info("👈 Configure parameters and click '▶️ Run Backtest' to begin analysis")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            ## Features:
            - **Multi-Strategy Comparison** — Run multiple strategies simultaneously
            - **Parameter Tuning** — Customize strategy windows and thresholds
            - **Cost Modeling** — Include transaction costs and slippage
            - **Risk Analysis** — VaR, CVaR, Sharpe ratio, max drawdown
            - **Trade Statistics** — Commission tracking and return per trade
            - **Performance Charts** — Equity curves, returns, drawdowns
            """)
        
        with col2:
            st.markdown("""
            ## Available Strategies:
            1. **SMA Crossover** — Simple moving average trend following
            2. **EMA Crossover** — Exponential moving average crossover
            3. **Momentum** — N-period price momentum strategy
            4. **RSI** — Relative strength index mean reversion
            5. **Buy & Hold** — Baseline passive strategy
            
            Customize each strategy's parameters in the sidebar!
            """)


if __name__ == "__main__":
    main()
