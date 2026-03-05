import logging
import time
from config import config
from binance_api import binance_api
from grok_api import grok_api
from tg_bot import tg_bot
from feishu_bot import feishu_bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SniperEngine:
    """
    核心扫盘引擎 - 专注于“即将打满”的精选代币
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()

    def is_token_quality_fine(self, token: dict) -> tuple:
        """
        [精选层] 在请求 Grok 之前，先通过物理指标过滤，极大地节省 Token
        """
        symbol = token.get("symbol", "Unknown")
        progress = float(token.get("progress", 0))

        # 1. 进度过滤：必须达到 95% 以上
        if progress < 95:
            return False, f"进度不足 ({progress}%)"

        # 2. 筹码集中度 (Top 10 Holders)
        # 超过 50% 视为高度控盘（比之前更严格）
        holders_top10 = float(token.get("holdersTop10Percent", 100))
        if holders_top10 > 50:
            return False, f"筹码过于集中 ({holders_top10}%)"

        # 3. 开发者行为
        # 开发者卖了超过 20% 就跳过
        dev_sell = float(token.get("devSellPercent", 0))
        if dev_sell > 20:
            return False, f"开发者已跑路/抛售 ({dev_sell}%)"

        # 4. 市值过滤
        mcap = float(token.get("marketCap", 0))
        if mcap < 20000:
            return False, f"市值太小 (${mcap:.0f})"

        return True, "优质精选目标"

    def run_scan_cycle(self):
        """
        执行一次完整的扫盘周期
        """
        logging.info("=" * 40)
        logging.info("开始执行新一轮【即将打满】金狗扫盘...")

        # 1. 抓取即将打满的榜单
        tokens = binance_api.get_finalizing_memes(chain_id=self.chain_id, limit=10)

        if not tokens:
            logging.info("当前没有符合打满条件的代币。")
            return

        for token in tokens:
            symbol = token.get("symbol", "Unknown")
            ca = token.get("contractAddress")

            if not ca or ca in self.seen_tokens:
                continue

            # 2. 物理指标初筛 (无需花费 Token)
            is_fine, reason = self.is_token_quality_fine(token)
            if not is_fine:
                logging.info(f"⏩ 跳过 ${symbol}: {reason}")
                # 注意：即便没过初筛，也记录 CA 防止重复扫描同一个垃圾币
                self.seen_tokens.add(ca)
                continue

            # 3. 安全审计
            audit_result = binance_api.audit_token_security(self.chain_id, ca)
            if not audit_result.get("is_safe"):
                logging.warning(f"❌ 剔除 ${symbol}: {audit_result.get('reason')}")
                self.seen_tokens.add(ca)
                continue

            logging.info(
                f"💎 发现优质精选 ${symbol}，进度 {token.get('progress')}%。请求 Grok-4 进行最后的社交背书分析...")

            # 4. Grok 流量透视
            self.seen_tokens.add(ca)
            grok_analysis = grok_api.analyze_token_traffic(token)
            rating = grok_analysis.get("rating", "F")

            # 5. 最终推送
            if rating in ["S", "A"]:
                logging.info(f"🚀 确认金狗 ${symbol} (评级 {rating})，发送推送！")
                tg_bot.format_and_send_alert(token, grok_analysis)
                feishu_bot.format_and_send_alert(token, grok_analysis)
            else:
                logging.info(f"🛑 放弃 ${symbol}: Grok 评级 {rating}")

            time.sleep(2)

        logging.info("扫盘周期结束。")
        logging.info("=" * 40)


engine = SniperEngine()