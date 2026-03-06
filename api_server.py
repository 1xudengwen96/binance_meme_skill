import logging
import os
from flask import Flask, request, jsonify, send_from_directory

# 初始化 Flask 应用，静态文件目录设为当前目录（为了直接读取 index.html）
app = Flask(__name__, static_folder='.')

# 全局变量，用于保存狙击引擎的实例
_engine_instance = None


def init_api_server(engine):
    """
    初始化 API 服务器并绑定 SniperEngine 实例
    由 main.py 在启动时调用
    """
    global _engine_instance
    _engine_instance = engine
    logging.info("🔌 API 控制接口已成功绑定狙击引擎实例。")


# ==========================================
# 页面路由
# ==========================================
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
    """
    一键启停控制接口
    接收 JSON: {"action": "start"} 或 {"action": "stop"}
    """
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
    """
    获取当前系统状态（供前端页面刷新时同步显示）
    """
    global _engine_instance
    is_active = getattr(_engine_instance, 'is_active', False) if _engine_instance else False

    return jsonify({
        "status": "success",
        "is_active": is_active
    })


# ==========================================
# 服务器启动逻辑
# ==========================================
def run_server(host='0.0.0.0', port=8000):
    """
    启动 Flask Web 服务器
    """
    # 禁用 Flask 默认的开发服务器滚动日志，保持终端清爽（只看打狗日志）
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    print(f"\n🌐 Web 作战大盘已启动: http://127.0.0.1:{port}\n")

    # 启动应用
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    # 仅供独立测试 API 使用
    run_server()