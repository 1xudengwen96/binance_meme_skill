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
    核心扫盘引擎 - 叙事与聪明钱增强版 (Narrative & Smart Money Tracking)
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()

    def is_token_physical_quality_fine(self, token: dict, rank_type: int) -> tuple:
        """
        [第一层：物理过滤] 基础指标过滤，不合格的直接排除，节省后续 API 成本
        """
        symbol = token.get("symbol", "Unknown")
        progress = float(token.get("progress", 0))
        protocol = token.get("protocol")

        # 1. 协议过滤：必须是主流发行平台
        allowed_protocols = [1001, 2001, 2002]
        if protocol not in allowed_protocols:
            return False, f"非主流协议 ({protocol})"

        # 2. 动态进度过滤
        if rank_type == 10:  # 新币榜
            if progress < 50:
                return False, f"新币进度尚浅 ({progress}%)"
        elif rank_type == 20:  # 打满榜
            if progress < 80:
                return False, f"打满榜进度不足 ({progress}%)"

        # 3. 筹码分布严控 (Top 10 Holders)
        holders_top10 = float(token.get("holdersTop10Percent", 100))
        if holders_top10 > 35:
            return False, f"筹码过分集中 ({holders_top10}%)"

        # 4. 开发者风险
        dev_sell = float(token.get("devSellPercent", 0))
        if dev_sell > 40:
            return False, f"开发者已撤退 ({dev_sell}%)"

        # 5. 市值门槛
        mcap = float(token.get("marketCap", 0))
        if mcap < 20000:
            return False, f"市值过低 (${mcap:.0f})"

        return True, "物理指标通过"

    def match_narrative_and_funds(self, token: dict, trending_topics: list, smart_inflow: list) -> dict:
        """
        [第二层：背景验证] 检查代币是否符合当前叙事热点或聪明钱流向
        """
        symbol = token.get("symbol", "").upper()
        ca = token.get("contractAddress", "").lower()

        result = {
            "narrative_hit": None,
            "smart_money_hit": False,
            "inflow_amount": 0
        }

        # 1. 匹配叙事热点 (检查 Symbol 或代币名称是否包含话题关键字)
        for topic in trending_topics:
            topic_name = topic.get("name", {}).get("topicNameEn", "").upper()
            if symbol in topic_name or topic_name in symbol:
                result["narrative_hit"] = topic_name
                break

        # 2. 匹配聪明钱流入
        for inflow_item in smart_inflow:
            if inflow_item.get("ca", "").lower() == ca:
                result["smart_money_hit"] = True
                result["inflow_amount"] = inflow_item.get("inflow", 0)
                break

        return result

    def process_token_list(self, tokens: list, rank_type: int, rank_name: str, trending_topics: list,
                           smart_inflow: list):
        """
        处理代币列表，增加叙事与资金权重逻辑
        """
        if not tokens:
            return

        for token in tokens:
            symbol = token.get("symbol", "Unknown")
            ca = token.get("contractAddress")

            if not ca or ca in self.seen_tokens:
                continue

            # 1. 物理指标初筛
            is_fine, reason = self.is_token_physical_quality_fine(token, rank_type)
            if not is_fine:
                logging.info(f"⏩ [{rank_name}] 跳过 ${symbol}: {reason}")
                self.seen_tokens.add(ca)
                continue

            # 2. 叙事与资金背景交叉验证
            context = self.match_narrative_and_funds(token, trending_topics, smart_inflow)

            # 3. 安全审计
            audit_result = binance_api.audit_token_security(self.chain_id, ca)
            if not audit_result.get("is_safe"):
                logging.warning(f"❌ [{rank_name}] 安全拦截 ${symbol}: {audit_result.get('reason')}")
                self.seen_tokens.add(ca)
                continue

            # 如果命中叙事或聪明钱，增加日志高亮
            hit_msg = []
            if context["narrative_hit"]: hit_msg.append(f"叙事:[{context['narrative_hit']}]")
            if context["smart_money_hit"]: hit_msg.append(f"聪明钱流入:[${context['inflow_amount']}]")

            tag = " | ".join(hit_msg) if hit_msg else "普通热度"
            logging.info(f"💎 [{rank_name}] 锁定目标 ${symbol} ({tag}). 请求 Grok-4 最终评审...")

            # 4. Grok 深度评审 (带入叙事和资金背景)
            self.seen_tokens.add(ca)
            # 构造更丰富的分析数据
            analysis_payload = {**token, **context}
            grok_analysis = grok_api.analyze_token_traffic(analysis_payload)

            rating = grok_analysis.get("rating", "F")

            if rating in ["S", "A"]:
                logging.info(f"🚀 [{rank_name}] 确认金狗 ${symbol} (评级 {rating})，发送推送！")
                # 推送时带上背景数据
                token_with_context = {**token, "context": context}
                tg_bot.format_and_send_alert(token_with_context, grok_analysis)
                feishu_bot.format_and_send_alert(token_with_context, grok_analysis)
            else:
                logging.info(f"🛑 [{rank_name}] 放弃 ${symbol}: Grok 评级 {rating}")

            time.sleep(1)

    def run_scan_cycle(self):
        """
        执行完整扫盘周期：全局背景抓取 + 三线并发监控
        """
        logging.info("=" * 50)

        # 1. 抓取全局上下文 (每个周期刷新一次)
        logging.info("🌍 正在抓取全局背景：叙事热点 & 聪明钱流向...")
        trending_topics = binance_api.get_trending_topics(self.chain_id)
        smart_inflow = binance_api.get_smart_money_inflow(self.chain_id)

        # 轨道 A：即将打满 (Finalizing)
        logging.info(f"轨道 A: 轮询 {self.chain_id} 【即将打满】名单...")
        final_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=20)
        self.process_token_list(final_tokens, 20, "打满榜", trending_topics, smart_inflow)

        # 轨道 B：高热新币 (New)
        logging.info(f"轨道 B: 轮询 {self.chain_id} 【高热新币】名单...")
        new_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=10)
        self.process_token_list(new_tokens, 10, "新币榜", trending_topics, smart_inflow)

        # 轨道 C：已迁移 (Migrated)
        logging.info(f"轨道 C: 轮询 {self.chain_id} 【刚刚迁移】名单...")
        migrated_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=30)
        self.process_token_list(migrated_tokens, 30, "已迁移榜", trending_topics, smart_inflow)

        logging.info("本轮全周期智能扫盘结束。")
        logging.info("=" * 50)


engine = SniperEngine()