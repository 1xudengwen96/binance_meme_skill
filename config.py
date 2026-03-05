import os
from dotenv import load_dotenv

# 加载当前目录下的 .env 文件
load_dotenv()


class Config:
    """
    统一管理项目的环境变量与配置参数
    """
    # ---------------- Grok (xAI) 配置 ----------------
    GROK_API_KEY = os.getenv("GROK_API_KEY")
    GROK_BASE_URL = "https://api.x.ai/v1"  # Grok 官方 API 基础路径

    # ---------------- Telegram 配置 ----------------
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
    TG_CHAT_ID = os.getenv("TG_CHAT_ID")

    # ---------------- 飞书 配置 ----------------
    FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL")

    # ---------------- 引擎运行配置 ----------------
    # 获取不到则默认 30 秒
    SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS", 30))
    TARGET_CHAIN_ID = os.getenv("TARGET_CHAIN_ID", "CT_501")

    @classmethod
    def validate(cls):
        """
        启动前校验核心配置是否已填写
        """
        missing_configs = []

        # 校验 Grok API Key
        if not cls.GROK_API_KEY or cls.GROK_API_KEY.startswith("xai-your"):
            missing_configs.append("GROK_API_KEY")

        # 校验通知通道：允许 Telegram 或 飞书 至少配置一个
        tg_ready = cls.TG_BOT_TOKEN and not cls.TG_BOT_TOKEN.startswith("123456789")
        feishu_ready = cls.FEISHU_WEBHOOK_URL and "feishu" in cls.FEISHU_WEBHOOK_URL

        if not tg_ready and not feishu_ready:
            missing_configs.append("TG_BOT_TOKEN 或 FEISHU_WEBHOOK_URL (至少需要配置一个通知通道)")

        if missing_configs:
            raise ValueError(f"🚨 缺少必要的环境变量配置: {', '.join(missing_configs)}。请检查 .env 文件！")


# 实例化并提供给其他模块使用
config = Config()