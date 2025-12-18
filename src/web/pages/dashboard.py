import io
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import os
import sys

project_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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


# ---- caching ----
@st.cache_data(ttl=60 * 60)
def cached_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    return fetch_price_data(ticker, start, end)


# ---- strategy factory with params ----
STRATEGIES = {
    "SMA Crossover": SMACrossoverStrategy,
    "EMA Crossover": EMACrossoverStrategy,
    "Momentum": MomentumStrategy,
    "RSI": RSIStrategy,
    "Buy & Hold": BuyAndHoldStrategy,
}


def make_strategy(name: str, params: dict):
    cls = STRATEGIES.get(name)
    if cls is SMACrossoverStrategy:
        return cls(
            short_window=int(params.get("sma_short", 20)),
            long_window=int(params.get("sma_long", 50)),
        )
    if cls is EMACrossoverStrategy:
        return cls(
            short_window=int(params.get("ema_short", 12)),
            long_window=int(params.get("ema_long", 26)),
        )
    if cls is MomentumStrategy:
        return cls(
            lookback=int(params.get("mom_lookback", 20)),
            threshold=float(params.get("mom_threshold", 0.0)),
        )
    if cls is RSIStrategy:
        return cls(
            period=int(params.get("rsi_period", 14)),
            oversold=int(params.get("rsi_oversold", 30)),
            overbought=int(params.get("rsi_overbought", 70)),
        )
    return cls()


# ---- sidebar inputs ----
def sidebar():
    st.sidebar.title("Data & Strategy")
    ticker = st.sidebar.text_input("Ticker", value=DEFAULT_TICKER)
    start = st.sidebar.date_input("Start", pd.to_datetime(START_DATE))
    end = st.sidebar.date_input("End", pd.to_datetime(END_DATE))

    st.sidebar.markdown("---")
    selected = st.sidebar.multiselect(
        "Select strategies to run",
        list(STRATEGIES.keys()),
        default=["SMA Crossover", "Buy & Hold"],
    )

    # per-strategy param groups
    params = {}
    st.sidebar.markdown("Strategy parameters")
    if "SMA Crossover" in selected:
        st.sidebar.caption("SMA")
        params["SMA Crossover"] = {
            "sma_short": st.sidebar.slider("SMA short", 5, 100, 20, key="sma_short"),
            "sma_long": st.sidebar.slider("SMA long", 10, 300, 50, key="sma_long"),
        }
    if "EMA Crossover" in selected:
        params["EMA Crossover"] = {
            "ema_short": st.sidebar.slider("EMA short", 5, 100, 12, key="ema_short"),
            "ema_long": st.sidebar.slider("EMA long", 10, 300, 26, key="ema_long"),
        }
    if "Momentum" in selected:
        params["Momentum"] = {
            "mom_lookback": st.sidebar.slider(
                "Momentum lookback", 2, 252, 20, key="mom_lookback"
            ),
            "mom_threshold": float(
                st.sidebar.number_input(
                    "Momentum threshold (pct)", value=0.0, step=0.001, key="mom_thr"
                )
            ),
        }
    if "RSI" in selected:
        params["RSI"] = {
            "rsi_period": st.sidebar.slider("RSI period", 5, 50, 14, key="rsi_period"),
            "rsi_oversold": st.sidebar.slider(
                "RSI oversold", 10, 40, 30, key="rsi_oversold"
            ),
            "rsi_overbought": st.sidebar.slider(
                "RSI overbought", 60, 90, 70, key="rsi_overbought"
            ),
        }

    st.sidebar.markdown("---")
    capital = st.sidebar.number_input("Starting capital", value=100000.0, step=1000.0)
    commission_per_trade = st.sidebar.number_input(
        "Commission per trade (USD)", value=1.0, step=0.1, format="%.4f"
    )
    commission_pct = st.sidebar.number_input(
        "Commission % (proportional)", value=0.0005, step=0.0001, format="%.6f"
    )
    run = st.sidebar.button("Run")
    return dict(
        ticker=ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        selected=selected,
        params=params,
        capital=capital,
        commission_per_trade=commission_per_trade,
        commission_pct=commission_pct,
        run=run,
    )


# ---- helpers for downloads & tables ----
def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    b = io.BytesIO()
    df.to_csv(b, index=True)
    return b.getvalue()


def metrics_to_json_bytes(metrics: dict) -> bytes:
    return json.dumps(metrics, indent=2, default=str).encode()


# ---- main UI ----
def main():
    st.title("OpenOpt RiskEngine — Interactive Dashboard")
    st.markdown(
        "Modern dashboard for strategy exploration — compare strategies, tweak parameters and inspect behavior."
    )

    ui = sidebar()
    if not ui["selected"]:
        st.info("Select at least one strategy in the sidebar.")
        return

    if ui["run"]:
        with st.spinner("Fetching data..."):
            try:
                df = cached_fetch(ui["ticker"], ui["start"], ui["end"])
            except Exception as e:
                st.error(f"Failed to fetch data: {e}")
                return

        st.success(f"Fetched {len(df)} rows for {ui['ticker']}")

        results = {}
        equity_df = pd.DataFrame(index=df.index)

        for name in ui["selected"]:
            strat = make_strategy(name, ui["params"].get(name, {}))
            try:
                df_signals = strat.generate_signals(df.copy())
            except Exception as e:
                st.error(f"Signal generation failed for {name}: {e}")
                continue

            try:
                df_bt, metrics = run_backtest(
                    df_signals,
                    capital=float(ui["capital"]),
                    commission_per_trade=float(ui["commission_per_trade"]),
                    commission_pct=float(ui["commission_pct"]),
                )
            except Exception as e:
                st.error(f"Backtest failed for {name}: {e}")
                continue

            results[name] = {"df": df_bt, "metrics": metrics}
            equity_df[name] = df_bt["equity_curve"]

        # ---- metrics header (cards) ----
        st.subheader("Performance snapshot")
        metric_cols = st.columns(len(results) if len(results) <= 4 else 4)
        # show up to 4 strategies with compact metrics
        for i, (name, res) in enumerate(results.items()):
            if i >= len(metric_cols):
                break
            col = metric_cols[i]
            m = res["metrics"]
            col.metric(
                label=f"{name} — Final Equity",
                value=f"${m.get('final_equity', 0):,.0f}",
                delta=f"{m.get('total_return_pct', 0):.2%}",
            )
            col.write(
                f"CAGR: {m.get('cagr', m.get('approx_annual_return', 0)):.2%}  |  MaxDD: {m.get('max_drawdown', 0):.2%}"
            )
            col.write(
                f"Trades: {int(m.get('n_trades', 0))}  |  Comms: ${m.get('total_commission_paid', 0):,.2f}"
            )

        # ---- main charts ----
        st.subheader("Equity curves")
        if not equity_df.empty:
            fig = go.Figure()
            print("EQUITY----------------------->", equity_df.head())
            for col in equity_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=equity_df.index,
                        y=equity_df[col],
                        mode="lines",
                        name=col,
                        hovertemplate="%{x|%Y-%m-%d}: $%{y:,.2f}",
                    )
                )
            fig.update_layout(
                legend=dict(orientation="h"), height=420, margin=dict(t=30, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

        # Price + indicators (for first selected strategy df)
        # flatten MultiIndex columns

        first_name = next(iter(results.keys()))
        df_first = results[first_name]["df"]

        df_first_copy = df_first.copy()

        df_first_copy.columns = [
            col[0] if col[1] == "" else f"{col[0]}_{col[1]}"
            for col in df_first_copy.columns
        ]
        # st.subheader(f"Price and indicators — {first_name}")
        print("Df----------------------->", df_first_copy.columns)
        # print("Df----------------------->", df_first.head())
        # price_fig = go.Figure()
        # price_fig.add_trace(
        #     go.Scatter(
        #         x=df_first.index,
        #         y=df_first["Close"],
        #         name="Close",
        #         line=dict(color="#222222"),
        #     )
        # )

        price_fig = go.Figure()

        price_fig.add_trace(
            go.Scatter(
                x=df_first_copy.index,
                y=df_first_copy["Close_NVDA"],
                name="Close",
                line=dict(color="#222222"),
            )
        )

        price_fig.add_trace(
            go.Scatter(
                x=df_first_copy.index,
                y=df_first_copy["SMA_20"],
                name="SMA 20",
                line=dict(color="blue"),
            )
        )

        price_fig.add_trace(
            go.Scatter(
                x=df_first_copy.index,
                y=df_first_copy["SMA_50"],
                name="SMA 50",
                line=dict(color="red"),
            )
        )

        # handle both simple string columns and MultiIndex tuples
        for c in df_first_copy.columns:
            col_str = str(c)  # convert tuple to string if needed
            if "SMA_" in col_str or "EMA_" in col_str:
                price_fig.add_trace(
                    go.Scatter(
                        x=df_first_copy.index,
                        y=df_first_copy[c],
                        name=col_str,
                        line=dict(dash="dot"),
                    )
                )
        price_fig.update_layout(height=350, margin=dict(t=10, b=10))
        st.plotly_chart(price_fig, use_container_width=True)

        # Return distribution + drawdown
        st.subheader("Return distribution & Drawdown")
        r1, r2 = st.columns([2, 1])
        net_returns_list = []
        for name, res in results.items():
            if "net_strategy_returns" in res["df"].columns:
                net_returns_list.append(
                    res["df"]["net_strategy_returns"].dropna().rename(name)
                )
        if net_returns_list:
            net_returns = pd.concat(net_returns_list)
            # histogram for the last selected strategy
            last = list(results.values())[-1]["df"]
            fig_hist = px.histogram(
                last["net_strategy_returns"].dropna(),
                nbins=60,
                title="Return distribution (last strategy)",
            )
            r1.plotly_chart(fig_hist, use_container_width=True)
        else:
            r1.info("No returns available to plot.")

        # drawdown plot for first strategy
        dd = results[first_name]["df"].copy()
        running_max = dd["equity_curve"].cummax()
        dd["drawdown"] = (dd["equity_curve"] - running_max) / running_max

        # flatten MultiIndex columns to single-level strings for plotly express
        if isinstance(dd.columns, pd.MultiIndex):
            dd.columns = [
                f"{col[0]}_{col[1]}" if col[1] else col[0] for col in dd.columns
            ]

        dd_reset = dd.reset_index()
        # after reset_index(), the index becomes a column named "Date" (or whatever the index name is)
        index_col_name = dd_reset.columns[
            0
        ]  # first column after reset is the old index

        fig_dd = px.area(
            dd_reset,
            x=index_col_name,
            y="drawdown",
            title=f"Drawdown — {first_name}",
            labels={"drawdown": "Drawdown"},
        )
        r2.plotly_chart(fig_dd, use_container_width=True)

        # Trades table and downloads
        st.subheader("Trades & Data")
        tab1, tab2 = st.tabs(["Trades", "Download"])
        with tab1:
            # combine trade events across strategies
            trade_frames = []
            for name, res in results.items():
                df_t = res["df"]
                if "trade_event" in df_t.columns and df_t["trade_event"].sum() > 0:
                    tf = df_t[df_t["trade_event"] > 0][
                        ["Close", "trade_event", "trade_cost"]
                    ].copy()
                    tf["strategy"] = name
                    trade_frames.append(tf)
            if trade_frames:
                trades_all = pd.concat(trade_frames).sort_index()
                st.dataframe(trades_all.head(200))
            else:
                st.info("No trade events to show.")

        with tab2:
            # download metrics and equity csv
            for name, res in results.items():
                st.markdown(f"**{name}**")
                df_bytes = df_to_csv_bytes(res["df"])
                st.download_button(
                    label=f"Download {name} dataframe (CSV)",
                    data=df_bytes,
                    file_name=f"{name.replace(' ','_')}_results.csv",
                    mime="text/csv",
                )
                st.download_button(
                    label=f"Download {name} metrics (JSON)",
                    data=metrics_to_json_bytes(res["metrics"]),
                    file_name=f"{name.replace(' ','_')}_metrics.json",
                    mime="application/json",
                )

        # raw metrics
        st.subheader("Metrics (raw)")
        st.json({k: v["metrics"] for k, v in results.items()})

    else:
        st.info("Configure parameters and press Run in the sidebar.")


if __name__ == "__main__":
    main()
