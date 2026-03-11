import time
import logging
import threading
import requests
import base64
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
    增强版：自带高可用节点矩阵，免疫 AWS/云端单点 DNS 瘫痪 ([Errno -5])
    """

    def __init__(self):
        self.rpc_url = config.SOL_RPC_URL
        self.private_key = config.SOL_PRIVATE_KEY

        # [核心修复] 建立高可用节点池。即使 AWS 解析不了 quote-api，也能秒切备用节点
        self.quote_endpoints = [
            "https://quote-api.jup.ag/v6/quote",
            "https://api.jup.ag/swap/v1/quote"
        ]
        self.swap_endpoints = [
            "https://quote-api.jup.ag/v6/swap",
            "https://api.jup.ag/swap/v1/swap"
        ]
        self.WSOL = "So11111111111111111111111111111111111111112"
        self.defense_count = 0

        # 初始化 Session (底层 TCP 连接复用，比每次 request.get 快 30% 以上)
        self.session = requests.Session()

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
        执行真实的 Solana Swap 交易 (带高可用节点切换)
        """
        if not self.keypair:
            logging.warning(f"⚠️ [模拟模式] 模拟 {action} {token_address}")
            return f"sim_tx_{int(time.time())}"

        # 1. 设置买卖方向
        if action == "buy":
            in_mint, out_mint = self.WSOL, token_address
            amount = int((amount_sol or config.BUY_AMOUNT_SOL) * 1e9)
        else:
            in_mint, out_mint = token_address, self.WSOL
            amount = int(amount_sol) if amount_sol else 0

        slippage = slippage_bps or config.SLIPPAGE_DEFAULT

        # ==========================================
        # 2. 🛡️ 节点防瘫痪轮询逻辑获取报价
        # ==========================================
        quote_res = None
        used_index = 0

        for i, quote_api in enumerate(self.quote_endpoints):
            try:
                url = f"{quote_api}?inputMint={in_mint}&outputMint={out_mint}&amount={amount}&slippageBps={slippage}"
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                quote_res = resp.json()

                if "error" not in quote_res:
                    used_index = i
                    break  # 成功拿到报价，跳出循环
                else:
                    logging.warning(f"⚠️ 节点 {quote_api} 返回错误: {quote_res['error']}")
            except requests.exceptions.ConnectionError as e:
                # 捕获 Errno -5 DNS 错误，不崩溃，直接尝试下一个节点
                logging.warning(f"⚠️ 节点 {quote_api} 连接失败(DNS可能被墙)，正在切换备用节点...")
            except Exception as e:
                logging.warning(f"⚠️ 节点 {quote_api} 异常: {e}")

        if not quote_res or "error" in quote_res:
            logging.error(f"❌ 所有 Jupiter 节点报价获取均失败！请检查 AWS 的 DNS 配置！")
            return None

        # 3. 获取交易体 (Serialized Transaction)
        swap_api = self.swap_endpoints[used_index]
        priority_fee = int(config.SOL_PRIORITY_FEE * 1e9)
        swap_res = None

        try:
            resp = self.session.post(
                swap_api,
                json={
                    "quoteResponse": quote_res,
                    "userPublicKey": self.pubkey,
                    "wrapAndUnwrapSol": True,
                    "prioritizationFeeLamports": priority_fee
                },
                timeout=10
            )
            resp.raise_for_status()
            swap_res = resp.json()
        except Exception as e:
            logging.error(f"❌ 无法构建交易体 (节点: {swap_api}): {e}")
            return None

        if not swap_res or "swapTransaction" not in swap_res:
            logging.error(f"❌ 交易体解析失败: {swap_res}")
            return None

        # 4. 签名并发送
        try:
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
            logging.error(f"❌ 交易执行与签名崩溃: {e}")
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
            res = self.session.get(f"https://price.jup.ag/v4/price?ids={ca}", timeout=10).json()
            return float(res["data"][ca]["price"])
        except:
            return 0.0

    def _notify(self, msg):
        if tg_bot: tg_bot.send_message(msg)


trade_engine = TradeEngine()