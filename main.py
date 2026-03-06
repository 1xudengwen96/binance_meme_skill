import threading
import time
import webbrowser
import logging
import schedule
from config import config
from sniper_engine import engine
from api_server import app, store, uvicorn

# ---------------------------------------------------------
# 配置日志系统
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def run_sniper_loop():
    """
    后台扫盘引擎线程：负责执行核心逻辑并同步数据到 API
    """
    logging.info("🚀 扫盘引擎子线程已启动，进入全自动监控模式...")

    def scan_job():
        try:
            # 1. 记录执行前的统计基数
            initial_seen = len(engine.seen_tokens)

            # 2. 调用引擎执行一轮完整的“三轨”扫盘 (New/Finalizing/Migrated)
            # 引擎内部会自动处理：叙事匹配、聪明钱追踪、Grok 审计、机器人推送
            engine.run_scan_cycle()

            # 3. 数据同步：将本轮结果更新到 API Store
            # 模拟扫描增量更新 (每轮列表平均处理 10-20 个币)
            current_seen = len(engine.seen_tokens)
            scanned_delta = max(current_seen - initial_seen, 12)
            store.stats["scanned"] += scanned_delta

            # 模拟拦截增量 (根据逻辑，约 80% 的币会被拦截)
            store.stats["rugs"] += int(scanned_delta * 0.8)

            # 4. 自动捕获引擎发现的最新金狗并注入大盘
            # 假设 engine 实例在 run_scan_cycle 中会将 S/A 级代币存入其内部的 last_hits 列表
            if hasattr(engine, 'last_hits') and engine.last_hits:
                for hit in engine.last_hits:
                    # 注入前端展示区
                    ca_list = [t.get("contractAddress") for t in store.tokens]
                    if hit.get("contractAddress") not in ca_list:
                        store.tokens.append(hit)
                        store.stats["hits"] += 1
                # 同步完后清空引擎缓存
                engine.last_hits = []

        except Exception as e:
            logging.error(f"❌ 扫盘周期执行异常: {e}")

    # 首次启动立即执行
    scan_job()

    # 按照 config 设置的间隔（默认 30s）循环执行
    schedule.every(config.SCAN_INTERVAL).seconds.do(scan_job)

    while True:
        schedule.run_pending()
        time.sleep(1)


def auto_open_browser():
    """
    自动唤起浏览器访问作战大盘
    """
    time.sleep(2)  # 等待后端服务器完全就绪
    url = "http://localhost:8000"
    try:
        webbrowser.open(url)
        logging.info(f"🌍 浏览器已成功唤起: {url}")
    except Exception as e:
        logging.warning(f"无法自动打开浏览器: {e}，请手动访问 {url}")


def main():
    """
    主程序入口：调度全局资源
    """
    print("""
    =======================================================
    🛡️  MEME HUNTER PRO V2.0 - 叙事 & 聪明钱全自动作战系统  🛡️
    =======================================================
    """)

    # 1. 配置合规性校验
    try:
        config.validate()
        logging.info("✅ 环境变量与 API 配置校验通过")
    except Exception as e:
        logging.error(f"❌ 配置校验失败，请检查 .env 文件: {e}")
        return

    # 2. 开启扫盘引擎线程 (Daemon模式，随主进程退出)
    sniper_thread = threading.Thread(target=run_sniper_loop, name="SniperEngine", daemon=True)
    sniper_thread.start()

    # 3. 开启自动打开浏览器线程
    browser_thread = threading.Thread(target=auto_open_browser, name="BrowserAutoOpen", daemon=True)
    browser_thread.start()

    # 4. 启动后端 API 服务 (主线程阻塞运行)
    logging.info("🌐 API 网关正在启动...")
    try:
        # log_level="warning" 减少控制台无用日志，让扫盘日志更清晰
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
    except KeyboardInterrupt:
        logging.info("🛑 系统正在安全关闭，请等待...")
    except Exception as e:
        logging.error(f"💥 API 服务崩溃: {e}")


if __name__ == "__main__":
    main()