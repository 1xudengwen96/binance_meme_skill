import logging
import time
from config import config
from binance_api import binance_api
from grok_api import grok_api
from tg_bot import tg_bot
from feishu_bot import feishu_bot
from trade_engine import trader  # 引入交易引擎

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SniperEngine:
    """
    核心扫盘引擎 - 全自动狙击作战版
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()
        self.last_hits = []

    def is_token_physical_quality_fine(self, token: dict, rank_type: int) -> tuple:
        symbol = token.get("symbol", "Unknown")
        progress = float(token.get("progress", 0))
        protocol = token.get("protocol")

        allowed_protocols = [1001, 2001, 2002]
        if protocol not in allowed_protocols: return False, f"非主流协议 ({protocol})"

        if rank_type == 10 and progress < 50:
            return False, f"新币进度尚浅 ({progress}%)"
        elif rank_type == 20 and progress < 80:
            return False, f"打满榜进度不足 ({progress}%)"

        if float(token.get("holdersTop10Percent", 100)) > 35: return False, f"筹码过分集中"
        if float(token.get("devSellPercent", 0)) > 40: return False, f"开发者已撤退"
        if float(token.get("marketCap", 0)) < 20000: return False, f"市值过低"

        return True, "物理指标通过"

    def match_narrative_and_funds(self, token: dict, trending_topics: list, smart_inflow: list) -> dict:
        symbol = token.get("symbol", "").upper()
        ca = token.get("contractAddress", "").lower()

        result = {"narrative_hit": None, "smart_money_hit": False, "inflow_amount": 0}

        for topic in trending_topics:
            topic_name = topic.get("name", {}).get("topicNameEn", "").upper()
            if symbol in topic_name or topic_name in symbol:
                result["narrative_hit"] = topic_name
                break

        for item in smart_inflow:
            if item.get("ca", "").lower() == ca:
                result["smart_money_hit"] = True
                result["inflow_amount"] = item.get("inflow", 0)
                break

        return result

    def process_token_list(self, tokens: list, rank_type: int, rank_name: str, trending_topics: list,
                           smart_inflow: list):
        if not tokens: return

        for token in tokens:
            symbol = token.get("symbol", "Unknown")
            ca = token.get("contractAddress")

            if not ca or ca in self.seen_tokens: continue

            is_fine, reason = self.is_token_physical_quality_fine(token, rank_type)
            if not is_fine:
                logging.info(f"⏩ [{rank_name}] 跳过 ${symbol}: {reason}")
                self.seen_tokens.add(ca)
                continue

            context = self.match_narrative_and_funds(token, trending_topics, smart_inflow)

            audit_result = binance_api.audit_token_security(self.chain_id, ca)
            if not audit_result.get("is_safe"):
                logging.warning(f"❌ [{rank_name}] 安全拦截 ${symbol}: {audit_result.get('reason')}")
                self.seen_tokens.add(ca)
                continue

            hit_msg = []
            if context["narrative_hit"]: hit_msg.append(f"叙事:[{context['narrative_hit']}]")
            if context["smart_money_hit"]: hit_msg.append(f"聪明钱:[${context['inflow_amount']}]")
            tag = " | ".join(hit_msg) if hit_msg else "普通热度"

            logging.info(f"💎 [{rank_name}] 锁定目标 ${symbol} ({tag}). 请求 Grok-4...")

            self.seen_tokens.add(ca)
            analysis_payload = {**token, **context}
            grok_analysis = grok_api.analyze_token_traffic(analysis_payload)

            rating = grok_analysis.get("rating", "F")

            if rating in ["S", "A"]:
                logging.info(f"🚀 [{rank_name}] 确认金狗 ${symbol} (评级 {rating})！")
                token_with_context = {**token, "context": context}
                self.last_hits.append(token_with_context)  # 加入供 API 获取

                tg_bot.format_and_send_alert(token_with_context, grok_analysis)
                feishu_bot.format_and_send_alert(token_with_context, grok_analysis)

                # ==========================================
                # 自动买入触发 (严格限制只买 S 级)
                # ==========================================
                if rating == "S":
                    trader.buy_token(token_with_context)
            else:
                logging.info(f"🛑 [{rank_name}] 放弃 ${symbol}: Grok 评级 {rating}")

            time.sleep(1)

    def run_scan_cycle(self):
        logging.info("=" * 50)
        logging.info("🌍 正在抓取全局背景：叙事热点 & 聪明钱流向...")
        trending_topics = binance_api.get_trending_topics(self.chain_id)
        smart_inflow = binance_api.get_smart_money_inflow(self.chain_id)

        logging.info(f"轨道 A: 轮询 {self.chain_id} 【即将打满】名单...")
        final_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=20)
        self.process_token_list(final_tokens, 20, "打满榜", trending_topics, smart_inflow)

        logging.info(f"轨道 B: 轮询 {self.chain_id} 【高热新币】名单...")
        new_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=10)
        self.process_token_list(new_tokens, 10, "新币榜", trending_topics, smart_inflow)

        logging.info(f"轨道 C: 轮询 {self.chain_id} 【刚刚迁移】名单...")
        migrated_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=30)
        self.process_token_list(migrated_tokens, 30, "已迁移榜", trending_topics, smart_inflow)

        logging.info("本轮智能扫盘结束。")
        logging.info("=" * 50)


engine = SniperEngine()