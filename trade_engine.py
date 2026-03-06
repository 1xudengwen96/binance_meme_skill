import time
import logging
import requests
import base58
from config import config
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from tg_bot import tg_bot
from feishu_bot import feishu_bot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')


class TradeEngine:
    """
    Solana 自动交易引擎：对接 Jupiter API 进行极速 Swap，并执行四维动态出货策略
    """

    def __init__(self):
        self.rpc_url = config.SOL_RPC_URL
        self.client = Client(self.rpc_url)
        self.buy_amount_sol = config.BUY_AMOUNT_SOL
        self.sol_mint = "So11111111111111111111111111111111111111112"

        # 记录仓位状态
        # 结构: { "CA": {"symbol": "", "token_balance_raw": 0, "cost_basis_sol": 0.0, "highest_value_sol": 0.0, "status": "FULL"/"MOONBAG"} }
        self.active_positions = {}

        try:
            if config.SOL_PRIVATE_KEY:
                raw_pk = base58.b58decode(config.SOL_PRIVATE_KEY)
                self.wallet = Keypair.from_bytes(raw_pk)
                logging.info(f"🔑 交易钱包加载成功! 地址: {self.wallet.pubkey()}")
            else:
                self.wallet = None
                logging.warning("⚠️ 未配置 SOL_PRIVATE_KEY，自动交易系统将以模拟模式(只读)运行。")
        except Exception as e:
            self.wallet = None
            logging.error(f"❌ 私钥解析失败: {e}")

    def check_gas_and_balance(self) -> bool:
        """购买前检查余额：预留 0.01 SOL 作为 Gas"""
        if not self.wallet: return False
        try:
            balance_resp = self.client.get_balance(self.wallet.pubkey())
            balance_lamports = balance_resp.value
            balance_sol = balance_lamports / 1e9

            required_sol = self.buy_amount_sol + 0.01
            if balance_sol < required_sol:
                logging.error(f"💸 余额不足! 当前: {balance_sol:.4f} SOL, 需要: {required_sol:.4f} SOL")
                return False
            return True
        except Exception as e:
            logging.error(f"❌ 查账失败: {e}")
            return False

    def execute_swap(self, input_mint: str, output_mint: str, amount_in_lamports: int, slippage_bps: int = 500) -> dict:
        """调用 Jupiter API 执行 Swap"""
        if not self.wallet: return {"success": False, "reason": "无钱包配置"}
        try:
            # 1. 获取报价
            quote_url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_in_lamports}&slippageBps={slippage_bps}"
            quote_res = requests.get(quote_url, timeout=10).json()

            if "error" in quote_res:
                return {"success": False, "reason": f"报价失败: {quote_res['error']}"}

            # 2. 构建交易
            swap_url = "https://quote-api.jup.ag/v6/swap"
            payload = {
                "quoteResponse": quote_res,
                "userPublicKey": str(self.wallet.pubkey()),
                "wrapAndUnwrapSol": True
            }
            swap_res = requests.post(swap_url, json=payload, timeout=10).json()

            if "swapTransaction" not in swap_res:
                return {"success": False, "reason": "未获取到交易体"}

            # 3. 签名并发送
            raw_tx = base58.b58decode(swap_res['swapTransaction'])
            tx = VersionedTransaction.from_bytes(raw_tx)
            signed_tx = VersionedTransaction(tx.message, [self.wallet])

            tx_sig = self.client.send_raw_transaction(bytes(signed_tx)).value
            return {"success": True, "tx_hash": str(tx_sig), "expected_out": quote_res.get("outAmount")}

        except Exception as e:
            return {"success": False, "reason": str(e)}

    def buy_token(self, token: dict):
        """全自动买入指令"""
        symbol = token.get("symbol", "UNKNOWN")
        ca = token.get("contractAddress")

        if ca in self.active_positions: return
        if not self.check_gas_and_balance(): return

        logging.info(f"⚡ [TradeEngine] 发起攻击: 买入 ${symbol} ({self.buy_amount_sol} SOL)...")
        amount_lamports = int(self.buy_amount_sol * 1e9)

        res = self.execute_swap(self.sol_mint, ca, amount_lamports, slippage_bps=500)

        if res["success"]:
            logging.info(f"✅ 买入成功! 哈希: {res['tx_hash']}")
            tokens_received = int(res["expected_out"])

            # 登记仓位
            self.active_positions[ca] = {
                "symbol": symbol,
                "token_balance_raw": tokens_received,
                "cost_basis_sol": self.buy_amount_sol,
                "highest_value_sol": self.buy_amount_sol,
                "status": "FULL"
            }
            msg = f"🛒 **已自动买入**: ${symbol}\n投入: {self.buy_amount_sol} SOL\nTX: `{res['tx_hash']}`"
            tg_bot.send_message(msg)
            feishu_bot.send_message(msg) if hasattr(feishu_bot, 'send_message') else None
        else:
            logging.error(f"❌ 买入失败: {res['reason']}")

    def sell_token(self, ca: str, percentage: float, reason: str):
        """自动出货逻辑 (支持按比例卖出)"""
        pos = self.active_positions.get(ca)
        if not pos: return

        symbol = pos["symbol"]
        amount_to_sell = int(pos["token_balance_raw"] * percentage)

        logging.info(f"📉 [TradeEngine] 执行出货: ${symbol} ({percentage * 100}%). 原因: {reason}")

        # 卖出滑点调高到 10% (1000 bps) 保证能跑掉
        res = self.execute_swap(ca, self.sol_mint, amount_to_sell, slippage_bps=1000)

        if res["success"]:
            actual_sol_received = int(res.get("expected_out", 0)) / 1e9
            logging.info(f"✅ 卖出成功! 预计回收: {actual_sol_received:.4f} SOL")

            msg = f"💰 **自动出货**: ${symbol}\n出货比例: {percentage * 100}%\n触发规则: {reason}\nTX: `{res['tx_hash']}`"
            tg_bot.send_message(msg)

            if percentage >= 1.0:
                del self.active_positions[ca]
            else:
                pos["status"] = "MOONBAG"
                pos["token_balance_raw"] -= amount_to_sell
                pos["cost_basis_sol"] *= (1 - percentage)
                pos["highest_value_sol"] = 0  # 重置最高点
        else:
            logging.error(f"❌ 卖出失败: {res['reason']}")

    def get_position_value_in_sol(self, ca: str, raw_amount: int) -> float:
        """通过 Jupiter 询价获取当前仓位的 SOL 价值"""
        if raw_amount <= 0: return 0.0
        try:
            url = f"https://quote-api.jup.ag/v6/quote?inputMint={ca}&outputMint={self.sol_mint}&amount={raw_amount}"
            res = requests.get(url, timeout=5).json()
            if "outAmount" in res:
                return int(res["outAmount"]) / 1e9
            return 0.0
        except:
            return 0.0

    def monitor_positions_loop(self):
        """出货策略雷达：四维动态监控"""
        logging.info("🛡️ 出货策略雷达 (Smart Exit Matrix) 已启动")
        while True:
            try:
                for ca, pos in list(self.active_positions.items()):
                    current_value_sol = self.get_position_value_in_sol(ca, pos["token_balance_raw"])
                    if current_value_sol <= 0: continue

                    cost_basis = pos["cost_basis_sol"]
                    ath = pos["highest_value_sol"]
                    status = pos["status"]

                    # 刷新最高价值
                    if current_value_sol > ath:
                        self.active_positions[ca]["highest_value_sol"] = current_value_sol
                        ath = current_value_sol

                    roi = (current_value_sol - cost_basis) / cost_basis if cost_basis > 0 else 0
                    drawdown = (current_value_sol - ath) / ath if ath > 0 else 0

                    # === 维度一：刚性防御 (硬止损 -35%) ===
                    if roi <= -0.35:
                        self.sell_token(ca, 1.0, f"刚性止损 (盈亏: {roi * 100:.2f}%)")
                        continue

                    # === 维度二：翻倍抽本 (Moonbag) ===
                    if status == "FULL" and roi >= 1.0:
                        self.sell_token(ca, 0.5, f"翻倍抽本 (盈亏: {roi * 100:.2f}%)，开启Moonbag")
                        continue

                    # === 维度三：动态追踪逃顶 ===
                    if status == "MOONBAG" and drawdown <= -0.25:
                        self.sell_token(ca, 1.0, f"追踪逃顶 (最高回撤达 25%)，利润落袋")
                        continue
                    elif status == "FULL" and drawdown <= -0.30 and roi > 0.2:
                        self.sell_token(ca, 1.0, f"提前逃顶 (未翻倍但利润回撤破防)")
                        continue

            except Exception as e:
                logging.error(f"出货监控异常: {e}")

            time.sleep(5)


# 实例化单例
trader = TradeEngine()