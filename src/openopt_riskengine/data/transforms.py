# OpenOpt-RiskEngine/src/openopt_riskengine/data/transforms.py

def normalize_data(data):
    """Normalize the input data to a range of [0, 1]."""
    min_val = data.min()
    max_val = data.max()
    return (data - min_val) / (max_val - min_val)

def log_transform(data):
    """Apply logarithmic transformation to the input data."""
    return np.log(data + 1e-9)  # Adding a small constant to avoid log(0)

def moving_average(data, window_size):
    """Calculate the moving average of the input data."""
    return data.rolling(window=window_size).mean()

def exponential_moving_average(data, span):
    """Calculate the exponential moving average of the input data."""
    return data.ewm(span=span, adjust=False).mean()

def difference(data, lag=1):
    """Calculate the difference of the input data."""
    return data.diff(lag)