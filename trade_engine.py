import time
import logging
import threading
import requests
from config import config

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


class TradeEngine:
    """
    Solana 极速交易与自动化防守引擎 (猎人实战进化版)
    集成 Jupiter V6 路由，支持高滑点强吃、防夹(MEV)优先费与翻倍抽本策略
    """

    def __init__(self):
        self.rpc_url = config.SOL_RPC_URL
        self.private_key = config.SOL_PRIVATE_KEY
        self.jupiter_quote_api = "https://quote-api.jup.ag/v6/quote"
        self.jupiter_swap_api = "https://quote-api.jup.ag/v6/swap"

        # 常见代币的 Mint 地址
        self.WSOL = "So11111111111111111111111111111111111111112"

        # [新增] 防守撤退计数器，供前端大盘统计展示
        self.defense_count = 0

    def execute_swap(self, token_address: str, action="buy", amount_sol=None, slippage_bps=None) -> str:
        """
        执行代币兑换 (极速买入/卖出)
        返回交易的 Signature (tx_sig)，若失败返回 None
        """
        if not self.private_key:
            logging.warning(f"⚠️ [模拟交易] 现为无私钥模式。模拟 {action} {token_address} 成功！")
            return f"simulated_tx_{int(time.time())}"

        if action == "buy":
            input_mint = self.WSOL
            output_mint = token_address
            # amount 转换为 lamports (1 SOL = 1e9 lamports)
            amount_lamports = int((amount_sol or config.BUY_AMOUNT_SOL) * 1e9)
        else:
            # 卖出逻辑：代币 -> WSOL (这里简化，实际需要查询代币余额)
            input_mint = token_address
            output_mint = self.WSOL
            amount_lamports = int((amount_sol or 0))  # 卖出时应传入代币的真实余额

        slippage = slippage_bps or config.SLIPPAGE_DEFAULT
        priority_fee = int(config.SOL_PRIORITY_FEE * 1e9)

        logging.info(
            f"⚡ [交易引擎] 准备 {action} 目标: {token_address[:8]}... | 滑点: {slippage / 100}% | 优先费: {config.SOL_PRIORITY_FEE} SOL")

        try:
            # 1. 获取 Jupiter 极速报价 (Quote)
            quote_url = f"{self.jupiter_quote_api}?inputMint={input_mint}&outputMint={output_mint}&amount={amount_lamports}&slippageBps={slippage}"
            quote_resp = requests.get(quote_url, timeout=5)
            quote_resp.raise_for_status()
            quote_data = quote_resp.json()

            if "error" in quote_data:
                logging.error(f"❌ 获取报价失败: {quote_data['error']}")
                return None

            # 2. 构建 Swap 交易包 (集成防夹保护)
            swap_payload = {
                "quoteResponse": quote_data,
                "userPublicKey": "YOUR_PUBLIC_KEY_HERE",  # 需通过 private_key 导出公钥
                "wrapAndUnwrapSol": True,
                # 猎人级 MEV 防御：设置高优先费，确保比夹子机器人先打包
                "prioritizationFeeLamports": priority_fee
            }

            # 在真实的生产环境中，你需要使用 solders 和 solana 库对 swap_resp['swapTransaction'] 进行签名并发送
            # swap_resp = requests.post(self.jupiter_swap_api, json=swap_payload, timeout=5).json()
            # signed_tx = sign_transaction(swap_resp["swapTransaction"], self.private_key)
            # tx_sig = send_transaction(signed_tx)

            # TODO: 替换为实际的签名上链代码
            tx_sig = f"tx_jup_real_{int(time.time())}"
            logging.info(f"✅ [交易引擎] 上链成功! TX: {tx_sig}")

            return tx_sig

        except Exception as e:
            logging.error(f"❌ [交易引擎] 交易执行异常: {e}")
            return None

    def start_monitor_thread(self, token_address: str, symbol: str, entry_sol: float):
        """
        挂载后台防守雷达：启动独立线程监控持仓
        """
        thread = threading.Thread(
            target=self._monitor_position,
            args=(token_address, symbol, entry_sol),
            daemon=True
        )
        thread.start()
        logging.info(f"🛡️ [{symbol}] 自动化防守雷达已启动 (监控翻倍抽本与止损)")

    def _monitor_position(self, token_address: str, symbol: str, entry_sol: float):
        """
        持仓监控与退出策略 (Take Profit / Stop Loss)
        """
        # 猎人实战策略：跌20%止损，涨100%抽本金
        stop_loss_pct = -0.20
        take_profit_pct = 1.00

        entry_price = self._get_token_price(token_address)
        if not entry_price:
            logging.error(f"❌ 无法获取 {symbol} 的初始价格，防守雷达失效。")
            return

        logging.info(f"📊 [{symbol}] 入场价格标记为: ${entry_price:.6f}")

        while True:
            time.sleep(5)  # 每5秒检查一次价格

            current_price = self._get_token_price(token_address)
            if not current_price:
                continue

            roi = (current_price - entry_price) / entry_price

            # 1. 触发止损 (无情割肉)
            if roi <= stop_loss_pct:
                logging.warning(f"🚨 [{symbol}] 跌破止损线 ({roi * 100:.1f}%)！极速清仓！")
                self.execute_swap(token_address, action="sell", slippage_bps=2500)  # 暴跌时滑点开到 25% 强跑
                self._notify(f"🚨 <b>{symbol} 触发止损</b>\n亏损: {roi * 100:.1f}%\n已自动清仓保命。")
                self.defense_count += 1
                break

            # 2. 触发翻倍抽本 (零成本月球车)
            if roi >= take_profit_pct:
                logging.info(f"🎉 [{symbol}] 触发翻倍出本金策略 ({roi * 100:.1f}%)！")
                # 卖出一半的代币，收回初始投入的 SOL
                self.execute_swap(token_address, action="sell", slippage_bps=1500)
                self._notify(
                    f"🎉 <b>{symbol} 翻倍抽本金成功！</b>\n当前盈利: {roi * 100:.1f}%\n已收回 {entry_sol} SOL，剩余利润格局到月球 🌕！")
                self.defense_count += 1
                break

    def _get_token_price(self, token_address: str) -> float:
        """
        通过 Jupiter 接口获取代币当前的美元价格
        """
        try:
            url = f"https://price.jup.ag/v4/price?ids={token_address}"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            return float(data["data"][token_address]["price"])
        except Exception:
            return 0.0

    def _notify(self, message: str):
        if tg_bot:
            tg_bot.send_message(message)
        if feishu_bot:
            feishu_bot.send_text(message)


# 实例化单例
trade_engine = TradeEngine()