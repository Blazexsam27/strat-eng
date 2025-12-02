def calculate_pnl(trades):
    total_pnl = sum(trade['profit_loss'] for trade in trades)
    return total_pnl

def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    excess_returns = [r - risk_free_rate for r in returns]
    mean_excess_return = sum(excess_returns) / len(excess_returns)
    return_std = (sum((r - mean_excess_return) ** 2 for r in excess_returns) / len(excess_returns)) ** 0.5
    if return_std == 0:
        return float('inf')
    return mean_excess_return / return_std

def calculate_drawdown(equity_curve):
    peak = equity_curve[0]
    max_drawdown = 0
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown

def calculate_metrics(trades, equity_curve, risk_free_rate=0.0):
    pnl = calculate_pnl(trades)
    returns = [trade['profit_loss'] / trade['entry_price'] for trade in trades]
    sharpe_ratio = calculate_sharpe_ratio(returns, risk_free_rate)
    max_drawdown = calculate_drawdown(equity_curve)
    
    return {
        'PnL': pnl,
        'Sharpe Ratio': sharpe_ratio,
        'Max Drawdown': max_drawdown
    }