"""
Black-Scholes-Merton Option Pricing Model
Calculates European option prices and associated Greeks.
"""

import numpy as np
from scipy.stats import norm


def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate d1 in the Black-Scholes formula.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility (annualized)

    Returns:
        d1 value
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    return (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))


def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate d2 in the Black-Scholes formula.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate
        sigma: Volatility (annualized)

    Returns:
        d2 value
    """
    if T <= 0 or sigma <= 0:
        return 0.0
    sigma_sqrt_t = sigma * np.sqrt(T)
    return d1(S, K, T, r, sigma) - sigma_sqrt_t


def call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate European call option price using Black-Scholes.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)

    Returns:
        Call option price
    """
    if T <= 0:
        return max(S - K, 0.0)
    if sigma <= 0:
        return max(S - K * np.exp(-r * T), 0.0)

    d_1 = d1(S, K, T, r, sigma)
    d_2 = d2(S, K, T, r, sigma)

    call = S * norm.cdf(d_1) - K * np.exp(-r * T) * norm.cdf(d_2)
    return max(call, 0.0)


def put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate European put option price using Black-Scholes.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)

    Returns:
        Put option price
    """
    if T <= 0:
        return max(K - S, 0.0)
    if sigma <= 0:
        return max(K * np.exp(-r * T) - S, 0.0)

    d_1 = d1(S, K, T, r, sigma)
    d_2 = d2(S, K, T, r, sigma)

    put = K * np.exp(-r * T) * norm.cdf(-d_2) - S * norm.cdf(-d_1)
    return max(put, 0.0)


def call_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate call option delta (∂C/∂S).
    Delta measures the rate of change of call price w.r.t. stock price.
    Range: [0, 1] for calls.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)

    Returns:
        Call delta
    """
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0

    d_1 = d1(S, K, T, r, sigma)
    return norm.cdf(d_1)


def put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate put option delta (∂P/∂S).
    Delta measures the rate of change of put price w.r.t. stock price.
    Range: [-1, 0] for puts.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)

    Returns:
        Put delta
    """
    if T <= 0 or sigma <= 0:
        return 0.0 if S > K else -1.0

    d_1 = d1(S, K, T, r, sigma)
    return norm.cdf(d_1) - 1.0


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate option gamma (∂²C/∂S²).
    Gamma measures the rate of change of delta w.r.t. stock price.
    Peak at-the-money. Same for calls and puts.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)

    Returns:
        Gamma (positive value)
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    d_1 = d1(S, K, T, r, sigma)
    return norm.pdf(d_1) / (S * sigma * np.sqrt(T))


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Calculate option vega (∂C/∂σ).
    Vega measures sensitivity to volatility changes.
    Same for calls and puts. 1 unit = 1% change in volatility.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)

    Returns:
        Vega (per 1% change in volatility)
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    d_1 = d1(S, K, T, r, sigma)
    return S * norm.pdf(d_1) * np.sqrt(T) / 100  # per 1% change in vol


def theta(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call"
) -> float:
    """
    Calculate option theta (∂C/∂T).
    Theta measures time decay. Usually negative for long options, positive for short.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)
        option_type: "call" or "put"

    Returns:
        Theta (per 1 day, typically)
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    d_1 = d1(S, K, T, r, sigma)
    d_2 = d2(S, K, T, r, sigma)

    if option_type == "call":
        theta_val = -S * norm.pdf(d_1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(
            -r * T
        ) * norm.cdf(d_2)
    else:  # put
        theta_val = -S * norm.pdf(d_1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(
            -r * T
        ) * norm.cdf(-d_2)

    # Convert to per-day theta (divide by 365)
    return theta_val / 365.0


def rho(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call"
) -> float:
    """
    Calculate option rho (∂C/∂r).
    Rho measures sensitivity to interest rate changes.
    Usually small impact on option prices.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)
        option_type: "call" or "put"

    Returns:
        Rho (per 1% change in interest rate)
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    d_2 = d2(S, K, T, r, sigma)

    if option_type == "call":
        rho_val = K * T * np.exp(-r * T) * norm.cdf(d_2) / 100
    else:  # put
        rho_val = -K * T * np.exp(-r * T) * norm.cdf(-d_2) / 100

    return rho_val


def lambda_greek(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call"
) -> float:
    """
    Calculate option lambda (elasticity or omega).
    Lambda measures percentage change in option price per 1% change in stock price.

    Parameters:
        S: Current stock price
        K: Strike price
        T: Time to expiration (in years)
        r: Risk-free interest rate (annual)
        sigma: Volatility (annualized)
        option_type: "call" or "put"

    Returns:
        Lambda elasticity
    """
    if option_type == "call":
        price = call_price(S, K, T, r, sigma)
        delta_val = call_delta(S, K, T, r, sigma)
    else:  # put
        price = put_price(S, K, T, r, sigma)
        delta_val = put_delta(S, K, T, r, sigma)

    if price <= 0:
        return 0.0

    return delta_val * S / price


class BlackScholesCalculator:
    """Convenience class for batch Greeks calculations."""

    def __init__(self, S: float, K: float, T: float, r: float, sigma: float):
        """
        Initialize calculator with option parameters.

        Parameters:
            S: Current stock price
            K: Strike price
            T: Time to expiration (in years)
            r: Risk-free interest rate
            sigma: Volatility (annualized)
        """
        self.S = S
        self.K = K
        self.T = T
        self.r = r
        self.sigma = sigma

    def call_greeks(self) -> dict:
        """Calculate all Greeks for a call option."""
        return {
            "price": call_price(self.S, self.K, self.T, self.r, self.sigma),
            "delta": call_delta(self.S, self.K, self.T, self.r, self.sigma),
            "gamma": gamma(self.S, self.K, self.T, self.r, self.sigma),
            "vega": vega(self.S, self.K, self.T, self.r, self.sigma),
            "theta": theta(self.S, self.K, self.T, self.r, self.sigma, "call"),
            "rho": rho(self.S, self.K, self.T, self.r, self.sigma, "call"),
            "lambda": lambda_greek(self.S, self.K, self.T, self.r, self.sigma, "call"),
        }

    def put_greeks(self) -> dict:
        """Calculate all Greeks for a put option."""
        return {
            "price": put_price(self.S, self.K, self.T, self.r, self.sigma),
            "delta": put_delta(self.S, self.K, self.T, self.r, self.sigma),
            "gamma": gamma(self.S, self.K, self.T, self.r, self.sigma),
            "vega": vega(self.S, self.K, self.T, self.r, self.sigma),
            "theta": theta(self.S, self.K, self.T, self.r, self.sigma, "put"),
            "rho": rho(self.S, self.K, self.T, self.r, self.sigma, "put"),
            "lambda": lambda_greek(self.S, self.K, self.T, self.r, self.sigma, "put"),
        }

    def call_value_sensitivity(self, S_range: np.ndarray) -> dict:
        """Calculate call price sensitivity across stock price range."""
        prices = [call_price(S, self.K, self.T, self.r, self.sigma) for S in S_range]
        deltas = [call_delta(S, self.K, self.T, self.r, self.sigma) for S in S_range]
        gammas = [gamma(S, self.K, self.T, self.r, self.sigma) for S in S_range]

        return {
            "S": S_range,
            "price": np.array(prices),
            "delta": np.array(deltas),
            "gamma": np.array(gammas),
        }

    def put_value_sensitivity(self, S_range: np.ndarray) -> dict:
        """Calculate put price sensitivity across stock price range."""
        prices = [put_price(S, self.K, self.T, self.r, self.sigma) for S in S_range]
        deltas = [put_delta(S, self.K, self.T, self.r, self.sigma) for S in S_range]
        gammas = [gamma(S, self.K, self.T, self.r, self.sigma) for S in S_range]

        return {
            "S": S_range,
            "price": np.array(prices),
            "delta": np.array(deltas),
            "gamma": np.array(gammas),
        }


# Test / example usage
if __name__ == "__main__":
    # Example: Call and put on GOOGL at $140 strike, 30 DTE, 5% rf rate, 25% vol
    S = 150  # Stock price
    K = 140  # Strike
    T = 30 / 365  # 30 days to expiration
    r = 0.05  # 5% risk-free rate
    sigma = 0.25  # 25% volatility

    calc = BlackScholesCalculator(S, K, T, r, sigma)

    print("CALL OPTION GREEKS:")
    call_greeks = calc.call_greeks()
    for greek, value in call_greeks.items():
        print(f"  {greek}: {value:.6f}")

    print("\nPUT OPTION GREEKS:")
    put_greeks = calc.put_greeks()
    for greek, value in put_greeks.items():
        print(f"  {greek}: {value:.6f}")
