import unittest
from openopt_riskengine.backtesting.engine import BacktestEngine
from openopt_riskengine.backtesting.strategies import SampleStrategy

class TestBacktesting(unittest.TestCase):

    def setUp(self):
        self.engine = BacktestEngine()
        self.strategy = SampleStrategy()

    def test_backtest_initialization(self):
        self.assertIsNotNone(self.engine)
        self.assertIsNotNone(self.strategy)

    def test_run_backtest(self):
        results = self.engine.run_backtest(self.strategy)
        self.assertIn('performance', results)
        self.assertGreater(results['performance']['PnL'], 0)

    def test_strategy_metrics(self):
        self.engine.run_backtest(self.strategy)
        metrics = self.engine.get_metrics()
        self.assertIn('Sharpe Ratio', metrics)
        self.assertGreater(metrics['Sharpe Ratio'], 0)

if __name__ == '__main__':
    unittest.main()