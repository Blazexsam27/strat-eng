from flask import Blueprint, jsonify, request

api = Blueprint('api', __name__)

@api.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@api.route('/backtest', methods=['POST'])
def run_backtest():
    data = request.json
    # Here you would integrate with the backtesting engine
    # For now, we will just return the received data
    return jsonify({"message": "Backtest started", "data": data}), 202

@api.route('/strategies', methods=['GET'])
def get_strategies():
    # This would typically fetch strategies from the backtesting module
    strategies = ["strategy1", "strategy2", "strategy3"]
    return jsonify({"strategies": strategies}), 200

@api.route('/metrics', methods=['GET'])
def get_metrics():
    # This would typically fetch metrics from the backtesting results
    metrics = {"PnL": 1000, "Sharpe Ratio": 1.5}
    return jsonify({"metrics": metrics}), 200