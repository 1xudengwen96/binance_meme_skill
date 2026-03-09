import time
import logging
from config import config
from binance_api import binance_api
from grok_api import grok_api
from trade_engine import trade_engine
from dexscreener_api import dexscreener_api  # 🦅 引入刚刚写好的 Level 1 级雷达

# 兼容原有的 TG / Feishu 推送
try:
    from tg_bot import tg_bot
except ImportError:
    tg_bot = None
try:
    from feishu_bot import feishu_bot
except ImportError:
    feishu_bot = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SniperEngine:
    """
    加权评分制 Meme 狙击引擎 (猎人实战进化版)
    解锁官方潜力榜、DexScreener Level 1 雷达、极高规格撤池子防御
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()
        self.is_active = True
        self.stats = {
            "total_scanned": 0,
            "ai_blocked": 0,
            "success_sniped": 0
        }

    def set_active_state(self, state: bool):
        self.is_active = state
        if state:
            logging.info("▶️ [状态切换] 引擎已唤醒，猎犬出笼，恢复打狗！")
        else:
            logging.info("⏸️ [状态切换] 引擎已暂停，进入休息状态。")

    def _safe_float(self, value, default=0.0):
        try:
            if value is None: return default
            return float(value)
        except (ValueError, TypeError):
            return default

    def calculate_physical_score(self, token: dict, rank_type: int, is_exclusive: bool = False) -> tuple[int, list]:
        """计算物理基础分"""
        score = 0
        reasons = []

        symbol = token.get("symbol", "Unknown")
        protocol = token.get("protocol")

        # 🌟 官方独家榜单逻辑
        if is_exclusive:
            algo_score = self._safe_float(token.get("score"), 0)
            score += 20 + int(algo_score / 5)
            reasons.append(f"🌟 官方高潜榜(算法Score:{algo_score})")
        else:
            if protocol not in [1001, 2001]:
                return -1, [f"非目标协议({protocol})"]

        progress = self._safe_float(token.get("progress"))
        holders_top10 = self._safe_float(token.get("holdersTop10Percent"), default=100.0)
        dev_sell = self._safe_float(token.get("devSellPercent"))
        mcap = self._safe_float(token.get("marketCap"))

        # 🦅 DexScreener 专属打分逻辑 (Rank 88)
        if rank_type == 88:
            score += 20
            reasons.append("🦅 Dex热榜/Dev自费打榜认证")
            liquidity = self._safe_float(token.get("liquidity"))
            # 极高流动性加分
            if liquidity >= 50000:
                score += 15
                reasons.append(f"💧 深水池(${liquidity:,.0f})完美承载")
            elif liquidity >= 20000:
                score += 10
                reasons.append(f"💧 标配安全池(${liquidity:,.0f})")

        # 进度得分 (降低抢新门槛)
        if rank_type == 10 and progress >= 30:
            score += 10
            reasons.append(f"新币进展快({progress}%)")
        elif rank_type == 20 and progress >= 70:
            score += 10
            reasons.append(f"打满埋伏区({progress}%)")
        elif rank_type in [30, 99]:
            score += 10
            reasons.append("已迁移或官方推")

        # 筹码集中度得分
        if holders_top10 <= 50:
            score += 15
            reasons.append(f"筹码较分散({holders_top10:.1f}%)")
        elif holders_top10 <= config.MAX_TOP10_HOLDING:
            score += 5
            reasons.append(f"筹码健康({holders_top10:.1f}%)")
        else:
            return -1, [f"⚠️筹码极度控盘({holders_top10:.1f}%)"]

        # 市值与开发者
        if mcap >= config.MIN_MARKET_CAP:
            score += 5
            reasons.append(f"市值达标(${mcap:,.0f})")

        if dev_sell < config.MAX_DEV_SELL or token.get("devPosition") != 2:
            score += 5
            reasons.append(f"开发者未清仓")

        return score, reasons

    def calculate_weighted_score(self, token: dict, audit_data: dict, smart_money: dict, trending_topics: list,
                                 is_exclusive: bool = False) -> tuple[int, list]:
        """综合加权评分系统"""
        total_score = 0
        score_details = []

        phys_score, phys_reasons = self.calculate_physical_score(token, token.get('rank_type_tracked', 20),
                                                                 is_exclusive)
        if phys_score < 0: return -1, phys_reasons
        total_score += phys_score
        score_details.extend(phys_reasons)

        risk_level = audit_data.get("risk_level", 5)
        protocol = token.get("protocol")

        if risk_level <= 2:
            total_score += 15
            score_details.append("✅ 币安深度安全审计通过")
        elif protocol in [1001, 2001]:
            total_score += 20
            score_details.append("🛡️ 平台免审信任(绝无撤池风险)")
        else:
            return -1, ["🚨 野生合约: 高风险拦截"]

        sm_count = smart_money.get("smartMoneyCount", 0)
        if sm_count >= 1:
            bonus = min(sm_count * 10, 30)
            total_score += bonus
            score_details.append(f"🐳 聪明钱介入({sm_count}个)")

        symbol = str(token.get("symbol", "")).upper()
        if any(topic.upper() in symbol or symbol in topic.upper() for topic in trending_topics):
            total_score += 15
            score_details.append(f"🚀 命中大盘叙事")

        return total_score, score_details

    def process_token_list(self, token_list: list, rank_type: int, list_name: str, trending_topics: list):
        if not token_list: return

        is_exclusive = (rank_type == 99)

        for token in token_list:
            try:
                ca = token.get("contractAddress")
                if not ca or ca in self.seen_tokens: continue

                # 严格跨链物理隔离
                if self.chain_id == "CT_501" and ca.startswith("0x"):
                    self.seen_tokens.add(ca)
                    continue
                if self.chain_id == "56" and not ca.startswith("0x"):
                    self.seen_tokens.add(ca)
                    continue

                self.stats["total_scanned"] += 1

                token['rank_type_tracked'] = rank_type
                symbol = token.get("symbol", "Unknown")

                phys_score, phys_reasons = self.calculate_physical_score(token, rank_type, is_exclusive)
                if phys_score < 0:
                    self.seen_tokens.add(ca)
                    continue

                logging.info(f"🔍 发现目标 [{list_name}]: {symbol} ({ca[:6]}...) | 初筛通过")

                # 【终极交叉验证】拿 DexScreener 的数据去问币安要安全审计和聪明钱数据！
                audit_data = binance_api.get_token_audit(self.chain_id, ca)
                smart_money = binance_api.get_smart_money_info(self.chain_id, ca)

                total_score, score_details = self.calculate_weighted_score(token, audit_data, smart_money,
                                                                           trending_topics, is_exclusive)

                if total_score < 0:
                    logging.warning(f"🚫 {symbol} 过滤原因: {', '.join(score_details)}")
                    self.seen_tokens.add(ca)
                    continue

                logging.info(f"📊 {symbol} 当前评分: {total_score} | 亮点: {', '.join(score_details)}")

                if total_score >= config.GROK_SCORE_THRESHOLD:
                    logging.info(f"🧠 {symbol} 达标({total_score}>={config.GROK_SCORE_THRESHOLD})，呼叫 Grok 分析...")
                    grok_result = grok_api.analyze_meme_potential(token)
                    rating = grok_result.get("rating", "Neutral")
                    summary = grok_result.get("summary", "无")

                    final_score = total_score

                    if rating == "S":
                        final_score += 40
                    elif rating == "A":
                        final_score += 20
                    elif rating == "Neutral":
                        final_score += 0
                    elif rating == "F":
                        final_score -= 50

                    logging.info(f"🏁 {symbol} 最终得分: {final_score} (含Grok) | 评级: {rating}")

                    if final_score >= 85:
                        self._execute_trade_and_notify(token, rating, final_score, summary, score_details,
                                                       config.SLIPPAGE_S_GRADE)
                    elif final_score >= 65:
                        token['override_buy_amount'] = config.BUY_AMOUNT_SOL * 0.5
                        self._execute_trade_and_notify(token, rating, final_score, summary, score_details,
                                                       config.SLIPPAGE_A_GRADE)
                    else:
                        logging.info(f"📉 {symbol} 最终得分不足 ({final_score})，放弃买入")
                        if rating in ["F", "Neutral"]: self.stats["ai_blocked"] += 1
                else:
                    logging.info(f"💤 {symbol} 评分({total_score})未达标，无需浪费 AI 算力")

                self.seen_tokens.add(ca)
            except Exception as e:
                logging.error(f"❌ 处理代币 {token.get('symbol')} 时异常: {e}")
                continue

    def _execute_trade_and_notify(self, token, grade, score, summary, details, slippage_bps):
        symbol = token.get("symbol")
        ca = token.get("contractAddress")
        buy_amount = token.get('override_buy_amount', config.BUY_AMOUNT_SOL)
        progress = self._safe_float(token.get("progress"))
        mcap = self._safe_float(token.get("marketCap"))

        msg = (
            f"🎯 <b>发现金狗目标！(最终评分: {score})</b>\n\n"
            f"🪙 <b>代币</b>: {symbol}\n"
            f"📍 <b>CA</b>: <code>{ca}</code>\n"
            f"📈 <b>进度</b>: {progress}% | <b>市值</b>: ${mcap:,.0f}\n"
            f"💡 <b>得分亮点</b>: {', '.join(details)}\n\n"
            f"🧠 <b>Grok (X) 洞察 [{grade}级]</b>: {summary}\n\n"
            f"⚡ 准备执行激进买入: {buy_amount} SOL (滑点: {slippage_bps / 100}%)"
        )

        logging.info(f"🚀 触发交易信号: {symbol} | 评级 {grade}")

        if tg_bot: tg_bot.send_message(msg)

        # 极速执行交易买入
        tx_sig = trade_engine.execute_swap(ca, "buy", amount_sol=buy_amount, slippage_bps=slippage_bps)

        if tx_sig and not tx_sig.startswith("sim_tx"):
            success_msg = f"✅ <b>买入成功!</b>\n代币: {symbol}\nTx: <code>{tx_sig}</code>"
            if tg_bot: tg_bot.send_message(success_msg)

            self.stats["success_sniped"] += 1
            logging.info(f"🛡️ 为 {symbol} 挂载自动防守雷达 (翻倍抽本/移动止损)...")
            trade_engine.start_monitor_thread(ca, symbol, buy_amount)
        elif tx_sig and tx_sig.startswith("sim_tx"):
            logging.info(f"⚠️ {symbol} 模拟买入成功 (未配置私钥)")
        else:
            logging.error(f"❌ {symbol} 买入失败")

    def run_scan_cycle(self):
        if not getattr(self, 'is_active', True):
            logging.info("💤 引擎休息中...")
            return

        logging.info("🌍 同步大盘叙事...")
        trending_topics = binance_api.get_trending_topics(self.chain_id)

        # ==========================================
        # 🦅 新增武器：DexScreener Level 1 实时扫描轨道
        # ==========================================
        if self.chain_id == "CT_501":  # 仅针对 Solana 开启此雷达
            logging.info(f"🦅 扫描轨道: {self.chain_id} [DexScreener 顶级热榜/高流动性区]...")
            dex_tokens = dexscreener_api.get_latest_safe_pairs()
            # 拿到 DexScreener 的数据后，依然会走币安的安全和聪明钱验证！
            self.process_token_list(dex_tokens, 88, "DexScreener榜", trending_topics)

        logging.info(f"🔥 扫描轨道: {self.chain_id} [官方 Exclusive 潜力榜]...")
        exclusive_tokens = binance_api.get_exclusive_memes(chain_id=self.chain_id)
        self.process_token_list(exclusive_tokens, 99, "官方高潜榜", trending_topics)

        logging.info(f"⚡ 扫描轨道: {self.chain_id} [Finalizing 打满埋伏区]...")
        final_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=20)
        self.process_token_list(final_tokens, 20, "打满榜", trending_topics)

        logging.info(f"👶 扫描轨道: {self.chain_id} [New 新币区]...")
        new_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=10)
        self.process_token_list(new_tokens, 10, "新币榜", trending_topics)