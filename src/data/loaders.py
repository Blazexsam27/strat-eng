from typing import Any, Dict
import pandas as pd

def load_data_from_csv(file_path: str) -> pd.DataFrame:
    """Load data from a CSV file."""
    return pd.read_csv(file_path)

def load_data_from_api(api_url: str, params: Dict[str, Any] = None) -> pd.DataFrame:
    """Load data from a financial API."""
    import requests
    response = requests.get(api_url, params=params)
    response.raise_for_status()
    return pd.DataFrame(response.json())

def load_data_from_database(connection_string: str, query: str) -> pd.DataFrame:
    """Load data from a database."""
    from sqlalchemy import create_engine
    engine = create_engine(connection_string)
    return pd.read_sql(query, engine)

def load_data(source: str, **kwargs) -> pd.DataFrame:
    """Load data from various sources."""
    if source == 'csv':
        return load_data_from_csv(kwargs['file_path'])
    elif source == 'api':
        return load_data_from_api(kwargs['api_url'], kwargs.get('params'))
    elif source == 'database':
        return load_data_from_database(kwargs['connection_string'], kwargs['query'])
    else:
        raise ValueError("Unsupported data source")