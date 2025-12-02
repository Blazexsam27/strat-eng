#!/bin/bash

# This script automates the process of running backtests for the OpenOpt-RiskEngine.

# Set the environment (if needed)
# source /path/to/your/venv/bin/activate

# Define the backtest parameters
STRATEGY=$1
START_DATE=$2
END_DATE=$3

# Check if the required parameters are provided
if [ -z "$STRATEGY" ] || [ -z "$START_DATE" ] || [ -z "$END_DATE" ]; then
    echo "Usage: $0 <strategy> <start_date> <end_date>"
    exit 1
fi

# Run the backtest using Python
python -m openopt_riskengine.backtesting.engine --strategy "$STRATEGY" --start "$START_DATE" --end "$END_DATE"