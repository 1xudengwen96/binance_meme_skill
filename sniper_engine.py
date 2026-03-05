import logging
import time
from config import config
from binance_api import binance_api
from grok_api import grok_api
from tg_bot import tg_bot
from feishu_bot import feishu_bot  # 导入新模块

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SniperEngine:
    """
    核心扫盘引擎
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()

    def run_scan_cycle(self):
        """
        执行一次完整的扫盘周期
        """
        logging.info("=" * 40)
        logging.info("开始执行新一轮 Meme 金狗扫盘...")

        tokens = binance_api.get_finalizing_memes(chain_id=self.chain_id, limit=10)

        if not tokens:
            logging.info("当前没有符合打满条件的早期代币。")
            return

        for token in tokens:
            symbol = token.get("symbol", "Unknown")
            ca = token.get("contractAddress")

            if not ca or ca in self.seen_tokens:
                continue

            self.seen_tokens.add(ca)

            # 1. 安全审计
            audit_result = binance_api.audit_token_security(self.chain_id, ca)
            if not audit_result.get("is_safe"):
                logging.warning(f"⚠️ 剔除 ${symbol}: 安全审计未通过 -> {audit_result.get('reason')}")
                continue

            # 2. Grok 流量透视
            grok_analysis = grok_api.analyze_token_traffic(token)
            rating = grok_analysis.get("rating", "F")

            # 3. 双通道推送
            if rating in ["S", "A"]:
                logging.info(f"🚀 确认高质量目标 ${symbol} (评级 {rating})，触发全渠道告警！")

                # 发送 Telegram
                tg_bot.format_and_send_alert(token, grok_analysis)

                # 发送 飞书
                feishu_bot.format_and_send_alert(token, grok_analysis)
            else:
                logging.info(f"🛑 放弃 ${symbol}: Grok 评级为 {rating}")

            time.sleep(2)

        logging.info("本轮扫盘结束。")
        logging.info("=" * 40)


engine = SniperEngine()