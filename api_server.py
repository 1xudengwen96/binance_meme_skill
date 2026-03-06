import logging
import os
from collections import deque
from flask import Flask, request, jsonify, send_from_directory


# ==========================================
# 新增：全局内存日志捕获器
# 用于将后端日志同步推送到前端大盘展示
# ==========================================
class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=200):
        super().__init__()
        # 使用双端队列，最多保存最近 200 条日志，避免内存溢出
        self.logs = deque(maxlen=capacity)

    def emit(self, record):
        # 格式化日志内容并追加到队列
        log_entry = self.format(record)
        self.logs.append(log_entry)

    def get_logs(self):
        return list(self.logs)


# 挂载自定义日志处理器到全局
memory_handler = MemoryLogHandler()
# 简化前端显示的时间格式
formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
memory_handler.setFormatter(formatter)
# 获取根日志记录器并添加处理器
logging.getLogger().addHandler(memory_handler)
logging.getLogger().setLevel(logging.INFO)

# ==========================================
# Flask Web 服务初始化
# ==========================================
app = Flask(__name__, static_folder='.')
_engine_instance = None


def init_api_server(engine):
    """初始化 API 服务器并绑定 SniperEngine 实例"""
    global _engine_instance
    _engine_instance = engine
    logging.info("🔌 API 控制接口已成功绑定狙击引擎实例。")


@app.route('/')
def index():
    """提供前端作战大盘 HTML 页面"""
    if os.path.exists('index.html'):
        return send_from_directory('.', 'index.html')
    return "⚠️ 找不到 index.html，请确保作战大盘页面文件在当前目录下。", 404


# ==========================================
# API 接口路由
# ==========================================
@app.route('/api/toggle_engine', methods=['POST'])
def toggle_engine():
    """一键启停控制接口"""
    global _engine_instance
    if not _engine_instance:
        return jsonify({"status": "error", "message": "引擎未初始化绑定"}), 500

    try:
        data = request.get_json()
        action = data.get('action')

        if action == 'start':
            _engine_instance.set_active_state(True)
            return jsonify({"status": "success", "message": "猎犬已出笼，恢复打狗！", "is_active": True})
        elif action == 'stop':
            _engine_instance.set_active_state(False)
            return jsonify({"status": "success", "message": "引擎已暂停，进入休息状态。", "is_active": False})
        else:
            return jsonify({"status": "error", "message": f"未知指令: {action}"}), 400

    except Exception as e:
        logging.error(f"❌ 切换引擎状态时发生错误: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取当前系统运行状态"""
    global _engine_instance
    is_active = getattr(_engine_instance, 'is_active', False) if _engine_instance else False
    return jsonify({"status": "success", "is_active": is_active})


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """前端获取实时日志的接口"""
    return jsonify({"status": "success", "logs": memory_handler.get_logs()})


# ==========================================
# 服务器启动逻辑
# ==========================================
def run_server(host='0.0.0.0', port=8000):
    """启动 Flask Web 服务器"""
    # 禁用 Flask 默认的访问日志，保持终端和前端清爽
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    print(f"\n🌐 Web 作战大盘已启动: http://127.0.0.1:{port}\n")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    run_server()