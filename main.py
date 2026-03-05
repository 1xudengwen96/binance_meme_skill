import time
import logging
import schedule
from config import config
from sniper_engine import engine

# 配置全局日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def job():
    """
    定时任务包裹函数
    """
    try:
        engine.run_scan_cycle()
    except Exception as e:
        logging.error(f"扫盘任务执行过程中发生未捕获的异常: {e}", exc_info=True)


def main():
    """
    程序主入口
    """
    print("""
    ==================================================
    🚀 Grok + Binance: 自动化 Meme 金狗探测器已启动 🚀
    ==================================================
    """)

    # 1. 启动前校验环境变量是否配置完整
    try:
        config.validate()
        logging.info("配置校验通过！")
    except ValueError as e:
        logging.error(e)
        logging.info("💡 请先复制 .env.example 为 .env，并填入你的 API 密钥！")
        return

    # 2. 立即执行一次
    job()

    # 3. 设定定时任务 (默认每 30 秒扫一次)
    interval = config.SCAN_INTERVAL
    schedule.every(interval).seconds.do(job)
    logging.info(f"已设置定时任务：每 {interval} 秒执行一次自动扫盘。")

    # 4. 保持程序运行
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()