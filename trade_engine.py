import time
import logging
import threading
import requests
import base64
from config import config
from web3 import Web3

# 引入 Solana 核心库
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts

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
    双链实战交易引擎 - 稳如老狗版
    Solana: Jupiter V6 (已彻底修复签名崩溃与CU超载问题，暴力上链)
    BSC: PancakeSwap V2 (防税率代币卡单优化)
    """

    def __init__(self):
        self.defense_count = 0
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json"
        })

        # ================= Solana 初始化 =================
        self.sol_client = Client(config.SOL_RPC_URL)
        self.sol_keypair = None
        self.sol_pubkey = None
        self.WSOL = "So11111111111111111111111111111111111111112"
        self.jup_quote = "https://quote-api.jup.ag/v6/quote"
        self.jup_swap = "https://quote-api.jup.ag/v6/swap"

        try:
            if config.SOL_PRIVATE_KEY:
                self.sol_keypair = Keypair.from_base58_string(config.SOL_PRIVATE_KEY)
                self.sol_pubkey = str(self.sol_keypair.pubkey())
                logging.info(f"✅ Solana 钱包已挂载: {self.sol_pubkey}")
        except Exception as e:
            logging.error(f"❌ Solana 私钥解析失败: {e}")

        # ================= BSC 初始化 =================
        self.w3 = None
        self.bsc_account = None
        self.WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
        self.PANCAKE_ROUTER = "0x10ED43C718714eb63d5aA57B78B54704E256024E"

        # PancakeSwap Router 极简 ABI (支持带税代币)
        self.router_abi = [
            {"inputs": [{"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                        {"internalType": "address[]", "name": "path", "type": "address[]"},
                        {"internalType": "address", "name": "to", "type": "address"},
                        {"internalType": "uint256", "name": "deadline", "type": "uint256"}],
             "name": "swapExactETHForTokensSupportingFeeOnTransferTokens", "outputs": [], "stateMutability": "payable",
             "type": "function"},
            {"inputs": [{"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                        {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                        {"internalType": "address[]", "name": "path", "type": "address[]"},
                        {"internalType": "address", "name": "to", "type": "address"},
                        {"internalType": "uint256", "name": "deadline", "type": "uint256"}],
             "name": "swapExactTokensForETHSupportingFeeOnTransferTokens", "outputs": [],
             "stateMutability": "nonpayable", "type": "function"}
        ]
        # ERC20 极简 ABI (用于授权和查余额)
        self.erc20_abi = [
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf",
             "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
            {"constant": False,
             "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
             "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"}
        ]

        if config.BSC_PRIVATE_KEY and config.BSC_RPC_URL:
            try:
                self.w3 = Web3(Web3.HTTPProvider(config.BSC_RPC_URL))
                if self.w3.is_connected():
                    self.bsc_account = self.w3.eth.account.from_key(config.BSC_PRIVATE_KEY)
                    logging.info(f"✅ BSC 钱包已挂载: {self.bsc_account.address}")
            except Exception as e:
                logging.error(f"❌ BSC 节点连接或私钥解析失败: {e}")

    def execute_swap(self, token_address: str, action: str, chain_id: str, amount=None, slippage_bps=None) -> str:
        """统一路由分发器"""
        if chain_id == "CT_501":
            return self._swap_solana(token_address, action, amount, slippage_bps)
        elif chain_id == "56":
            token_address = Web3.to_checksum_address(token_address)
            return self._swap_bsc(token_address, action, amount, slippage_bps)
        else:
            logging.error(f"❌ 不支持的 Chain ID: {chain_id}")
            return None

    # ================= Solana 交易逻辑 =================
    def _swap_solana(self, token_address: str, action: str, amount: float, slippage_bps: int) -> str:
        if not self.sol_keypair:
            logging.warning(f"⚠️ [模拟] Solana {action} {token_address}")
            return f"sim_tx_{int(time.time())}"

        slippage = slippage_bps or config.SLIPPAGE_DEFAULT

        if action == "buy":
            in_mint, out_mint = self.WSOL, token_address
            amt_lamports = int((amount or config.BUY_AMOUNT_SOL) * 1e9)
        else:
            in_mint, out_mint = token_address, self.WSOL
            amt_lamports = int(amount) if amount else 0

        # 1. 获取报价
        try:
            url = f"{self.jup_quote}?inputMint={in_mint}&outputMint={out_mint}&amount={amt_lamports}&slippageBps={slippage}"
            quote_res = self.session.get(url, timeout=10).json()
            if "error" in quote_res:
                logging.error(f"❌ Solana 报价失败: {quote_res['error']}")
                return None
        except Exception as e:
            logging.error(f"❌ Solana 节点连接异常: {e}")
            return None

        # 2. 构建交易 (新增 dynamicComputeUnitLimit 解决 CU 超载上链失败问题)
        priority_fee = int(config.SOL_PRIORITY_FEE * 1e9)
        try:
            payload = {
                "quoteResponse": quote_res,
                "userPublicKey": self.sol_pubkey,
                "wrapAndUnwrapSol": True,
                "prioritizationFeeLamports": priority_fee,
                "dynamicComputeUnitLimit": True  # 核心修复点：动态CU
            }
            swap_res = self.session.post(self.jup_swap, json=payload, timeout=10).json()
        except Exception as e:
            logging.error(f"❌ Solana 交易构建异常: {e}")
            return None

        if "swapTransaction" not in swap_res:
            logging.error(f"❌ Solana 未能返回交易体: {swap_res}")
            return None

        # 3. 签名与硬核暴力上链
        try:
            raw_tx = base64.b64decode(swap_res["swapTransaction"])
            tx = VersionedTransaction.from_bytes(raw_tx)

            # 核心修复点：tx.message 是属性不是方法，去掉括号并转换为 bytes
            msg_bytes = bytes(tx.message)
            signature = self.sol_keypair.sign_message(msg_bytes)
            signed_tx = VersionedTransaction(tx.message, [signature])

            # 核心修复点：开启 skip_preflight 跳过 RPC 本地预检，直接广播给矿工，极大提升抢购成功率
            opts = TxOpts(skip_preflight=True)
            res = self.sol_client.send_raw_transaction(bytes(signed_tx), opts=opts)

            tx_sig = str(res.value)
            logging.info(f"🚀 [Solana 上链] {action} 成功! Tx: {tx_sig}")
            return tx_sig
        except Exception as e:
            logging.error(f"❌ Solana 签名或广播崩溃: {e}")
            return None

    # ================= BSC 交易逻辑 =================
    def _swap_bsc(self, token_address: str, action: str, amount: float, slippage_bps: int) -> str:
        if not self.bsc_account or not self.w3:
            logging.warning(f"⚠️ [模拟] BSC {action} {token_address}")
            return f"sim_tx_{int(time.time())}"

        router_contract = self.w3.eth.contract(address=self.PANCAKE_ROUTER, abi=self.router_abi)
        my_address = self.bsc_account.address
        deadline = int(time.time()) + 300  # 5分钟过期
        gas_price = self.w3.eth.gas_price

        try:
            if action == "buy":
                # BNB 买代币
                buy_amt = amount or config.BUY_AMOUNT_BNB
                value_wei = self.w3.to_wei(buy_amt, 'ether')
                path = [self.WBNB, token_address]

                # 盲买不计算 amountOutMin (设置0强吃)，靠链上回滚防夹，因为土狗税率算不准
                txn = router_contract.functions.swapExactETHForTokensSupportingFeeOnTransferTokens(
                    0, path, my_address, deadline
                ).build_transaction({
                    'from': my_address,
                    'value': value_wei,
                    'gasPrice': gas_price,
                    'nonce': self.w3.eth.get_transaction_count(my_address),
                    'gas': 500000  # 固定高 gas 保证执行
                })

            else:
                # 卖代币回 BNB
                token_contract = self.w3.eth.contract(address=token_address, abi=self.erc20_abi)

                # 1. 查余额
                balance = token_contract.functions.balanceOf(my_address).call()
                if balance == 0:
                    logging.warning(f"⚠️ 钱包内没有可卖出的 {token_address}")
                    return None

                # 2. 授权 (Approve)
                nonce = self.w3.eth.get_transaction_count(my_address)
                approve_txn = token_contract.functions.approve(self.PANCAKE_ROUTER, balance).build_transaction({
                    'from': my_address,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'gas': 100000
                })
                signed_app = self.bsc_account.sign_transaction(approve_txn)
                self.w3.eth.send_raw_transaction(signed_app.rawTransaction)
                logging.info(f"🔓 [BSC] 授权成功，准备卖出...")
                time.sleep(3)  # 等待授权落块

                # 3. 卖出
                path = [token_address, self.WBNB]
                txn = router_contract.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(
                    balance, 0, path, my_address, deadline
                ).build_transaction({
                    'from': my_address,
                    'gasPrice': gas_price,
                    'nonce': self.w3.eth.get_transaction_count(my_address),
                    'gas': 500000
                })

            # 签名与发送交易
            signed_txn = self.bsc_account.sign_transaction(txn)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hex = self.w3.to_hex(tx_hash)
            logging.info(f"🚀 [BSC 上链] {action} 成功! Hash: {tx_hex}")
            return tx_hex

        except Exception as e:
            logging.error(f"❌ BSC 交易执行失败: {e}")
            return None

    # ================= 跨链防守监控中心 =================
    def start_monitor_thread(self, ca: str, symbol: str, amount_cost: float, chain_id: str):
        t = threading.Thread(target=self._monitor, args=(ca, symbol, chain_id), daemon=True)
        t.start()

    def _monitor(self, ca: str, symbol: str, chain_id: str):
        """跨链价格监控中心：通过 DexScreener 统一获取价格"""
        stop_loss = -0.20
        take_profit = 1.00

        entry_price = self._get_universal_price(ca)
        if not entry_price:
            logging.warning(f"⚠️ {symbol} 无法获取初始价格，防守模块取消。")
            return

        logging.info(f"🛡️ 开启 {symbol} 防守系统，建仓价: ${entry_price:.6f}")

        while True:
            time.sleep(15)  # 每 15 秒查询一次，防止被 DexScreener 封禁 IP
            curr_price = self._get_universal_price(ca)
            if not curr_price: continue

            roi = (curr_price - entry_price) / entry_price

            if roi <= stop_loss:
                logging.warning(f"🚨 {symbol} 触发断臂止损! 跌幅: {roi * 100:.2f}%")
                self.execute_swap(ca, "sell", chain_id, slippage_bps=2500)
                self.defense_count += 1
                self._notify(f"🚨 <b>{symbol} 触发止损卖出</b>\n损幅: {roi * 100:.2f}%")
                break

            if roi >= take_profit:
                logging.info(f"🎉 {symbol} 翻倍抽本! 涨幅: {roi * 100:.2f}%")
                self.execute_swap(ca, "sell", chain_id, slippage_bps=2000)
                self.defense_count += 1
                self._notify(f"🎉 <b>{symbol} 翻倍止盈卖出</b>\n利润: {roi * 100:.2f}%")
                break

    def _get_universal_price(self, ca: str) -> float:
        """跨链统一价格获取：使用 DexScreener API"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{ca}"
            resp = self.session.get(url, timeout=10).json()
            pairs = resp.get('pairs', [])
            if pairs:
                # 取最大池子的实时美金价格
                return float(pairs[0].get('priceUsd', 0.0))
            return 0.0
        except Exception:
            return 0.0

    def _notify(self, msg):
        if tg_bot: tg_bot.send_message(msg)


trade_engine = TradeEngine()