import time
import logging
from config import config
from binance_api import binance_api
from grok_api import grok_api
from trade_engine import trade_engine
from dexscreener_api import dexscreener_api

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
    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()  # 记录买过的、彻底Rug的高危币
        self.watch_list = {}  # 记录还在发育期的代币 {ca: scan_count}
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

    def calculate_physical_score(self, token: dict, rank_type: int, is_exclusive: bool = False, ca: str = "") -> tuple[
        int, list]:
        """计算物理基础分 (已修复参数丢失和逻辑死锁)"""
        score = 0
        reasons = []

        # 修复2：通过 CA 后缀识别 pump 盘，不再死板依赖协议号
        is_pump = str(ca).endswith('pump')
        protocol = token.get("protocol")

        if is_exclusive:
            algo_score = self._safe_float(token.get("score"), 0)
            score += 20 + int(algo_score / 5)
            reasons.append(f"🌟 官方高潜榜")
        else:
            # 放宽协议限制：是 pump 盘，或者是明确的 1001/2001，或者有足够市值
            if not is_pump and protocol not in [1001, 2001] and self._safe_float(token.get("marketCap")) < 5000:
                return -1, [f"非Pump且市值极低"]

        progress = self._safe_float(token.get("progress"))
        # 修复1：如果数据源没提供持仓比例，默认当做 0(安全) 而不是 100(极度危险)，防止无辜被杀
        holders_top10 = self._safe_float(token.get("holdersTop10Percent"), default=0.0)
        dev_sell = self._safe_float(token.get("devSellPercent"))
        mcap = self._safe_float(token.get("marketCap"))

        # Pump 盘天然加分 (绝不撤池)
        if is_pump:
            score += 15
            reasons.append("💊 Pump协议(防撤池)")

        # 🦅 DexScreener 专属打分逻辑 (Rank 88)
        if rank_type == 88:
            score += 15
            reasons.append("🦅 Dex热榜/Dev打榜")
            liquidity = self._safe_float(token.get("liquidity"))
            if liquidity >= 20000:
                score += 10
                reasons.append(f"💧 深水池(${liquidity:,.0f})")

        # 进度得分
        if rank_type == 10 and progress >= 30:
            score += 10
            reasons.append(f"新币进展快({progress}%)")
        elif rank_type == 20 and progress >= 70:
            score += 15
            reasons.append(f"即将打满({progress}%)")

        # 筹码集中度得分 (只惩罚真实的高控盘，不误杀无数据盘)
        if holders_top10 > 0:
            if holders_top10 <= 40:
                score += 15
                reasons.append(f"筹码极度分散({holders_top10:.1f}%)")
            elif holders_top10 <= config.MAX_TOP10_HOLDING:
                score += 5
            else:
                return -1, [f"⚠️筹码极度控盘({holders_top10:.1f}%)"]

        # 市值与开发者
        if mcap >= config.MIN_MARKET_CAP:
            score += 5
            reasons.append(f"市值达标(${mcap:,.0f})")

        if dev_sell < config.MAX_DEV_SELL:
            score += 5

        return score, reasons

    def calculate_weighted_score(self, token: dict, audit_data: dict, smart_money: dict, trending_topics: list,
                                 is_exclusive: bool = False, ca: str = "") -> tuple[int, list]:
        """综合加权评分系统"""
        total_score = 0
        score_details = []

        phys_score, phys_reasons = self.calculate_physical_score(token, token.get('rank_type_tracked', 20),
                                                                 is_exclusive, ca)
        if phys_score < 0: return -1, phys_reasons
        total_score += phys_score
        score_details.extend(phys_reasons)

        risk_level = audit_data.get("risk_level", 5)
        is_pump = str(ca).endswith('pump')

        # 修复3：审计逻辑松绑。Pump盘天然安全，不需要过苛刻的币安代码审计 (因为币安经常误判 Pump 没丢权限)
        if risk_level <= 2:
            total_score += 15
            score_details.append("✅ 审计通过")
        elif not is_pump and risk_level >= 4:
            return -1, ["🚨 野生高危合约"]

        sm_count = smart_money.get("smartMoneyCount", 0)
        if sm_count >= 1:
            bonus = min(sm_count * 15, 45)  # 大幅提高聪明钱的权重，这是抓住金狗的核心
            total_score += bonus
            score_details.append(f"🐳 聪明钱介入({sm_count}人)")

        symbol = str(token.get("symbol", "")).upper()
        # 叙事匹配稍微放宽，只要大盘热点词在代币名称中即可
        if any(topic.upper() in symbol for topic in trending_topics):
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

                # 跨链硬隔离
                if self.chain_id == "CT_501" and ca.startswith("0x"): continue
                if self.chain_id == "56" and not ca.startswith("0x"): continue

                self.stats["total_scanned"] += 1
                token['rank_type_tracked'] = rank_type
                symbol = token.get("symbol", "Unknown")

                phys_score, phys_reasons = self.calculate_physical_score(token, rank_type, is_exclusive, ca)

                # 修复4：只把真正的垃圾币拉黑，好币放进观察池 (watch_list) 持续发育
                if phys_score < 0:
                    self.seen_tokens.add(ca)
                    continue

                # 限制轮询频率，如果一个币一直在观察池但长时间没爆发，限制其查询次数，防止内存和 API 爆炸
                watch_count = self.watch_list.get(ca, 0)
                if watch_count > 10:
                    self.seen_tokens.add(ca)  # 看了10次(约半小时)都不行，彻底放弃
                    continue
                self.watch_list[ca] = watch_count + 1

                audit_data = binance_api.get_token_audit(self.chain_id, ca)
                smart_money = binance_api.get_smart_money_info(self.chain_id, ca)

                total_score, score_details = self.calculate_weighted_score(token, audit_data, smart_money,
                                                                           trending_topics, is_exclusive, ca)

                if total_score < 0:
                    self.seen_tokens.add(ca)  # 重新评估后确认为高危盘，拉黑
                    continue

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

                    # 核心修复：直接在终端日志里输出 Grok 的完整文字摘要
                    logging.info(f"🏁 {symbol} 最终得分: {final_score} (含Grok) | 评级: {rating} | 摘要: {summary}")

                    # 🚨 核心修改：提高买入门槛，拒绝瞎买“三无”新币
                    if final_score >= 85:  # S级金狗：物理满分 + Grok A以上 / 或庞大聪明钱
                        self._execute_trade_and_notify(token, rating, final_score, summary, score_details,
                                                       config.SLIPPAGE_S_GRADE)
                    elif final_score >= 75:  # A级跟单：物理满分 + 至少有聪明钱/叙事加持
                        token['override_buy_amount'] = config.BUY_AMOUNT_SOL * 0.5
                        self._execute_trade_and_notify(token, rating, final_score, summary, score_details,
                                                       config.SLIPPAGE_A_GRADE)
                    else:
                        logging.info(f"📉 {symbol} 最终得分不足 ({final_score} < 75)，不值得开仓，放弃买入")
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
            f"🎯 <b>金狗锁定！(评分: {score})</b>\n\n"
            f"🪙 <b>代币</b>: {symbol}\n"
            f"📍 <b>CA</b>: <code>{ca}</code>\n"
            f"📈 <b>进度</b>: {progress}% | <b>市值</b>: ${mcap:,.0f}\n"
            f"💡 <b>亮点</b>: {', '.join(details)}\n\n"
            f"🧠 <b>Grok [{grade}]</b>: {summary}\n"
        )
        if tg_bot: tg_bot.send_message(msg)

        # 👇 [修复核心] 彻底补齐飞书机器人的推送逻辑
        if feishu_bot:
            grok_analysis = {"rating": grade, "summary": summary}
            feishu_bot.format_and_send_alert(token, grok_analysis)

        tx_sig = trade_engine.execute_swap(ca, "buy", amount_sol=buy_amount, slippage_bps=slippage_bps)

        if tx_sig and not tx_sig.startswith("sim_tx"):
            self.stats["success_sniped"] += 1
            trade_engine.start_monitor_thread(ca, symbol, buy_amount)

    def run_scan_cycle(self):
        if not getattr(self, 'is_active', True): return

        try:
            trending_topics = binance_api.get_trending_topics(self.chain_id)

            if self.chain_id == "CT_501":
                dex_tokens = dexscreener_api.get_latest_safe_pairs()
                self.process_token_list(dex_tokens, 88, "DexScreener榜", trending_topics)

            exclusive_tokens = binance_api.get_exclusive_memes(chain_id=self.chain_id)
            self.process_token_list(exclusive_tokens, 99, "官方高潜榜", trending_topics)

            final_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=20)
            self.process_token_list(final_tokens, 20, "打满榜", trending_topics)

            new_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=10)
            self.process_token_list(new_tokens, 10, "新币榜", trending_topics)
        except Exception as e:
            logging.error(f"扫描周期异常: {e}")