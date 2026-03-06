import logging
import time
from config import config
from binance_api import binance_api
from grok_api import grok_api
from tg_bot import tg_bot
from feishu_bot import feishu_bot

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SniperEngine:
    """
    核心扫盘引擎 - 严控过滤版
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()

    def is_token_quality_fine(self, token: dict, rank_type: int) -> tuple:
        """
        [精选层] 物理指标过滤：收紧门槛以节省 Grok 成本并降低风险
        """
        symbol = token.get("symbol", "Unknown")
        progress = float(token.get("progress", 0))
        protocol = token.get("protocol")

        # 1. 协议过滤：必须是主流发射平台
        allowed_protocols = [1001, 2001, 2002]
        if protocol not in allowed_protocols:
            return False, f"非主流协议 ({protocol})"

        # 2. 动态进度过滤
        if rank_type == 10:  # 新币榜
            if progress < 50:
                return False, f"新币进度尚浅 ({progress}%)"
        else:  # 即将打满榜 (rank_type 20)
            if progress < 80:
                return False, f"打满榜进度不足 ({progress}%)"

        # 3. 开发者信誉检查 (弹性参考)
        # 虽然不作为硬性拦截，但记录在日志中供参考
        dev_migrate_count = int(token.get("devMigrateCount", 0))

        # 4. 筹码集中度检查 (Top 10 Holders) - 恢复严控
        # 严格限制在 35% 以内，防止低市值下的绝对控盘
        holders_top10 = float(token.get("holdersTop10Percent", 100))
        if holders_top10 > 35:
            return False, f"筹码过分集中 ({holders_top10}%)"

        # 5. 开发者仓位检查
        dev_sell = float(token.get("devSellPercent", 0))
        if dev_sell > 30:
            return False, f"开发者已大规模跑路 ({dev_sell}%)"

        # 6. 市值过滤 - 恢复门槛
        # 只有市值达到 $20,000 以上才认为具备初步分析价值
        mcap = float(token.get("marketCap", 0))
        if mcap < 20000:
            return False, f"市值过低 (${mcap:.0f})，不值得分析"

        return True, "物理指标优秀，准许进入 Grok 分析"

    def process_token_list(self, tokens: list, rank_type: int, rank_name: str):
        """
        处理特定榜单的代币逻辑
        """
        if not tokens:
            logging.info(f"[{rank_name}] 当前无符合条件的代币。")
            return

        for token in tokens:
            symbol = token.get("symbol", "Unknown")
            ca = token.get("contractAddress")

            if not ca or ca in self.seen_tokens:
                continue

            # 1. 指标初筛
            is_fine, reason = self.is_token_quality_fine(token, rank_type)
            if not is_fine:
                logging.info(f"⏩ [{rank_name}] 跳过 ${symbol}: {reason}")
                self.seen_tokens.add(ca)
                continue

            # 2. 安全审计
            audit_result = binance_api.audit_token_security(self.chain_id, ca)
            if not audit_result.get("is_safe"):
                logging.warning(f"❌ [{rank_name}] 安全拦截 ${symbol}: {audit_result.get('reason')}")
                self.seen_tokens.add(ca)
                continue

            logging.info(f"💎 [{rank_name}] 发现潜力目标 ${symbol} (进度 {token.get('progress')}%). 请求 Grok-4 分析...")

            # 3. Grok 分析与推送
            self.seen_tokens.add(ca)
            grok_analysis = grok_api.analyze_token_traffic(token)
            rating = grok_analysis.get("rating", "F")

            if rating in ["S", "A"]:
                logging.info(f"🚀 [{rank_name}] 锁定金狗 ${symbol} (评级 {rating})，发送推送！")
                tg_bot.format_and_send_alert(token, grok_analysis)
                feishu_bot.format_and_send_alert(token, grok_analysis)
            else:
                logging.info(f"🛑 [{rank_name}] 放弃 ${symbol}: Grok 评级 {rating}")

            time.sleep(1)

    def run_scan_cycle(self):
        """
        执行一次完整的扫盘周期
        """
        logging.info("=" * 45)

        logging.info(f"轨道 A: 轮询 {self.chain_id} 【即将打满】名单...")
        finalizing_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=20)
        self.process_token_list(finalizing_tokens, 20, "打满榜")

        logging.info(f"轨道 B: 轮询 {self.chain_id} 【高热新币】名单...")
        new_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=10)
        self.process_token_list(new_tokens, 10, "新币榜")

        logging.info("本轮双轨扫盘周期结束。")
        logging.info("=" * 45)


engine = SniperEngine()