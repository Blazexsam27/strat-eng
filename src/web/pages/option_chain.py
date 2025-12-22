import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
import sys

project_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..."))
if project_src not in sys.path:
    sys.path.insert(0, project_src)

from config import DEFAULT_TICKER, START_DATE, END_DATE
from data.fetcher import fetch_price_data
from models.black_scholes import (
    call_price,
    put_price,
    call_delta,
    put_delta,
    gamma,
    vega,
    theta,
    rho,
)
import yfinance as yf

st.set_page_config(
    page_title="Option Chain — OpenOpt RiskEngine",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .option-call { background-color: #e8f5e9; padding: 10px; border-radius: 5px; }
    .option-put { background-color: #ffebee; padding: 10px; border-radius: 5px; }
    .greeks-card { background-color: #f5f5f5; padding: 15px; border-radius: 8px; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60 * 5)
def fetch_options_data(ticker: str):
    """Fetch options data from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        options_dates = stock.options
        return options_dates
    except Exception as e:
        st.error(f"Failed to fetch options data: {e}")
        return []


@st.cache_data(ttl=60 * 5)
def get_option_chain(ticker: str, expiration: str):
    """Get option chain for a specific expiration date."""
    try:
        stock = yf.Ticker(ticker)
        chain = stock.option_chain(expiration)
        return chain.calls, chain.puts
    except Exception as e:
        st.error(f"Failed to fetch option chain: {e}")
        return None, None


def calculate_implied_volatility(
    option_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
):
    """Approximate implied volatility using binary search."""
    from scipy.optimize import brentq

    def objective(sigma):
        if option_type == "call":
            return call_price(S, K, T, r, sigma) - option_price
        else:
            return put_price(S, K, T, r, sigma) - option_price

    try:
        # bound the search to reasonable volatility range
        iv = brentq(objective, 0.001, 5.0, maxiter=100)
        return iv
    except:
        return np.nan


def sidebar_config():
    st.sidebar.header("⚙️ Option Chain Config")
    ticker = st.sidebar.text_input("📊 Ticker", value=DEFAULT_TICKER)

    # Fetch current price
    try:
        data = yf.download(ticker, period="1d", progress=False)
        spot_price = float(data["Close"].iloc[-1])
    except:
        spot_price = 100.0

    st.sidebar.metric("Current Price", f"${spot_price:.2f}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Options Parameters")

    # Risk-free rate
    risk_free_rate = st.sidebar.slider("Risk-free Rate (%)", 0.0, 10.0, 5.0) / 100

    # Expiration date
    try:
        options_dates = fetch_options_data(ticker)
        if options_dates:
            selected_exp = st.sidebar.selectbox("Expiration Date", options_dates[:10])
        else:
            selected_exp = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    except:
        selected_exp = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Greeks & Pricing")

    # Custom strikes option
    show_custom_strikes = st.sidebar.checkbox("Use Custom Strikes", value=False)
    if show_custom_strikes:
        strike_min = st.sidebar.number_input(
            "Min Strike", value=spot_price * 0.8, step=1.0
        )
        strike_max = st.sidebar.number_input(
            "Max Strike", value=spot_price * 1.2, step=1.0
        )
    else:
        strike_min = spot_price * 0.85
        strike_max = spot_price * 1.15

    st.sidebar.markdown("---")
    fetch = st.sidebar.button("📊 Load Option Chain", use_container_width=True)

    return {
        "ticker": ticker,
        "spot_price": spot_price,
        "expiration": selected_exp,
        "risk_free_rate": risk_free_rate,
        "strike_min": strike_min,
        "strike_max": strike_max,
        "fetch": fetch,
    }


def display_option_chain(ticker: str, expiration: str, spot_price: float, r: float):
    """Display option chain data with Greeks."""
    calls, puts = get_option_chain(ticker, expiration)

    if calls is None or puts is None:
        st.warning("Unable to load option chain data")
        return

    # Calculate days to expiration
    exp_date = pd.to_datetime(expiration)
    today = pd.to_datetime(datetime.now().date())
    dte = (exp_date - today).days / 365.0

    st.subheader(f"📊 Option Chain — {ticker} @ ${spot_price:.2f}")
    st.caption(f"Expiration: {expiration} ({(exp_date - today).days} DTE)")

    # Display calls and puts side by side
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📈 CALLS (Long Bullish)")
        calls_display = calls[calls["strike"] > 0].copy()
        calls_display["IV"] = calls_display.apply(
            lambda row: calculate_implied_volatility(
                row["lastPrice"], spot_price, row["strike"], dte, r, "call"
            ),
            axis=1,
        )
        calls_display["Delta"] = calls_display.apply(
            lambda row: call_delta(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
            ),
            axis=1,
        )
        calls_display["Gamma"] = calls_display.apply(
            lambda row: gamma(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
            ),
            axis=1,
        )
        calls_display["Theta"] = calls_display.apply(
            lambda row: theta(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
                "call",
            ),
            axis=1,
        )
        calls_display["Vega"] = calls_display.apply(
            lambda row: vega(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
            ),
            axis=1,
        )

        calls_cols = [
            "strike",
            "lastPrice",
            "bid",
            "ask",
            "volume",
            "openInterest",
            "IV",
            "Delta",
            "Gamma",
            "Theta",
            "Vega",
        ]
        calls_display_subset = calls_display[calls_cols].dropna(
            subset=["strike", "lastPrice"]
        )

        st.dataframe(
            calls_display_subset.style.format(
                {
                    "strike": "${:.2f}",
                    "lastPrice": "${:.4f}",
                    "bid": "${:.4f}",
                    "ask": "${:.4f}",
                    "IV": "{:.2%}",
                    "Delta": "{:.4f}",
                    "Gamma": "{:.6f}",
                    "Theta": "{:.6f}",
                    "Vega": "{:.6f}",
                }
            ),
            use_container_width=True,
        )

    with col2:
        st.markdown("### 📉 PUTS (Long Bearish)")
        puts_display = puts[puts["strike"] > 0].copy()
        puts_display["IV"] = puts_display.apply(
            lambda row: calculate_implied_volatility(
                row["lastPrice"], spot_price, row["strike"], dte, r, "put"
            ),
            axis=1,
        )
        puts_display["Delta"] = puts_display.apply(
            lambda row: put_delta(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
            ),
            axis=1,
        )
        puts_display["Gamma"] = puts_display.apply(
            lambda row: gamma(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
            ),
            axis=1,
        )
        puts_display["Theta"] = puts_display.apply(
            lambda row: theta(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
                "put",
            ),
            axis=1,
        )
        puts_display["Vega"] = puts_display.apply(
            lambda row: vega(
                spot_price,
                row["strike"],
                dte,
                r,
                row["IV"] if not np.isnan(row["IV"]) else 0.2,
            ),
            axis=1,
        )

        puts_cols = [
            "strike",
            "lastPrice",
            "bid",
            "ask",
            "volume",
            "openInterest",
            "IV",
            "Delta",
            "Gamma",
            "Theta",
            "Vega",
        ]
        puts_display_subset = puts_display[puts_cols].dropna(
            subset=["strike", "lastPrice"]
        )

        st.dataframe(
            puts_display_subset.style.format(
                {
                    "strike": "${:.2f}",
                    "lastPrice": "${:.4f}",
                    "bid": "${:.4f}",
                    "ask": "${:.4f}",
                    "IV": "{:.2%}",
                    "Delta": "{:.4f}",
                    "Gamma": "{:.6f}",
                    "Theta": "{:.6f}",
                    "Vega": "{:.6f}",
                }
            ),
            use_container_width=True,
        )

    return calls_display, puts_display


def display_greeks_visualization(
    calls: pd.DataFrame, puts: pd.DataFrame, spot_price: float
):
    """Visualize Greeks across strike prices."""
    st.subheader("📈 Greeks Visualization")

    col1, col2 = st.columns(2)

    with col1:
        # Delta by strike
        if "strike" in calls.columns and "Delta" in calls.columns:
            fig_delta = go.Figure()
            fig_delta.add_trace(
                go.Scatter(
                    x=calls["strike"],
                    y=calls["Delta"],
                    mode="lines+markers",
                    name="Call Delta",
                    line=dict(color="green"),
                )
            )
            fig_delta.add_trace(
                go.Scatter(
                    x=puts["strike"],
                    y=puts["Delta"],
                    mode="lines+markers",
                    name="Put Delta",
                    line=dict(color="red"),
                )
            )
            fig_delta.add_vline(
                x=spot_price,
                line_dash="dash",
                line_color="black",
                annotation_text="Spot",
            )
            fig_delta.update_layout(
                title="Delta by Strike",
                xaxis_title="Strike",
                yaxis_title="Delta",
                height=400,
                hovermode="x unified",
            )
            st.plotly_chart(fig_delta, use_container_width=True)

    with col2:
        # Gamma by strike
        if "strike" in calls.columns and "Gamma" in calls.columns:
            fig_gamma = go.Figure()
            fig_gamma.add_trace(
                go.Scatter(
                    x=calls["strike"],
                    y=calls["Gamma"],
                    mode="lines+markers",
                    name="Call Gamma",
                    line=dict(color="green"),
                )
            )
            fig_gamma.add_trace(
                go.Scatter(
                    x=puts["strike"],
                    y=puts["Gamma"],
                    mode="lines+markers",
                    name="Put Gamma",
                    line=dict(color="red"),
                )
            )
            fig_gamma.add_vline(
                x=spot_price,
                line_dash="dash",
                line_color="black",
                annotation_text="Spot",
            )
            fig_gamma.update_layout(
                title="Gamma by Strike",
                xaxis_title="Strike",
                yaxis_title="Gamma",
                height=400,
                hovermode="x unified",
            )
            st.plotly_chart(fig_gamma, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        # Theta by strike
        if "strike" in calls.columns and "Theta" in calls.columns:
            fig_theta = go.Figure()
            fig_theta.add_trace(
                go.Scatter(
                    x=calls["strike"],
                    y=calls["Theta"],
                    mode="lines+markers",
                    name="Call Theta",
                    line=dict(color="green"),
                )
            )
            fig_theta.add_trace(
                go.Scatter(
                    x=puts["strike"],
                    y=puts["Theta"],
                    mode="lines+markers",
                    name="Put Theta",
                    line=dict(color="red"),
                )
            )
            fig_theta.add_vline(
                x=spot_price,
                line_dash="dash",
                line_color="black",
                annotation_text="Spot",
            )
            fig_theta.update_layout(
                title="Theta by Strike (Decay per day)",
                xaxis_title="Strike",
                yaxis_title="Theta",
                height=400,
                hovermode="x unified",
            )
            st.plotly_chart(fig_theta, use_container_width=True)

    with col4:
        # Vega by strike
        if "strike" in calls.columns and "Vega" in calls.columns:
            fig_vega = go.Figure()
            fig_vega.add_trace(
                go.Scatter(
                    x=calls["strike"],
                    y=calls["Vega"],
                    mode="lines+markers",
                    name="Call Vega",
                    line=dict(color="green"),
                )
            )
            fig_vega.add_trace(
                go.Scatter(
                    x=puts["strike"],
                    y=puts["Vega"],
                    mode="lines+markers",
                    name="Put Vega",
                    line=dict(color="red"),
                )
            )
            fig_vega.add_vline(
                x=spot_price,
                line_dash="dash",
                line_color="black",
                annotation_text="Spot",
            )
            fig_vega.update_layout(
                title="Vega by Strike (IV Sensitivity)",
                xaxis_title="Strike",
                yaxis_title="Vega",
                height=400,
                hovermode="x unified",
            )
            st.plotly_chart(fig_vega, use_container_width=True)


def display_iv_smile(calls: pd.DataFrame, puts: pd.DataFrame, spot_price: float):
    """Display implied volatility smile."""
    st.subheader("😊 Implied Volatility Smile")

    fig_smile = go.Figure()

    if "IV" in calls.columns and "strike" in calls.columns:
        calls_clean = calls.dropna(subset=["IV", "strike"])
        fig_smile.add_trace(
            go.Scatter(
                x=calls_clean["strike"],
                y=calls_clean["IV"] * 100,
                mode="lines+markers",
                name="Call IV",
                line=dict(color="green"),
            )
        )

    if "IV" in puts.columns and "strike" in puts.columns:
        puts_clean = puts.dropna(subset=["IV", "strike"])
        fig_smile.add_trace(
            go.Scatter(
                x=puts_clean["strike"],
                y=puts_clean["IV"] * 100,
                mode="lines+markers",
                name="Put IV",
                line=dict(color="red"),
            )
        )

    fig_smile.add_vline(
        x=spot_price, line_dash="dash", line_color="black", annotation_text="ATM"
    )
    fig_smile.update_layout(
        title="Implied Volatility Smile",
        xaxis_title="Strike",
        yaxis_title="Implied Volatility (%)",
        height=400,
        hovermode="x unified",
    )
    st.plotly_chart(fig_smile, use_container_width=True)


def main():
    st.title("🎯 Option Chain — OpenOpt RiskEngine")
    st.markdown(
        "*Options pricing, Greeks analysis, and volatility surface visualization*"
    )
    st.markdown("---")

    config = sidebar_config()

    if config["fetch"]:
        with st.spinner(f"📊 Loading option chain for {config['ticker']}..."):
            calls, puts = display_option_chain(
                config["ticker"],
                config["expiration"],
                config["spot_price"],
                config["risk_free_rate"],
            )

            if calls is not None and puts is not None:
                st.success("✅ Option chain loaded successfully")

                # Greeks visualization
                display_greeks_visualization(calls, puts, config["spot_price"])

                # IV Smile
                display_iv_smile(calls, puts, config["spot_price"])

                # Greeks explanation
                with st.expander("📚 Greeks Explained"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(
                            """
                        **Delta (Δ):** Rate of change of option price w.r.t. stock price. Range: [0,1] for calls, [-1,0] for puts.
                        
                        **Gamma (Γ):** Rate of change of delta. Peak at-the-money. Measures convexity risk.
                        
                        **Vega (ν):** Sensitivity to volatility changes. Positive for both calls and puts.
                        """
                        )
                    with col2:
                        st.markdown(
                            """
                        **Theta (Θ):** Time decay (per day). Usually negative for long options, positive for short.
                        
                        **Rho (ρ):** Sensitivity to interest rate changes. Usually small impact.
                        
                        **IV (σ):** Implied Volatility — market's expectation of future volatility.
                        """
                        )

    else:
        st.info(
            "👈 Configure ticker and expiration date in the sidebar, then click '📊 Load Option Chain'"
        )
        st.markdown(
            """
        ## Option Chain Analysis Features:

        - **Live Option Chain Data:** Real-time calls and puts with bid/ask spreads
        - **Greeks Calculation:** Delta, Gamma, Theta, Vega, Rho across strikes
        - **Implied Volatility:** Extracted from market prices via binary search
        - **Greeks Surface:** Visualize Greeks behavior across strike prices
        - **IV Smile:** Volatility surface curvature analysis
        - **Price Moneyness:** Filter by custom strike ranges

        Use this page to analyze option opportunities and manage Greeks exposure.
        """
        )


if __name__ == "__main__":
    main()
