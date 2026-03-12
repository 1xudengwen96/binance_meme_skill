import os
from dotenv import load_dotenv

# 加载当前目录下的 .env 文件
load_dotenv()


class Config:
    """
    统一管理项目的环境变量与配置参数 - 猎人进化版 (纯净实战版)
    """
    # ---------------- 代理配置 ----------------
    # 本地开发时写: http://127.0.0.1:8800
    # AWS 服务器上: 留空即可 (代码内自带备用节点穿墙)
    PROXY_URL = os.getenv("PROXY_URL", "").strip()

    # ---------------- Grok (xAI) 配置 ----------------
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    GROK_BASE_URL = "https://api.x.ai/v1"
    GROK_MODEL = os.getenv("GROK_MODEL", "grok-beta")
    GROK_SCORE_THRESHOLD = int(os.getenv("GROK_SCORE_THRESHOLD", 45))

    # ---------------- Telegram 配置 ----------------
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
    TG_CHAT_ID = os.getenv("TG_CHAT_ID")

    # ---------------- 飞书 配置 ----------------
    FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")

    # ---------------- 引擎运行配置 ----------------
    SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS", 3))
    TARGET_CHAIN_ID = os.getenv("TARGET_CHAIN_ID", "CT_501,56")

    # ---------------- 猎人筛选阈值 (实战放宽) ----------------
    MAX_TOP10_HOLDING = float(os.getenv("MAX_TOP10_HOLDING", 75.0))
    MIN_MARKET_CAP = float(os.getenv("MIN_MARKET_CAP", 3000.0))
    MAX_DEV_SELL = float(os.getenv("MAX_DEV_SELL", 80.0))

    # ---------------- 自动交易与竞争配置 (Solana) ----------------
    SOL_PRIVATE_KEY = os.getenv("SOL_PRIVATE_KEY")
    BUY_AMOUNT_SOL = float(os.getenv("BUY_AMOUNT_SOL", 0.1))
    SOL_RPC_URL = os.getenv("SOL_RPC_URL", "https://api.mainnet-beta.solana.com")
    SOL_PRIORITY_FEE = float(os.getenv("SOL_PRIORITY_FEE", 0.005))

    # ---------------- 交易备用网关 (穿墙核心) ----------------
    # 当美国 IP (如 AWS) 被 Jupiter 官方拉黑/DNS污染时，自动无缝切换到备用企业节点强行下单！
    JUPITER_ENDPOINTS = [
        "https://quote-api.jup.ag/v6",  # 官方主节点 (AWS美国IP会报 getaddrinfo failed)
        "https://jupiter-swap-api.quiknode.pro/v6",  # QuickNode 企业级备用节点 (防封杀，穿墙专用)
        "https://api.jup.ag/swap/v1"  # 官方历史备用节点
    ]

    # ---------------- 自动交易与竞争配置 (BSC - 新增) ----------------
    BSC_PRIVATE_KEY = os.getenv("BSC_PRIVATE_KEY")
    BSC_WALLET_ADDRESS = os.getenv("BSC_WALLET_ADDRESS")
    BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
    BUY_AMOUNT_BNB = float(os.getenv("BUY_AMOUNT_BNB", 0.01))

    # 激进滑点设置 (BPS: 100 = 1%)
    SLIPPAGE_S_GRADE = 2000
    SLIPPAGE_A_GRADE = 1500
    SLIPPAGE_DEFAULT = 1000

    @classmethod
    def validate(cls):
        missing_configs = []

        if not cls.GROK_API_KEY or cls.GROK_API_KEY.startswith("xai-your"):
            missing_configs.append("GROK_API_KEY")

        tg_ready = cls.TG_BOT_TOKEN and not cls.TG_BOT_TOKEN.startswith("123456789")
        feishu_ready = cls.FEISHU_WEBHOOK_URL and "feishu" in cls.FEISHU_WEBHOOK_URL

        if not tg_ready and not feishu_ready:
            missing_configs.append("推送通道 (TG 或 飞书 至少配置一个)")

        active_chains = [c.strip() for c in cls.TARGET_CHAIN_ID.split(',')]

        if "CT_501" in active_chains and not cls.SOL_PRIVATE_KEY:
            print("⚠️ 未配置 SOL_PRIVATE_KEY，Solana 将以【模拟模式】运行。")

        if "56" in active_chains and not cls.BSC_PRIVATE_KEY:
            print("⚠️ 未配置 BSC_PRIVATE_KEY，BSC 将以【模拟模式】运行。")

        if missing_configs:
            raise ValueError(f"🚨 缺少必要的环境变量配置: {', '.join(missing_configs)}。请检查 .env 文件！")


# 实例化
config = Config()