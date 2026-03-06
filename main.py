import time
import threading
import logging
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from config import config
from sniper_engine import SniperEngine


# ==========================================
# 1. 极简日志捕获 (用于网页同步显示)
# ==========================================
class MemoryLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.logs = []

    def emit(self, record):
        try:
            self.logs.append(self.format(record))
            if len(self.logs) > 30: self.logs.pop(0)
        except Exception:
            self.handleError(record)


log_handler = MemoryLogHandler()
# 修复错误：不能直接写 %H，需要使用 %(asctime)s 并配合 datefmt
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
logging.getLogger().addHandler(log_handler)
logging.getLogger().setLevel(logging.INFO)

ENGINE_INSTANCE = None


# ==========================================
# 2. 极简 API 服务器 (仅处理状态和日志)
# ==========================================
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 处理状态请求，解决“离线”显示问题
        if self.path == '/api/status':
            self._send_json({"status": "success", "is_active": getattr(ENGINE_INSTANCE, 'is_active', True)})

        # 处理日志请求
        elif self.path == '/api/logs':
            self._send_json({"status": "success", "logs": log_handler.logs})

        # 默认返回 index.html 内容
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            if os.path.exists('index.html'):
                with open('index.html', 'rb') as f:
                    self.wfile.read(f.read())
            else:
                self.wfile.write(b"<h1>Bot is Running</h1><p>index.html not found.</p>")

    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        return


def start_server():
    HTTPServer(('0.0.0.0', 8000), SimpleHandler).serve_forever()


# ==========================================
# 3. 主程序
# ==========================================
def main():
    global ENGINE_INSTANCE
    logging.info("🚀 系统初始化中...")

    try:
        config.validate()
        ENGINE_INSTANCE = SniperEngine()
        ENGINE_INSTANCE.is_active = True
    except Exception as e:
        logging.error(f"❌ 启动失败: {e}")
        return

    # 启动 8000 端口监控
    threading.Thread(target=start_server, daemon=True).start()
    logging.info("✅ 监控端口 8000 已开启，正在处理 API 请求...")

    while True:
        try:
            if getattr(ENGINE_INSTANCE, 'is_active', True):
                ENGINE_INSTANCE.run_scan_cycle()
            time.sleep(config.SCAN_INTERVAL)
        except Exception as e:
            logging.error(f"⚠️ 扫盘异常: {e}")
            time.sleep(config.SCAN_INTERVAL)


if __name__ == "__main__":
    main()