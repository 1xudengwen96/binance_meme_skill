import time
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from config import config
from sniper_engine import SniperEngine  # 改为导入类名，由 main 函数负责实例化

# 统一配置全局日志格式，增加日期显示
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# --- 健康检查服务器配置 ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """处理面板或监控的探测请求"""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK - Meme Hunter is alive")

    def log_message(self, format, *args):
        """静默处理健康检查日志"""
        return


def run_health_server(port=8000):
    """启动健康检查 HTTP 服务器"""
    try:
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logging.info(f"✅ 健康检查/面板监控服务已启动，监听端口: {port}")
        server.serve_forever()
    except Exception as e:
        logging.error(f"❌ 无法启动健康检查服务器: {e}")


# --------------------------

def main():
    print("===================================================")
    print("🚀 Grok + Binance: 自动化 Meme 金狗探测器 (V3.2) 启动")
    print("===================================================")

    try:
        # 1. 启动前校验环境变量是否配置完整
        config.validate()
        logging.info("⚙️  环境变量校验通过。")
    except ValueError as e:
        logging.error(f"❌ 配置错误: {e}")
        return

    # 2. 实例化狙击引擎
    # 在这里实例化可以捕捉到 sniper_engine.py 初始化过程中的报错
    try:
        engine = SniperEngine()
        logging.info("🎯 狙击引擎实例化成功。")
    except Exception as e:
        logging.error(f"❌ 狙击引擎初始化失败: {e}")
        return

    # 3. 在独立线程中启动健康检查服务 (端口 8000)
    health_thread = threading.Thread(
        target=run_health_server,
        kwargs={'port': 8000},
        daemon=True
    )
    health_thread.start()

    logging.info(f"📡 扫描任务启动，间隔: {config.SCAN_INTERVAL} 秒。")
    logging.info("---------------------------------------------------")

    # 4. 进入主循环：不间断扫描
    while True:
        try:
            # 执行一轮扫盘逻辑
            engine.run_scan_cycle()

            # 按照配置文件设定的间隔进行休眠
            time.sleep(config.SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 接收到退出指令，程序安全终止。")
            break
        except Exception as e:
            # 捕获异常，防止网络波动导致整个程序崩溃
            logging.error(f"⚠️ 扫描周期发生异常: {e}")
            time.sleep(config.SCAN_INTERVAL)


if __name__ == "__main__":
    main()