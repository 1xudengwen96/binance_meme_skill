import time
import logging
from config import config
from binance_api import binance_api
from grok_api import grok_api
from trade_engine import trade_engine
from feishu_bot import feishu_bot

# 兼容原有的 TG Bot
try:
    from tg_bot import send_tg_message
except ImportError:
    send_tg_message = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SniperEngine:
    """
    加权评分制 Meme 狙击引擎 (V3 实战版)
    已优化安全评分逻辑：针对 Pump.fun 等平台币提供原生安全信任加分
    """

    def __init__(self):
        self.chain_id = config.TARGET_CHAIN_ID
        self.seen_tokens = set()
        self.is_active = True  # 控制引擎是否处于工作状态的开关，默认启动

    def set_active_state(self, state: bool):
        """
        供外部(如 API 接口/前端)调用的启停控制方法
        """
        self.is_active = state
        if state:
            logging.info("▶️ [状态切换] 引擎已唤醒，猎犬出笼，恢复打狗！")
        else:
            logging.info("⏸️ [状态切换] 引擎已暂停，进入休息状态。")

    def _safe_float(self, value, default=0.0):
        """安全转换 float，处理 NoneType 异常"""
        try:
            if value is None:
                return default
            return float(value)
        except (ValueError, TypeError):
            return default

    def calculate_physical_score(self, token: dict, rank_type: int) -> tuple[int, list]:
        """
        计算物理基础分 (满分 40)
        """
        score = 0
        reasons = []

        symbol = token.get("symbol", "Unknown")
        protocol = token.get("protocol")

        # 1. 协议白名单 (硬性过滤)
        if protocol not in [1001, 2001]:
            return -1, [f"非目标协议({protocol})"]

        # 安全读取数值
        progress = self._safe_float(token.get("progress"))
        holders_top10 = self._safe_float(token.get("holdersTop10Percent"), default=100.0)
        dev_sell = self._safe_float(token.get("devSellPercent"))
        mcap = self._safe_float(token.get("marketCap"))

        # 2. 进度得分 (10分)
        if rank_type == 10 and progress >= 40:
            score += 10
            reasons.append(f"新币进度良好({progress}%)")
        elif rank_type == 20 and progress >= 70:
            score += 10
            reasons.append(f"打满埋伏区({progress}%)")
        elif rank_type == 30:
            score += 10
            reasons.append("已迁移(进度满分)")

        # 3. 筹码集中度得分 (20分)
        if holders_top10 <= 35:
            score += 20
            reasons.append(f"筹码极其分散({holders_top10:.1f}%)")
        elif holders_top10 <= config.MAX_TOP10_HOLDING:
            score += 10
            reasons.append(f"筹码正常集中({holders_top10:.1f}%)")
        else:
            reasons.append(f"⚠️筹码过度集中({holders_top10:.1f}%)")

        # 4. 开发者风险与市值 (10分)
        if mcap >= config.MIN_MARKET_CAP:
            score += 5
            reasons.append(f"市值达标(${mcap:,.0f})")

        if dev_sell < config.MAX_DEV_SELL or token.get("devPosition") != 2:
            score += 5
            reasons.append(f"开发者未清仓")
        else:
            reasons.append(f"⚠️开发者已离场")

        return score, reasons

    def calculate_weighted_score(self, token: dict, audit_data: dict, smart_money: dict, trending_topics: list) -> \
    tuple[int, list]:
        """综合加权评分系统"""
        total_score = 0
        score_details = []

        # 1. 物理基础分 (最高 40)
        phys_score, phys_reasons = self.calculate_physical_score(token, token.get('rank_type_tracked', 20))
        if phys_score < 0: return -1, phys_reasons
        total_score += phys_score
        score_details.extend(phys_reasons)

        # 2. 深度安全分
        risk_level = audit_data.get("risk_level", 5)
        protocol = token.get("protocol")

        if risk_level == 1:
            total_score += 20
            score_details.append("安全评级:极低风险")
        elif risk_level == 2:
            total_score += 10
            score_details.append("安全评级:低风险")
        elif risk_level >= 4:
            # 针对 Pump.fun / Four.meme 机制信任加分
            if protocol in [1001, 2001]:
                # 不扣分，反而给予 5 分信任分，因为平台机制已规避了合约后门
                total_score += 5
                score_details.append("🛡️ 平台原生安全 (Pump/Four 机制保护)")
            else:
                # 只有非平台托管的野生代币，才执行高风险拦截
                return -1, ["🚨 非平台合约: 高风险拦截"]

        # 3. 聪明钱雷达 (最高 20)
        sm_count = smart_money.get("smartMoneyCount", 0)
        if sm_count >= 5:
            total_score += 20
            score_details.append(f"🔥 聪明钱扎堆({sm_count}个)")
        elif sm_count >= 2:
            total_score += 10
            score_details.append(f"聪明钱流入({sm_count}个)")

        # 4. 叙事共振分 (最高 20)
        symbol = str(token.get("symbol", "")).upper()
        if any(topic.upper() in symbol or symbol in topic.upper() for topic in trending_topics):
            total_score += 20
            score_details.append(f"🚀 命中热门叙事")

        return total_score, score_details

    def process_token_list(self, token_list: list, rank_type: int, list_name: str, trending_topics: list):
        if not token_list: return

        for token in token_list:
            try:
                ca = token.get("contractAddress")
                if not ca or ca in self.seen_tokens: continue

                token['rank_type_tracked'] = rank_type
                symbol = token.get("symbol", "Unknown")

                # 【阶段一】本地物理初筛
                phys_score, _ = self.calculate_physical_score(token, rank_type)
                if phys_score < 10:
                    self.seen_tokens.add(ca)
                    continue

                logging.info(f"🔍 发现潜力目标 [{list_name}]: {symbol} ({ca[:6]}...) | 初筛通过，深度审计中...")

                # 【阶段二】深度数据聚合
                audit_data = binance_api.get_token_audit(self.chain_id, ca)
                smart_money = binance_api.get_smart_money_info(self.chain_id, ca)

                # 计算综合评分
                total_score, score_details = self.calculate_weighted_score(token, audit_data, smart_money,
                                                                           trending_topics)

                if total_score < 0:
                    logging.warning(f"🚫 {symbol} 过滤原因: {', '.join(score_details)}")
                    self.seen_tokens.add(ca)
                    continue

                # 【阶段三】Grok 社交大脑终审
                logging.info(f"📊 {symbol} 综合评分: {total_score} | 详情: {', '.join(score_details)}")

                if total_score >= config.GROK_SCORE_THRESHOLD:
                    logging.info(f"🧠 {symbol} 达标(>={config.GROK_SCORE_THRESHOLD})，呼叫 Grok 分析...")
                    grok_result = grok_api.analyze_meme_potential(token)
                    rating = grok_result.get("rating", "F")
                    summary = grok_result.get("summary", "无")

                    final_score = total_score
                    if rating == "S":
                        final_score += 30
                    elif rating == "A":
                        final_score += 15
                    elif rating == "F":
                        final_score -= 50

                    logging.info(f"🏁 {symbol} 最终得分: {final_score} (含Grok) | 评级: {rating}")

                    if final_score >= 85:
                        self._execute_trade_and_notify(token, "S", final_score, summary, score_details,
                                                       config.SLIPPAGE_S_GRADE)
                    elif final_score >= 65:
                        token['override_buy_amount'] = config.BUY_AMOUNT_SOL * 0.5
                        self._execute_trade_and_notify(token, "A", final_score, summary, score_details,
                                                       config.SLIPPAGE_A_GRADE)
                    else:
                        logging.info(f"📉 {symbol} 最终得分不足 ({final_score})")

                else:
                    logging.info(f"💤 {symbol} 评分({total_score})未达标，不调用 Grok")

                self.seen_tokens.add(ca)
            except Exception as e:
                logging.error(f"❌ 处理代币时发生非预期异常: {e}")
                continue

    def _execute_trade_and_notify(self, token, grade, score, summary, details, slippage_bps):
        symbol = token.get("symbol")
        ca = token.get("contractAddress")
        buy_amount = token.get('override_buy_amount', config.BUY_AMOUNT_SOL)

        msg = (
            f"🎯 <b>发现 {grade} 级目标！(评分: {score})</b>\n\n"
            f"🪙 <b>代币</b>: {symbol}\n"
            f"📍 <b>CA</b>: <code>{ca}</code>\n"
            f"📈 <b>进度</b>: {token.get('progress')}% | <b>市值</b>: ${float(token.get('marketCap', 0) or 0):,.0f}\n"
            f"💡 <b>得分亮点</b>: {', '.join(details)}\n\n"
            f"🧠 <b>Grok 洞察</b>: {summary}\n\n"
            f"⚡ 准备执行买入: {buy_amount} SOL"
        )

        logging.info(f"🚀 准备买入 {symbol} | 评级 {grade}")

        if feishu_bot.webhook_url and "feishu" in feishu_bot.webhook_url:
            feishu_bot.send_text(
                msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""))
        elif send_tg_message:
            send_tg_message(msg)

        tx_sig = trade_engine.execute_swap(ca, "buy", amount_sol=buy_amount, slippage_bps=slippage_bps)

        if tx_sig:
            success_msg = f"✅ <b>买入成功!</b>\n代币: {symbol}\nTx: <code>{tx_sig}</code>"
            if feishu_bot.webhook_url:
                feishu_bot.send_text(success_msg.replace("<b>", "").replace("</b>", ""))
            elif send_tg_message:
                send_tg_message(success_msg)

            logging.info(f"🛡️ 为 {symbol} 挂载自动防守雷达...")
            trade_engine.start_monitor_thread(ca, symbol, buy_amount)
        else:
            logging.error(f"❌ {symbol} 买入失败")

    def run_scan_cycle(self):
        if not getattr(self, 'is_active', True):
            logging.info("💤 引擎休息中...")
            return

        logging.info("🌍 同步大盘叙事...")
        trending_topics = binance_api.get_trending_topics(self.chain_id)

        logging.info(f"⚡ 扫描轨道: {self.chain_id} [Finalizing]...")
        final_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=20)
        self.process_token_list(final_tokens, 20, "打满榜", trending_topics)

        logging.info(f"👶 扫描轨道: {self.chain_id} [New]...")
        new_tokens = binance_api.get_memes(chain_id=self.chain_id, rank_type=10)
        self.process_token_list(new_tokens, 10, "新币榜", trending_topics)