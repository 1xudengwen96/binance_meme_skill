import time
import logging
import threading
import requests
import base64
import base58
from config import config

# 引入 Solana 核心库 (需确保已安装 solders 和 solana)
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client

# 兼容原有的推送
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
    Solana 极速交易引擎 - 猎人实战版
    集成 Jupiter V6 真实签名上链与自动化防守
    """

    def __init__(self):
        self.rpc_url = config.SOL_RPC_URL
        self.private_key = config.SOL_PRIVATE_KEY
        self.jupiter_quote_api = "https://quote-api.jup.ag/v6/quote"
        self.jupiter_swap_api = "https://quote-api.jup.ag/v6/swap"
        self.WSOL = "So11111111111111111111111111111111111111112"
        self.defense_count = 0

        # 初始化 Solana 客户端与密钥对
        self.client = Client(self.rpc_url)
        try:
            if self.private_key:
                # 解析 phantom/solflare 导出的 base58 格式私钥
                self.keypair = Keypair.from_base58_string(self.private_key)
                self.pubkey = str(self.keypair.pubkey())
                logging.info(f"✅ 交易钱包已挂载: {self.pubkey}")
            else:
                self.keypair = None
                logging.warning("⚠️ 未检测到 SOL_PRIVATE_KEY，将以模拟模式运行")
        except Exception as e:
            logging.error(f"❌ 私钥解析失败，请检查 .env 文件: {e}")
            self.keypair = None

    def execute_swap(self, token_address: str, action="buy", amount_sol=None, slippage_bps=None) -> str:
        """
        执行真实的 Solana Swap 交易
        """
        if not self.keypair:
            logging.warning(f"⚠️ [模拟模式] 模拟 {action} {token_address}")
            return f"sim_tx_{int(time.time())}"

        try:
            # 1. 设置买卖方向
            if action == "buy":
                in_mint, out_mint = self.WSOL, token_address
                amount = int((amount_sol or config.BUY_AMOUNT_SOL) * 1e9)
            else:
                in_mint, out_mint = token_address, self.WSOL
                # 卖出逻辑通常需要查询代币余额，此处简化为全仓或指定 lamports
                amount = int(amount_sol) if amount_sol else 0

                # 2. 获取 Jupiter 报价
            slippage = slippage_bps or config.SLIPPAGE_DEFAULT
            quote_res = requests.get(
                f"{self.jupiter_quote_api}?inputMint={in_mint}&outputMint={out_mint}&amount={amount}&slippageBps={slippage}",
                timeout=10
            ).json()

            if "error" in quote_res:
                logging.error(f"❌ 报价获取失败: {quote_res['error']}")
                return None

            # 3. 获取交易体 (Serialized Transaction)
            priority_fee = int(config.SOL_PRIORITY_FEE * 1e9)
            swap_res = requests.post(
                self.jupiter_swap_api,
                json={
                    "quoteResponse": quote_res,
                    "userPublicKey": self.pubkey,
                    "wrapAndUnwrapSol": True,
                    "prioritizationFeeLamports": priority_fee
                },
                timeout=10
            ).json()

            if "swapTransaction" not in swap_res:
                logging.error(f"❌ 无法构建交易体: {swap_res}")
                return None

            # 4. 签名并发送
            raw_tx = base64.b64decode(swap_res["swapTransaction"])
            tx = VersionedTransaction.from_bytes(raw_tx)
            signature = self.keypair.sign_message(tx.message())
            signed_tx = VersionedTransaction(tx.message(), [signature])

            # 发送原始交易
            res = self.client.send_raw_transaction(bytes(signed_tx))
            tx_sig = str(res.value)

            logging.info(f"🚀 [交易上链] {action} 成功! 签名: {tx_sig}")
            return tx_sig

        except Exception as e:
            logging.error(f"❌ 交易执行崩溃: {e}")
            return None

    def start_monitor_thread(self, ca, symbol, entry_sol):
        t = threading.Thread(target=self._monitor, args=(ca, symbol, entry_sol), daemon=True)
        t.start()

    def _monitor(self, ca, symbol, entry_sol):
        stop_loss = -0.20
        take_profit = 1.00
        entry_price = self._get_price(ca)
        if not entry_price: return

        while True:
            time.sleep(10)
            curr_price = self._get_price(ca)
            if not curr_price: continue
            roi = (curr_price - entry_price) / entry_price

            if roi <= stop_loss:
                logging.warning(f"🚨 {symbol} 触发止损!")
                self.execute_swap(ca, "sell", slippage_bps=2500)
                self.defense_count += 1
                break
            if roi >= take_profit:
                logging.info(f"🎉 {symbol} 翻倍抽本!")
                self.execute_swap(ca, "sell", slippage_bps=1500)
                self.defense_count += 1
                break

    def _get_price(self, ca):
        try:
            return float(requests.get(f"https://price.jup.ag/v4/price?ids={ca}").json()["data"][ca]["price"])
        except:
            return 0.0

    def _notify(self, msg):
        if tg_bot: tg_bot.send_message(msg)


trade_engine = TradeEngine()