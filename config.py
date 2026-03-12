import os
from dotenv import load_dotenv

# 加载当前目录下的 .env 文件
load_dotenv()


class Config:
    """
    统一管理项目的环境变量与配置参数 - 猎人进化版 (双链实战升级)
    """
    # ---------------- Grok (xAI) 配置 ----------------
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    GROK_BASE_URL = "https://api.x.ai/v1"
    GROK_MODEL = os.getenv("GROK_MODEL", "grok-beta")

    # [核心优化] 触发 AI 审计的初始分阈值大幅降低 (60 -> 45)，给早期无数据的新币机会
    GROK_SCORE_THRESHOLD = int(os.getenv("GROK_SCORE_THRESHOLD", 45))

    # ---------------- Telegram 配置 ----------------
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
    TG_CHAT_ID = os.getenv("TG_CHAT_ID")

    # ---------------- 飞书 配置 ----------------
    FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")

    # ---------------- 引擎运行配置 ----------------
    # 缩短至 3 秒，毫秒级博弈需更快轮询 (原为5秒)
    SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS", 3))
    TARGET_CHAIN_ID = os.getenv("TARGET_CHAIN_ID", "CT_501")  # CT_501=Solana, 56=BSC

    # ---------------- 猎人筛选阈值 (实战放宽) ----------------
    MAX_TOP10_HOLDING = float(os.getenv("MAX_TOP10_HOLDING", 75.0))

    # 降低最小关注市值，捕捉 $3k 起步的黄金零头位
    MIN_MARKET_CAP = float(os.getenv("MIN_MARKET_CAP", 3000.0))

    MAX_DEV_SELL = float(os.getenv("MAX_DEV_SELL", 80.0))  # 开发者抛售上限

    # ---------------- 自动交易与竞争配置 (Solana) ----------------
    SOL_PRIVATE_KEY = os.getenv("SOL_PRIVATE_KEY")
    BUY_AMOUNT_SOL = float(os.getenv("BUY_AMOUNT_SOL", 0.1))
    SOL_RPC_URL = os.getenv("SOL_RPC_URL", "https://api.mainnet-beta.solana.com")

    # 提高 Solana 默认优先费，防止极端行情被 MEV 夹击阻断 (单位: SOL)
    SOL_PRIORITY_FEE = float(os.getenv("SOL_PRIORITY_FEE", 0.005))

    # ---------------- 自动交易与竞争配置 (BSC - 新增) ----------------
    BSC_PRIVATE_KEY = os.getenv("BSC_PRIVATE_KEY")
    BSC_WALLET_ADDRESS = os.getenv("BSC_WALLET_ADDRESS")
    BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
    BUY_AMOUNT_BNB = float(os.getenv("BUY_AMOUNT_BNB", 0.01))

    # 激进滑点设置 (BPS: 100 = 1%) - 买不进比买贵了更痛苦
    SLIPPAGE_S_GRADE = 2000  # S级金狗滑点 20%
    SLIPPAGE_A_GRADE = 1500  # A级优质滑点 15%
    SLIPPAGE_DEFAULT = 1000  # 默认滑点 10%

    @classmethod
    def validate(cls):
        """
        启动前校验核心配置是否已填写
        """
        missing_configs = []

        if not cls.GROK_API_KEY or cls.GROK_API_KEY.startswith("xai-your"):
            missing_configs.append("GROK_API_KEY")

        tg_ready = cls.TG_BOT_TOKEN and not cls.TG_BOT_TOKEN.startswith("123456789")
        feishu_ready = cls.FEISHU_WEBHOOK_URL and "feishu" in cls.FEISHU_WEBHOOK_URL

        if not tg_ready and not feishu_ready:
            missing_configs.append("推送通道 (TG 或 飞书 至少配置一个)")

        # ---------------- 双链钱包校验 ----------------
        if cls.TARGET_CHAIN_ID == "CT_501" and not cls.SOL_PRIVATE_KEY:
            print("⚠️ 未配置 SOL_PRIVATE_KEY，Solana 将以【模拟模式】运行。")

        if cls.TARGET_CHAIN_ID == "56" and not cls.BSC_PRIVATE_KEY:
            print("⚠️ 未配置 BSC_PRIVATE_KEY，BSC 将以【模拟模式】运行。")

        if missing_configs:
            raise ValueError(f"🚨 缺少必要的环境变量配置: {', '.join(missing_configs)}。请检查 .env 文件！")


# 实例化
config = Config()