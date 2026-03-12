import os
import requests
from dotenv import load_dotenv

# 加载当前目录下的 .env 文件
load_dotenv()


def auto_detect_proxy():
    """
    智能网络嗅探器：解决本地开发与海外服务器部署来回改代理的痛点
    """
    env_proxy = os.getenv("PROXY_URL", "").strip()
    if env_proxy:
        print(f"🌐 [网络嗅探] 使用 .env 强制指定的代理: {env_proxy}")
        return env_proxy

    print("🌐 [网络嗅探] 正在检测 Jupiter API 连通性...")
    # 1. 尝试直连 (模拟海外服务器或全局 TUN 模式)
    try:
        # 只要能连上就行，哪怕报 400 Bad Request 也说明网络是通的
        requests.get("https://quote-api.jup.ag", timeout=2)
        print("✅ [网络嗅探] API 直连通畅！当前为海外环境或全局 TUN 模式，免代理。")
        return ""
    except requests.RequestException:
        print("⚠️ [网络嗅探] 直连失败 (可能遇墙/DNS污染)，正在自动扫描本地常用代理端口...")

    # 2. 扫描本地常用代理客户端端口 (已将你的专属端口置于最高优先级)
    common_proxies = [
        "http://127.0.0.1:8800",  # 👑 你的专属 HTTP 代理
        "socks5://127.0.0.1:10020",  # 👑 你的专属 SOCKS5 代理
        "http://127.0.0.1:7890",  # Clash 默认
        "http://127.0.0.1:10809",  # v2rayN 默认
        "http://127.0.0.1:10808",  # Xray 默认
        "http://127.0.0.1:1080",  # Shadowsocks 默认
        "http://127.0.0.1:1081",
        "http://127.0.0.1:9090",
    ]

    for p in common_proxies:
        try:
            proxies = {"http": p, "https": p}
            requests.get("https://quote-api.jup.ag", proxies=proxies, timeout=1.5)
            print(f"✅ [网络嗅探] 成功命中本地代理池，自动挂载: {p}")
            return p
        except requests.RequestException:
            continue

    print("❌ [网络嗅探] 所有常用代理端口均未响应，后续 Solana 交易可能大概率超时！")
    return ""


class Config:
    """
    统一管理项目的环境变量与配置参数 - 猎人进化版 (双链实战升级)
    """
    # ---------------- 智能网络 ----------------
    # 自动获取最佳网络通道
    PROXY_URL = auto_detect_proxy()

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
    TARGET_CHAIN_ID = os.getenv("TARGET_CHAIN_ID", "CT_501,56")  # CT_501=Solana, 56=BSC

    # ---------------- 猎人筛选阈值 (实战放宽) ----------------
    MAX_TOP10_HOLDING = float(os.getenv("MAX_TOP10_HOLDING", 75.0))
    MIN_MARKET_CAP = float(os.getenv("MIN_MARKET_CAP", 3000.0))
    MAX_DEV_SELL = float(os.getenv("MAX_DEV_SELL", 80.0))

    # ---------------- 自动交易与竞争配置 (Solana) ----------------
    SOL_PRIVATE_KEY = os.getenv("SOL_PRIVATE_KEY")
    BUY_AMOUNT_SOL = float(os.getenv("BUY_AMOUNT_SOL", 0.1))
    SOL_RPC_URL = os.getenv("SOL_RPC_URL", "https://api.mainnet-beta.solana.com")
    SOL_PRIORITY_FEE = float(os.getenv("SOL_PRIORITY_FEE", 0.005))

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