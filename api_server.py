import logging
import os
from collections import deque
from flask import Flask, request, jsonify, send_from_directory
from config import config

class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=500): # 增加后台日志缓存容量到500条
        super().__init__()
        self.logs = deque(maxlen=capacity)
        self.counter = 0 # 全局日志自增ID

    def emit(self, record):
        # 存入字典，携带唯一递增 ID
        self.logs.append({"id": self.counter, "text": self.format(record)})
        self.counter += 1

    def get_logs(self, last_id=-1):
        # 如果是初次请求，返回全部缓存；否则只返回比 last_id 更大的新日志（增量推送）
        if last_id == -1:
            return list(self.logs)
        return [log for log in self.logs if log["id"] > last_id]

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

# ==========================================
# 🛡️ CORS 跨域问题解决模块
# ==========================================
@app.before_request
def handle_options():
    """处理浏览器发来的 OPTIONS 预检请求"""
    if request.method == 'OPTIONS':
        return '', 204

@app.after_request
def add_cors_headers(response):
    """全局注入允许跨域的 Header"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response
# ==========================================

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
    # 接收前端传来的 last_id
    last_id = int(request.args.get('last_id', -1))
    logs = memory_handler.get_logs(last_id)
    return jsonify({"status": "success", "logs": logs})

def run_server(host='0.0.0.0', port=8000):
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False, use_reloader=False)