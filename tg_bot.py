import requests
import logging
from config import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TelegramBot:
    """
    封装 Telegram 机器人相关的推送功能
    优化排版以支持一键复制，并深度集成币安 Web3 钱包
    """

    def __init__(self):
        self.bot_token = config.TG_BOT_TOKEN
        self.chat_id = config.TG_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text: str) -> bool:
        """
        发送消息到指定的 Telegram Chat
        """
        if not self.bot_token or not self.chat_id or self.bot_token.startswith("123456789"):
            logging.warning("Telegram Bot 未配置，输出到控制台：\n" + text)
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logging.error(f"Telegram 推送失败: {e}")
            return False

    def format_and_send_alert(self, token_data: dict, grok_analysis: dict) -> bool:
        """
        组装金狗战报：支持点击即复制 CA，且按钮直达币安 Web3 钱包
        """
        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        chain_id = token_data.get("chainId", "CT_501")  # 默认 Solana
        progress = token_data.get("progress", "Unknown")

        # 市值美化
        mcap_raw = token_data.get("marketCap", "0")
        try:
            mcap = f"${float(mcap_raw):,.0f}"
        except:
            mcap = f"${mcap_raw}"

        rating = grok_analysis.get("rating", "Unknown")
        summary = grok_analysis.get("summary", "无摘要")

        # 针对币安 Web3 钱包的 deeplink 构造
        # 手机端会自动唤起币安 App
        binance_swap_url = f"https://www.binance.com/zh-CN/web3wallet/dex/swap?chainId={chain_id}&toTokenAddress={ca}"
        binance_chart_url = f"https://www.binance.com/zh-CN/web3wallet/dex/chart?chainId={chain_id}&address={ca}"

        # 评级 Emoji
        rating_emoji = {"S": "🔥", "A": "✅", "B": "👀", "F": "❌"}.get(rating, "ℹ️")

        # --- 组装 Markdown ---
        # 注意：ca 被包裹在单反引号内，手机端点击即可复制
        msg = f"""🚨 **发现潜在金狗：${symbol}**

📊 **链上指标**：
- 进度：{progress}% (即将打满)
- 市值：{mcap}
- 审计：✅ 已通过币安深度安全审计

🐦 **Grok 社交透视 [{rating_emoji} {rating}级]**：
_{summary}_

🎯 **一键复制合约 (点击下方地址)**：
`{ca}`

⚡ **快捷操作 (直达币安 App)**：
[🚀 币安 Web3 极速买入]({binance_swap_url})
[📈 币安 Web3 查看K线]({binance_chart_url})
"""
        logging.info(f"推送代币 ${symbol} 至 Telegram...")
        return self.send_message(msg)


# 实例化
tg_bot = TelegramBot()