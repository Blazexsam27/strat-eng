import numpy as np


def value_at_risk(returns, confidence_level=0.95):
    """
    Calculate the Value at Risk (VaR) for a given set of returns.

    Parameters:
    returns (list or np.array): Array of returns.
    confidence_level (float): Confidence level for VaR (default is 0.95).

    Returns:
    float: The VaR at the specified confidence level.
    """
    if not isinstance(returns, (list, np.ndarray)):
        raise ValueError("Returns should be a list or numpy array.")

    if len(returns) == 0:
        raise ValueError("Returns array cannot be empty.")

    return -np.percentile(returns, (1 - confidence_level) * 100)


def conditional_value_at_risk(returns, confidence_level=0.95):
    """
    Calculate the Conditional Value at Risk (CVaR) for a given set of returns.

    Parameters:
    returns (list or np.array): Array of returns.
    confidence_level (float): Confidence level for CVaR (default is 0.95).

    Returns:
    float: The CVaR at the specified confidence level.
    """
    if not isinstance(returns, (list, np.ndarray)):
        raise ValueError("Returns should be a list or numpy array.")

    if len(returns) == 0:
        raise ValueError("Returns array cannot be empty.")

    var = value_at_risk(returns, confidence_level)
    return -returns[returns <= -var].mean() if np.any(returns <= -var) else 0.0


def expected_shortfall(returns, confidence_level=0.95):
    """
    Calculate the Expected Shortfall (ES) for a given set of returns.

    Parameters:
    returns (list or np.array): Array of returns.
    confidence_level (float): Confidence level for ES (default is 0.95).

    Returns:
    float: The Expected Shortfall at the specified confidence level.
    """
    return conditional_value_at_risk(returns, confidence_level)
