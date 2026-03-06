import time
import threading
import logging
from config import config
from sniper_engine import SniperEngine
from api_server import init_api_server, run_server

# 统一配置全局日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def main():
    print("===================================================")
    print("🚀 Meme Hunter Pro V3 - Solana 极速量化狙击系统启动")
    print("===================================================")

    try:
        # 1. 启动前校验核心配置（API Key、私钥等）
        config.validate()
    except ValueError as e:
        print(e)
        return

    # 2. 实例化加权狙击引擎
    engine = SniperEngine()

    # 3. 初始化并启动后台 API 与 Web 服务 (强制绑定 8000 端口)
    init_api_server(engine)
    api_thread = threading.Thread(
        target=run_server,
        kwargs={'host': '0.0.0.0', 'port': 8000},
        daemon=True
    )
    api_thread.start()

    logging.info(f"✅ 核心引擎初始化完成 | 轮询间隔: {config.SCAN_INTERVAL} 秒 | 优先费: {config.SOL_PRIORITY_FEE} SOL")
    logging.info("💡 提示: 请在浏览器中打开 http://127.0.0.1:8000 访问作战大盘！")

    # 4. 进入主循环：不间断扫描打狗
    while True:
        try:
            # 引擎内部会判断 self.is_active 状态来决定是休息还是扫描
            engine.run_scan_cycle()

            # 遵守配置文件的扫描间隔
            time.sleep(config.SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\n🛑 接收到退出指令，程序安全终止。")
            break
        except Exception as e:
            logging.error(f"❌ 主循环发生未捕获异常，将在 {config.SCAN_INTERVAL} 秒后重试: {e}")
            time.sleep(config.SCAN_INTERVAL)


if __name__ == "__main__":
    main()