import pytest
from openopt_riskengine import cli

def test_end_to_end():
    # Simulate a complete workflow of the OpenOpt-RiskEngine
    # 1. Load data
    data = cli.load_data("path/to/data")
    
    # 2. Transform data
    transformed_data = cli.transform_data(data)
    
    # 3. Run backtest
    results = cli.run_backtest(transformed_data, strategy="example_strategy")
    
    # 4. Validate results
    assert results is not None
    assert "PnL" in results
    assert results["PnL"] >= 0  # Example assertion for profitability

    # 5. Generate report
    report = cli.generate_report(results)
    assert report is not None
    assert "summary" in report

    # 6. Clean up
    cli.cleanup()