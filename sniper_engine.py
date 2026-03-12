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
        self.seen_tokens = set()
        self.watch_list = {}
        self.is_active = True
        self.stats = {
            "total_scanned": 0,
            "ai_blocked": 0,
            "success_sniped": 0
        }

    def set_active_state(self, state: bool):
        self.is_active = state
        if state:
            logging.info("▶️ [状态切换] 金狗猎犬已唤醒，双链并发猎杀开启！")
        else:
            logging.info("⏸️ [状态切换] 引擎已暂停。")

    def _safe_float(self, value, default=0.0):
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def calculate_physical_score(self, token: dict, rank_type: int, is_exclusive: bool, ca: str, chain_id: str) -> \
    tuple[int, list]:
        score = 0
        reasons = []

        # 识别安全发币平台
        is_pump = str(ca).endswith('pump') and chain_id == "CT_501"
        is_four_meme = chain_id == "56" and "four" in str(token.get("source", "")).lower()
        is_safe_platform = is_pump or is_four_meme

        protocol = token.get("protocol")

        if is_exclusive:
            algo_score = self._safe_float(token.get("score"), 0)
            score += 20 + int(algo_score / 5)
            reasons.append(f"🌟 官方高潜榜")
        else:
            # 基础过滤拦截
            if chain_id == "CT_501" and not is_pump and protocol not in [1001, 2001] and self._safe_float(
                    token.get("marketCap")) < 5000:
                return -1, [f"非Pump且市值极低"]
            if chain_id == "56" and not is_four_meme and self._safe_float(token.get("marketCap")) < 5000:
                return -1, [f"非Four且市值极低"]

        progress = self._safe_float(token.get("progress"))
        holders_top10 = self._safe_float(token.get("holdersTop10Percent"), default=0.0)
        mcap = self._safe_float(token.get("marketCap"))

        if is_safe_platform:
            score += 15
            reasons.append("💊 安全平台协议")

        if rank_type == 88:
            score += 15
            reasons.append("🦅 Dex热榜")
            liquidity = self._safe_float(token.get("liquidity"))
            if liquidity >= 15000:
                score += 10
                reasons.append(f"💧 深水池")

        if holders_top10 > 0:
            if holders_top10 <= 40:
                score += 15
                reasons.append(f"筹码分散")
            elif holders_top10 > config.MAX_TOP10_HOLDING:
                return -1, [f"⚠️筹码极度控盘"]

        if mcap >= config.MIN_MARKET_CAP:
            score += 5
            reasons.append(f"市值达标")

        return score, reasons

    def calculate_weighted_score(self, token: dict, audit_data: dict, smart_money: dict, trending_topics: list,
                                 is_exclusive: bool, ca: str, chain_id: str) -> tuple[int, list]:
        total_score = 0
        score_details = []

        phys_score, phys_reasons = self.calculate_physical_score(token, token.get('rank_type_tracked', 20),
                                                                 is_exclusive, ca, chain_id)
        if phys_score < 0: return -1, phys_reasons
        total_score += phys_score
        score_details.extend(phys_reasons)

        risk_level = audit_data.get("risk_level", 5)
        is_pump = str(ca).endswith('pump') and chain_id == "CT_501"
        is_four_meme = chain_id == "56" and "four" in str(token.get("source", "")).lower()

        if risk_level <= 2:
            total_score += 15
            score_details.append("✅ 审计通过")
        elif not (is_pump or is_four_meme) and risk_level >= 4:
            return -1, ["🚨 野生高危合约"]

        sm_count = smart_money.get("smartMoneyCount", 0)
        if sm_count >= 3:
            total_score += 60
            score_details.append(f"🔥 聪明钱抱团({sm_count}人)")
        elif sm_count > 0:
            total_score += sm_count * 15
            score_details.append(f"🐳 聪明钱介入")

        symbol = str(token.get("symbol", "")).upper()
        if any(topic.upper() in symbol for topic in trending_topics):
            total_score += 20
            score_details.append(f"🚀 命中叙事")

        return total_score, score_details

    def process_token_list(self, token_list: list, rank_type: int, list_name: str, trending_topics: list,
                           chain_id: str):
        if not token_list: return
        is_exclusive = (rank_type == 99)

        for token in token_list:
            try:
                ca = token.get("contractAddress")
                if not ca or ca in self.seen_tokens: continue

                # 根据传入的 chain_id 动态过滤地址格式
                if chain_id == "CT_501" and ca.startswith("0x"): continue
                if chain_id == "56" and not ca.startswith("0x"): continue

                self.stats["total_scanned"] += 1
                token['rank_type_tracked'] = rank_type
                token['chainId'] = chain_id
                symbol = token.get("symbol", "Unknown")

                phys_score, phys_reasons = self.calculate_physical_score(token, rank_type, is_exclusive, ca, chain_id)
                if phys_score < 0:
                    self.seen_tokens.add(ca)
                    continue

                audit_data = binance_api.get_token_audit(chain_id, ca)
                smart_money = binance_api.get_smart_money_info(chain_id, ca)

                total_score, score_details = self.calculate_weighted_score(token, audit_data, smart_money,
                                                                           trending_topics, is_exclusive, ca, chain_id)

                if total_score < 0:
                    self.seen_tokens.add(ca)
                    continue

                # 【锁定配置】：物理初筛最低分强制锁定为 45 分
                if total_score >= 55:
                    logging.info(f"🔍 [{chain_id}] {symbol} 资金端达标({total_score}分)，启动 Grok 金狗审计...")

                    social_info = dexscreener_api.get_token_social_info(ca)
                    token.update(social_info)
                    token['smart_money_count'] = smart_money.get("smartMoneyCount", 0)
                    token['smart_money_inflow'] = smart_money.get("smartMoneyInflow", 0.0)

                    grok_result = grok_api.analyze_meme_potential(token)
                    rating = grok_result.get("rating", "Neutral")
                    summary = grok_result.get("summary", "无")

                    final_score = total_score
                    if rating == "S":
                        final_score += 80
                    elif rating == "A":
                        final_score += 20
                    elif rating == "F":
                        final_score -= 200

                    logging.info(f"🏁 [{chain_id}] {symbol} 裁决得分: {final_score} | 评级: [{rating}] | {summary}")

                    if final_score >= 85:
                        self._execute_trade_and_notify(token, rating, final_score, summary, score_details,
                                                       config.SLIPPAGE_S_GRADE, chain_id)
                    elif final_score >= 75:
                        token['override_buy_amount'] = (
                                                           config.BUY_AMOUNT_SOL if chain_id == "CT_501" else config.BUY_AMOUNT_BNB) * 0.8
                        self._execute_trade_and_notify(token, rating, final_score, summary, score_details,
                                                       config.SLIPPAGE_A_GRADE, chain_id)

                self.seen_tokens.add(ca)
            except Exception as e:
                logging.error(f"❌ 处理代币 {token.get('symbol')} 时异常: {e}")
                continue

    def _execute_trade_and_notify(self, token, grade, score, summary, details, slippage_bps, chain_id):
        symbol = token.get("symbol")
        ca = token.get("contractAddress")

        buy_amount = token.get('override_buy_amount',
                               config.BUY_AMOUNT_SOL if chain_id == "CT_501" else config.BUY_AMOUNT_BNB)
        progress = self._safe_float(token.get("progress"))
        mcap = self._safe_float(token.get("marketCap"))
        chain_name = "Solana" if chain_id == "CT_501" else "BSC"

        msg = (
            f"👑 <b>[{chain_name}] 金狗锁定！(评分: {score})</b>\n\n"
            f"🪙 <b>代币</b>: {symbol}\n"
            f"📍 <b>CA</b>: <code>{ca}</code>\n"
            f"📈 <b>进度</b>: {progress}% | <b>市值</b>: ${mcap:,.0f}\n"
            f"💡 <b>主力动向</b>: {', '.join(details)}\n\n"
            f"🧠 <b>Grok 指令 [{grade}]</b>: {summary}\n"
        )
        if tg_bot: tg_bot.send_message(msg)
        if feishu_bot:
            feishu_bot.format_and_send_alert(token, {"rating": grade, "summary": summary})

        tx_sig = trade_engine.execute_swap(ca, "buy", chain_id, amount=buy_amount, slippage_bps=slippage_bps)

        if tx_sig and not tx_sig.startswith("sim_tx"):
            self.stats["success_sniped"] += 1
            trade_engine.start_monitor_thread(ca, symbol, buy_amount, chain_id)

    def run_scan_cycle(self):
        """核心修复：锁定双链并发扫描，不再依赖前端选链接口"""
        if not getattr(self, 'is_active', True): return

        # 直接锁定扫描目标为 Solana (CT_501) 和 BSC (56)
        active_chains = ["CT_501", "56"]

        for chain_id in active_chains:
            try:
                logging.debug(f"正在全自动扫描网络: {chain_id}...")
                trending_topics = binance_api.get_trending_topics(chain_id)

                # 1. DexScreener 雷达
                dex_tokens = dexscreener_api.get_latest_safe_pairs(chain_id)
                self.process_token_list(dex_tokens, 88, f"DexScreener({chain_id})", trending_topics, chain_id)

                # 2. 官方高潜榜
                exclusive_tokens = binance_api.get_exclusive_memes(chain_id=chain_id)
                self.process_token_list(exclusive_tokens, 99, f"Exclusive({chain_id})", trending_topics, chain_id)

                # 3. 基础榜单 (Rank 20 / 10)
                for rank in [20, 10]:
                    memes = binance_api.get_memes(chain_id=chain_id, rank_type=rank)
                    self.process_token_list(memes, rank, f"Rank{rank}({chain_id})", trending_topics, chain_id)

            except Exception as e:
                logging.error(f"扫描网络 [{chain_id}] 周期异常: {e}")


sniper_engine = SniperEngine()