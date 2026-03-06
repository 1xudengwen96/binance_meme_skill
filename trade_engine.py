import base64
import logging
import time
import requests
import json
import base58
import threading
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TradeEngine:
    """
    Solana 极速狙击与风控引擎 (Jupiter V6 接入)
    具备: 极速抢跑、自动余额追踪、翻倍抽本、动态追踪止损(Trailing Stop)
    """

    def __init__(self):
        self.rpc_url = config.SOL_RPC_URL
        self.client = Client(self.rpc_url)
        self.private_key = config.SOL_PRIVATE_KEY
        self.keypair = None

        # 统一钱包加载逻辑
        if self.private_key:
            try:
                if self.private_key.startswith('['):
                    secret = json.loads(self.private_key)
                    self.keypair = Keypair.from_bytes(bytes(secret))
                else:
                    self.keypair = Keypair.from_bytes(base58.b58decode(self.private_key))
                logging.info(f"✅ [TradeEngine] 钱包已加载，公钥: {self.keypair.pubkey()}")
            except Exception as e:
                logging.error(f"⚠️ [TradeEngine] 私钥解析失败，请检查 .env。当前处于【模拟模式】。错误: {e}")

        # W-SOL 合约地址
        self.wsol = "So11111111111111111111111111111111111111112"

    def get_token_balance(self, token_address: str) -> int:
        """获取钱包中指定代币的真实余额 (最小单位)"""
        if not self.keypair: return 0
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    str(self.keypair.pubkey()),
                    {"mint": token_address},
                    {"encoding": "jsonParsed"}
                ]
            }
            resp = requests.post(self.rpc_url, json=payload, timeout=10).json()
            accounts = resp.get("result", {}).get("value", [])
            if not accounts: return 0

            amount_str = accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]
            return int(amount_str)
        except Exception as e:
            logging.error(f"❌ [TradeEngine] 获取余额失败: {e}")
            return 0

    def execute_swap(self, token_address: str, action: str = "buy", amount_sol: float = None, slippage_bps: int = None,
                     sell_percentage: int = 100) -> str:
        """执行 Swap 操作 (极限压缩上链时间)"""
        if not self.keypair:
            logging.warning(f"🛑 [模拟模式] 拦截 {action} 交易 -> 代币: {token_address}")
            return "simulated_tx_signature_123456789"

        if slippage_bps is None: slippage_bps = config.SLIPPAGE_DEFAULT

        if action == "buy":
            amount_sol = amount_sol or config.BUY_AMOUNT_SOL
            trade_amount = int(amount_sol * 1e9)
            input_mint, output_mint = self.wsol, token_address
        else:
            total_token_amount = self.get_token_balance(token_address)
            if total_token_amount <= 0: return None
            trade_amount = int(total_token_amount * (sell_percentage / 100.0))
            if trade_amount <= 0: return None
            input_mint, output_mint = token_address, self.wsol

        priority_fee_lamports = int(config.SOL_PRIORITY_FEE * 1e9)

        try:
            # 1. 获取报价
            quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={trade_amount}&slippageBps={slippage_bps}"
            quote_resp = requests.get(quote_url, timeout=10).json()
            if "error" in quote_resp: return None

            # 2. 构造带优先费的交易
            swap_url = "https://quote-api.jup.ag/v6/swap"
            payload = {
                "quoteResponse": quote_resp,
                "userPublicKey": str(self.keypair.pubkey()),
                "wrapAndUnwrapSol": True,
                "prioritizationFeeLamports": priority_fee_lamports
            }
            swap_resp = requests.post(swap_url, json=payload, timeout=15).json()
            if "error" in swap_resp: return None

            # 3. 签名并跳过预检广播 (skip_preflight=True)
            tx_bytes = base64.b64decode(swap_resp["swapTransaction"])
            tx = VersionedTransaction.from_bytes(tx_bytes)
            signed_tx = VersionedTransaction(tx.message, [self.keypair])

            result = self.client.send_raw_transaction(bytes(signed_tx), opts={"skip_preflight": True, "max_retries": 3})
            logging.info(f"✅ [Solana] {action.upper()} 交易已极速广播! 签名: {result.value}")
            return str(result.value)

        except Exception as e:
            logging.error(f"❌ [TradeEngine] 交易执行异常: {e}")
            return None

    # ==========================
    # 实战风控宏与后台雷达
    # ==========================
    def sell_panic(self, token_address: str) -> str:
        logging.warning(f"🚨 触发恐慌清仓! 不计成本卖出: {token_address}")
        return self.execute_swap(token_address, action="sell", slippage_bps=2000, sell_percentage=100)

    def sell_half_for_profit(self, token_address: str) -> str:
        logging.info(f"💰 触发翻倍抽本! 卖出 50% 仓位锁定利润: {token_address}")
        return self.execute_swap(token_address, action="sell", slippage_bps=1000, sell_percentage=50)

    def _monitor_position(self, token_address: str, symbol: str, cost_sol: float):
        """后台死盯逻辑：保护利润，隔绝深套"""
        cost_lamports = int(cost_sol * 1e9)
        logging.info(f"👀 [雷达] 开启 {symbol} 战术监控 | 成本: {cost_sol} SOL")

        # 1. 确认代币到账 (防链上拥堵延迟)
        balance = 0
        for _ in range(12):  # 最多等 60 秒
            balance = self.get_token_balance(token_address)
            if balance > 0: break
            time.sleep(5)

        if balance <= 0:
            logging.error(f"❌ [雷达] {symbol} 迟迟未确认到账，监控终止。")
            return

        logging.info(f"✅ [雷达] {symbol} 代币已确认入库，进入防守模式...")

        # 核心战术参数
        stop_loss_pct = -0.30  # 铁血止损线: 跌 30% 砍仓
        take_profit_pct = 1.00  # 翻倍抽本线: 涨 100% 卖半仓
        trailing_activation = 0.40  # 追踪止损激活线: 涨 40% 激活
        trailing_stop_pct = 0.15  # 追踪保本线: 锁定至少 15% 利润

        max_pnl_pct = 0.0  # 记录历史最高盈亏比
        is_moonbag = False  # 是否已经是抽本后的零成本底仓

        while True:
            try:
                time.sleep(4)  # 每4秒查一次 Jupiter 报价

                current_balance = self.get_token_balance(token_address)
                if current_balance <= 0:
                    logging.info(f"🛑 [雷达] {symbol} 余额已归零，自动销毁监控线程。")
                    break

                quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={token_address}&outputMint={self.wsol}&amount={current_balance}&slippageBps=100"
                resp = requests.get(quote_url, timeout=5).json()
                if "error" in resp: continue

                current_value = int(resp.get("outAmount", 0))

                # 如果已经是格局仓，盈亏比计算基准改变，只要不跌破防线就一直拿
                if is_moonbag:
                    pnl_pct = (current_value - cost_lamports) / cost_lamports if cost_lamports > 0 else 0
                else:
                    pnl_pct = (current_value - cost_lamports) / cost_lamports

                if pnl_pct > max_pnl_pct: max_pnl_pct = pnl_pct

                # 计算动态止损线：如果曾涨超40%，止损线上移到+15%；否则维持-30%
                curr_stop = trailing_stop_pct if (
                            max_pnl_pct >= trailing_activation and not is_moonbag) else stop_loss_pct

                status_icon = "🟢" if pnl_pct > 0 else "🔴"
                logging.info(
                    f"📊 [雷达-{symbol}] 估值: {current_value / 1e9:.4f} SOL | 浮动盈亏: {status_icon} {pnl_pct * 100:.1f}% (最高: {max_pnl_pct * 100:.1f}%) | 触发线: {curr_stop * 100:.1f}%")

                # 执行防守反击
                if pnl_pct <= curr_stop:
                    reason = "追踪止损(保利润)" if max_pnl_pct >= trailing_activation else "硬止损(断臂求生)"
                    logging.warning(f"🚨 [雷达] {symbol} 击穿防线，触发 {reason}，立刻清仓！")
                    self.sell_panic(token_address)
                    break

                elif pnl_pct >= take_profit_pct and not is_moonbag:
                    logging.info(f"🚀 [雷达] {symbol} 达成翻倍 (+{pnl_pct * 100:.1f}%)! 自动抽本...")
                    self.sell_half_for_profit(token_address)
                    # 转化为 Moonbag 格局模式
                    is_moonbag = True
                    cost_lamports = current_value // 2  # 重新设定锚点
                    max_pnl_pct = 0
                    stop_loss_pct = -0.40  # 格局仓容忍 40% 波动
                    logging.info(f"🛡️ [雷达] {symbol} 本金已安全撤出！剩余免费筹码将持续格局监控...")

            except Exception as e:
                logging.error(f"⚠️ [雷达] 巡逻异常: {e}")
                time.sleep(3)

    def start_monitor_thread(self, token_address: str, symbol: str, cost_sol: float):
        """挂载后台雷达线程 (非阻塞)"""
        t = threading.Thread(target=self._monitor_position, args=(token_address, symbol, cost_sol))
        t.daemon = True
        t.start()


# 实例化引擎单例
trade_engine = TradeEngine()