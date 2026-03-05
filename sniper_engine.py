import logging
import time
from config import config
from binance_api import binance_api
from grok_api import grok_api
from tg_bot import tg_bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SniperEngine:
    """
    核心扫盘引擎
    负责串联 Binance 链上数据、安全风控、Grok 情绪分析与 Telegram 报警
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        # 使用集合保存已经处理过的合约地址，防止重复报警
        # 在实际生产环境中，可以使用 Redis 来持久化这个集合
        self.seen_tokens = set()

    def run_scan_cycle(self):
        """
        执行一次完整的扫盘周期
        """
        logging.info("=" * 40)
        logging.info("开始执行新一轮 Meme 金狗扫盘...")

        # 1. 抓取即将打满的早期代币列表
        tokens = binance_api.get_finalizing_memes(chain_id=self.chain_id, limit=10)

        if not tokens:
            logging.info("当前没有符合打满条件的早期代币。")
            return

        logging.info(f"扫盘发现 {len(tokens)} 个高潜代币，开始逐一分析...")

        for token in tokens:
            symbol = token.get("symbol", "Unknown")
            ca = token.get("contractAddress")

            if not ca:
                continue

            # 过滤已经分析过的代币
            if ca in self.seen_tokens:
                logging.debug(f"代币 ${symbol} 已处理过，跳过。")
                continue

            # 加入已处理集合 (防止下次循环重复处理)
            self.seen_tokens.add(ca)

            logging.info(f"🔍 锁定新代币: ${symbol} ({ca})")

            # 2. 毫秒级安全审计 (链上物理防线)
            audit_result = binance_api.audit_token_security(self.chain_id, ca)
            if not audit_result.get("is_safe"):
                logging.warning(f"⚠️ 剔除 ${symbol}: 安全审计未通过 -> {audit_result.get('reason')}")
                continue  # 安全不达标，直接抛弃，跳过 Grok 分析（省钱）

            logging.info(f"✅ 代币 ${symbol} 审计通过，无合约风险！准备交由 Grok 进行推特流量透视...")

            # 3. Grok 推特流量与情绪透视
            grok_analysis = grok_api.analyze_token_traffic(token)
            rating = grok_analysis.get("rating", "F")

            # 4. 终极决策与推送
            # 只有评级为 S 或 A 的共振/高潜币种，才推送到 Telegram
            if rating in ["S", "A"]:
                logging.info(f"🚀 确认高质量目标 ${symbol} (评级 {rating})，正在触发 Telegram 警报！")
                tg_bot.format_and_send_alert(token, grok_analysis)
            else:
                logging.info(f"🛑 放弃 ${symbol}: Grok 评级为 {rating}，缺乏真实流量或存在负面情绪。")

            # 礼貌性延时，避免触发 API 速率限制
            time.sleep(2)

        logging.info("本轮扫盘结束。")
        logging.info("=" * 40)


# 实例化引擎
engine = SniperEngine()