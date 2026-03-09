import logging
import os
from collections import deque
from flask import Flask, request, jsonify, send_from_directory
from config import config


class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=200):
        super().__init__()
        self.logs = deque(maxlen=capacity)

    def emit(self, record):
        self.logs.append(self.format(record))

    def get_logs(self):
        return list(self.logs)


memory_handler = MemoryLogHandler()
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
memory_handler.setFormatter(formatter)
logging.getLogger().addHandler(memory_handler)
logging.getLogger().setLevel(logging.INFO)

app = Flask(__name__, static_folder='.')
_engine_instance = None


def init_api_server(engine):
    global _engine_instance
    _engine_instance = engine


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/toggle_engine', methods=['POST'])
def toggle_engine():
    data = request.get_json()
    action = data.get('action')
    state = (action == 'start')
    if _engine_instance:
        _engine_instance.set_active_state(state)
    return jsonify({"status": "success", "is_active": state, "message": "指令已同步"})


@app.route('/api/update_config', methods=['POST'])
def update_config():
    """动态更新云端配置，无需重启服务器即可生效"""
    try:
        data = request.get_json()
        config.BUY_AMOUNT_SOL = float(data.get('buy_amount', config.BUY_AMOUNT_SOL))
        config.SOL_PRIORITY_FEE = float(data.get('priority_fee', config.SOL_PRIORITY_FEE))
        config.SLIPPAGE_DEFAULT = int(float(data.get('slippage', 10)) * 100)
        config.GROK_SCORE_THRESHOLD = int(data.get('grok_threshold', config.GROK_SCORE_THRESHOLD))
        config.MAX_TOP10_HOLDING = float(data.get('max_top10', config.MAX_TOP10_HOLDING))

        logging.info("⚙️ 云端配置已实时热更新！")
        return jsonify({"status": "success", "message": "配置已成功下发生效"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/api/manual_snipe', methods=['POST'])
def manual_snipe():
    """接收前端手动强吃买入指令"""
    from trade_engine import trade_engine
    data = request.get_json()
    ca = data.get('ca')
    amount = float(data.get('amount', 0.1))

    logging.info(f"⚡ [前端指令] 正在强行狙击合约: {ca}")
    tx = trade_engine.execute_swap(ca, action="buy", amount_sol=amount, slippage_bps=2000)

    if tx and not tx.startswith("sim_tx"):
        return jsonify({"status": "success", "message": f"买入指令已上链: {tx[:10]}..."})
    elif tx and tx.startswith("sim_tx"):
        return jsonify({"status": "success", "message": f"模拟买入成功 (未配置私钥): {tx}"})
    else:
        return jsonify({"status": "error", "message": "交易发送失败，请检查控制台日志"})


@app.route('/api/status')
def get_status():
    return jsonify({"status": "success", "is_active": getattr(_engine_instance, 'is_active', False)})


@app.route('/api/stats')
def get_stats():
    from trade_engine import trade_engine
    stats = getattr(_engine_instance, 'stats', {"total_scanned": 0, "ai_blocked": 0, "success_sniped": 0}).copy()
    stats['defended'] = getattr(trade_engine, 'defense_count', 0)
    return jsonify({"status": "success", "stats": stats})


@app.route('/api/logs')
def get_logs():
    return jsonify({"status": "success", "logs": memory_handler.get_logs()})


def run_server(host='0.0.0.0', port=8000):
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False)