import time
import logging
import traceback
import threading
from config import config
from sniper_engine import SniperEngine
import api_server

# 配置全局日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def main():
    print("==================================================")
    print("🐺 Meme Hunter Pro V4 - 云端实战版启动 🐺")
    print("==================================================")

    # 1. 启动前核心配置校验
    try:
        config.validate()
    except ValueError as e:
        logging.error(e)
        logging.error("系统启动中止，请检查 .env 配置。")
        return

    # 2. 实例化狙击引擎
    engine = SniperEngine()

    logging.info(f"⚙️ 引擎初始化完成 | 目标链: {config.TARGET_CHAIN_ID}")
    logging.info(f"⏱️ 极速扫描间隔: {config.SCAN_INTERVAL} 秒")
    logging.info(f"🛡️ 自动防守策略: 跌20%断臂 / 涨100%抽本")
    logging.info("--------------------------------------------------")

    # 3. 初始化并启动 Web API 服务 (在独立后台线程中运行，防止阻塞)
    try:
        api_server.init_api_server(engine)
        # 将 Flask 服务作为守护线程(daemon=True)启动，主程序退出时它会自动安全销毁
        web_thread = threading.Thread(target=api_server.run_server, kwargs={'host': '0.0.0.0', 'port': 8000}, daemon=True)
        web_thread.start()
        logging.info("🌐 云端控制台服务已在后台成功挂载。")
    except Exception as e:
        logging.error(f"❌ Web 控制台启动失败: {e}")

    # 4. 开启猎杀主循环 (主线程保持运行)
    while True:
        try:
            start_time = time.time()

            # 执行一次完整的扫描与狙击周期
            engine.run_scan_cycle()

            # 计算耗时，动态调整休眠时间，确保严格遵守轮询周期
            elapsed = time.time() - start_time
            sleep_time = max(0.5, config.SCAN_INTERVAL - elapsed)

            time.sleep(sleep_time)

        except KeyboardInterrupt:
            logging.info("🛑 接收到手动退出信号，猎人引擎安全关闭。")
            break
        except Exception as e:
            logging.error(f"❌ 主循环发生未捕获异常: {e}")
            logging.debug(traceback.format_exc())
            logging.info("🔄 5秒后引擎将自动尝试重启扫描轨道...")
            time.sleep(5)  # 崩溃退避重试，保证无人值守时机器人的存活


if __name__ == "__main__":
    main()