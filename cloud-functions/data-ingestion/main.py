import functions_framework
from google.cloud import bigquery
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
PROJECT_ID = os.environ.get("GCP_PROJECT")
DATASET_ID = os.environ.get("BIGQUERY_DATASET")
TABLE_ID = "stock_prices"

# Default symbols if not provided
DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]


@functions_framework.http
def ingest_stock_data(request):
    """
    HTTP Cloud Function to ingest stock data into BigQuery.

    Request body (JSON):
    {
        "symbols": ["SPY", "AAPL"],  # Optional, defaults to DEFAULT_SYMBOLS
        "lookback_days": 7            # Optional, defaults to 7
    }
    """
    try:
        # Parse request
        request_json = request.get_json(silent=True)

        if request_json:
            symbols = request_json.get("symbols", DEFAULT_SYMBOLS)
            lookback_days = request_json.get("lookback_days", 7)
        else:
            symbols = DEFAULT_SYMBOLS
            lookback_days = 7

        logger.info(f"Starting data ingestion for {len(symbols)} symbols")
        logger.info(f"Symbols: {symbols}")
        logger.info(f"Lookback period: {lookback_days} days")

        if not PROJECT_ID or not DATASET_ID:
            return {
                "status": "error",
                "message": "Missing environment variables: GCP_PROJECT or BIGQUERY_DATASET",
            }, 500

        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
        logger.info(f"Target table: {table_ref}")

        # Initialize BigQuery client
        client = bigquery.Client(project=PROJECT_ID)

        all_data = []
        errors = []
        success_count = 0

        # Fetch data for each symbol
        for symbol in symbols:
            try:
                logger.info(f"Fetching data for {symbol}...")

                # Download data from yfinance
                end_date = datetime.now()
                start_date = end_date - timedelta(days=lookback_days)

                logger.info(
                    f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                )

                # Use Ticker object for more reliable single-symbol fetching
                ticker = yf.Ticker(symbol)
                df = ticker.history(
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                )

                if df.empty:
                    logger.warning(f"No data retrieved for {symbol}")
                    continue

                # Debug: Log available columns
                logger.info(f"DataFrame columns for {symbol}: {df.columns.tolist()}")
                logger.info(f"DataFrame shape for {symbol}: {df.shape}")
                logger.info(f"DataFrame index type: {type(df.index)}")

                # Prepare data for BigQuery
                df = df.reset_index()  # Move Date from index to column

                logger.info(f"After reset_index - columns: {df.columns.tolist()}")

                df["symbol"] = symbol
                df["inserted_at"] = datetime.utcnow()

                # Create a mapping dictionary for available columns
                column_mapping = {}

                # Handle date column (could be 'Date' or 'date' depending on yfinance version)
                if "Date" in df.columns:
                    column_mapping["Date"] = "date"
                elif "index" in df.columns:
                    column_mapping["index"] = "date"

                # Map all available price columns
                for col in ["Open", "High", "Low", "Close", "Adj Close", "Volume"]:
                    if col in df.columns:
                        # Convert column names: 'Adj Close' -> 'adj_close', 'Close' -> 'close', etc.
                        new_name = col.lower().replace(" ", "_")
                        column_mapping[col] = new_name

                # Rename available columns
                df = df.rename(columns=column_mapping)

                logger.info(f"After rename - columns: {df.columns.tolist()}")

                # Handle missing 'adj_close' column
                if "adj_close" not in df.columns:
                    if "close" in df.columns:
                        # Use 'close' as a fallback for 'adj_close'
                        df["adj_close"] = df["close"]
                        logger.warning(
                            f"No 'Adj Close' column for {symbol}, using 'close' as fallback"
                        )
                    else:
                        # If neither exists, create a placeholder
                        df["adj_close"] = 0.0
                        logger.error(f"No price columns found for {symbol}")

                # Ensure all required columns exist with default values
                for col, default_value in [
                    ("open", 0.0),
                    ("high", 0.0),
                    ("low", 0.0),
                    ("close", 0.0),
                    ("adj_close", 0.0),
                    ("volume", 0),
                ]:
                    if col not in df.columns:
                        df[col] = default_value
                        logger.warning(
                            f"Missing column {col} for {symbol}, using default {default_value}"
                        )

                # Select only required columns (in correct order)
                df = df[
                    [
                        "symbol",
                        "date",
                        "open",
                        "high",
                        "low",
                        "close",
                        "adj_close",
                        "volume",
                        "inserted_at",
                    ]
                ]

                # Convert date to proper format for BigQuery
                # Handle various date types that might come from yfinance
                try:
                    if pd.api.types.is_datetime64_any_dtype(df["date"]):
                        df["date"] = df["date"].dt.date
                    else:
                        df["date"] = pd.to_datetime(df["date"]).dt.date
                except Exception as date_error:
                    logger.error(f"Date conversion error for {symbol}: {date_error}")
                    logger.info(f"Date column dtype: {df['date'].dtype}")
                    logger.info(f"Date column sample: {df['date'].head()}")
                    raise

                # Convert volume to integer
                df["volume"] = df["volume"].fillna(0).astype(int)

                # Convert numeric columns to float
                for col in ["open", "high", "low", "close", "adj_close"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

                all_data.append(df)
                success_count += 1
                logger.info(f"✓ Successfully fetched {len(df)} rows for {symbol}")

            except Exception as e:
                error_msg = f"Error fetching data for {symbol}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        if not all_data:
            logger.error("No data was successfully fetched")
            return {
                "status": "error",
                "message": "No data was successfully fetched",
                "errors": errors,
                "symbols_requested": len(symbols),
                "symbols_processed": 0,
            }, 500

        # Combine all dataframes
        combined_df = pd.concat(all_data, ignore_index=True)

        # Load to BigQuery
        logger.info(f"Loading {len(combined_df)} rows to BigQuery table {table_ref}")

        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema=[
                bigquery.SchemaField("symbol", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
                bigquery.SchemaField("open", "FLOAT64"),
                bigquery.SchemaField("high", "FLOAT64"),
                bigquery.SchemaField("low", "FLOAT64"),
                bigquery.SchemaField("close", "FLOAT64"),
                bigquery.SchemaField("adj_close", "FLOAT64"),
                bigquery.SchemaField("volume", "INTEGER"),
                bigquery.SchemaField("inserted_at", "TIMESTAMP", mode="REQUIRED"),
            ],
        )

        job = client.load_table_from_dataframe(
            combined_df, table_ref, job_config=job_config
        )

        job.result()  # Wait for job to complete

        logger.info("✓ Data ingestion completed successfully")

        response = {
            "status": "success",
            "message": f"Successfully ingested data for {success_count}/{len(symbols)} symbols",
            "rows_inserted": len(combined_df),
            "symbols_processed": success_count,
            "symbols_requested": len(symbols),
            "errors": errors if errors else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"Response: {json.dumps(response, indent=2)}")
        return response, 200

    except Exception as e:
        error_msg = f"Fatal error in data ingestion: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "error",
            "message": error_msg,
            "timestamp": datetime.utcnow().isoformat(),
        }, 500


# Optional: Health check endpoint
@functions_framework.http
def health_check(request):
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "stock-data-ingestion",
    }, 200
