from data.fetcher import fetch_price_data
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.buy_and_hold_strategy import BuyAndHoldStrategy
from strategies.ema_crossover import EMACrossoverStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.rsi_strategy import RSIStrategy
from backtesting.engine import run_backtest
from config import DEFAULT_TICKER, START_DATE, END_DATE


def main():
    df = fetch_price_data(DEFAULT_TICKER, START_DATE, END_DATE)

    strategies = [
        ("SMA Crossover", SMACrossoverStrategy(short_window=20, long_window=50)),
        ("Buy & Hold", BuyAndHoldStrategy()),
        ("EMA Crossover", EMACrossoverStrategy()),
        ("Momentum", MomentumStrategy()),
        ("RSI", RSIStrategy()),
    ]

    results = []
    for name, strat in strategies:
        df_signals = strat.generate_signals(df.copy())
        df_bt, metrics = run_backtest(
            df_signals, capital=100000, commission_per_trade=1.0, commission_pct=0.0005
        )
        results.append((name, metrics))

    # human-friendly summary table
    print(f"{'Strategy':<20} {'FinalEq':>12} {'TotRet%':>10} {'MaxDD%':>10} {'CAGR%':>8} {'Trades':>8}")
    for name, m in results:
        final = m.get("final_equity", 0.0)
        totr = m.get("total_return_pct", 0.0)
        maxdd = m.get("max_drawdown", 0.0)
        cagr = m.get("cagr", m.get("approx_annual_return", 0.0))
        ntrades = int(m.get("n_trades", 0))
        print(f"{name:<20} {final:12.2f} {totr:10.2%} {maxdd:10.2%} {cagr:8.2%} {ntrades:8d}")


if __name__ == "__main__":
    main()
