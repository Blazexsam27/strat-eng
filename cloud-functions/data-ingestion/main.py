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
        logger.info(f"Target: {PROJECT_ID}.{DATASET_ID}.{TABLE_ID}")

        # Initialize BigQuery client
        client = bigquery.Client(project=PROJECT_ID)
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

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

                df = yf.download(
                    symbol,
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                    progress=False,
                )

                if df.empty:
                    logger.warning(f"No data retrieved for {symbol}")
                    continue

                # Prepare data for BigQuery
                df = df.reset_index()
                df["symbol"] = symbol
                df["inserted_at"] = datetime.utcnow()

                # Rename columns to match BigQuery schema
                df = df.rename(
                    columns={
                        "Date": "date",
                        "Open": "open",
                        "High": "high",
                        "Low": "low",
                        "Close": "close",
                        "Adj Close": "adj_close",
                        "Volume": "volume",
                    }
                )

                # Select only required columns
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

                # Convert date to string format for BigQuery
                df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

                # Convert volume to integer
                df["volume"] = df["volume"].fillna(0).astype(int)

                all_data.append(df)
                success_count += 1
                logger.info(f"✓ Successfully fetched {len(df)} rows for {symbol}")

            except Exception as e:
                error_msg = f"Error fetching data for {symbol}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        if not all_data:
            logger.error("No data was successfully fetched")
            return {
                "status": "error",
                "message": "No data was successfully fetched",
                "errors": errors,
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
