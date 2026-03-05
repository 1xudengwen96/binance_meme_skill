import requests
import logging
from config import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TelegramBot:
    """
    封装 Telegram 机器人相关的推送功能
    用于将金狗战报发送到你的手机/群组
    """

    def __init__(self):
        self.bot_token = config.TG_BOT_TOKEN
        self.chat_id = config.TG_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text: str) -> bool:
        """
        发送 Markdown 格式的文本消息到指定的 Telegram Chat
        """
        # 如果没有配置 Telegram 参数，则只在控制台打印
        if not self.bot_token or not self.chat_id or self.bot_token.startswith("123456789"):
            logging.warning("Telegram Bot Token 未正确配置，已转为控制台输出：\n" + text)
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True  # 关闭链接自动预览，防止打乱我们精心设计的排版
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
        组装精美的金狗警报模板，并触发推送
        """
        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        progress = token_data.get("progress", "Unknown")

        # 将市值格式化，加上逗号使其更易读
        mcap_raw = token_data.get("marketCap", "0")
        try:
            mcap = f"${float(mcap_raw):,.2f}"
        except:
            mcap = f"${mcap_raw}"

        holders_top10 = token_data.get("holdersTop10Percent", "Unknown")
        dev_sell = token_data.get("devSellPercent", "Unknown")

        rating = grok_analysis.get("rating", "Unknown")
        summary = grok_analysis.get("summary", "Grok 无返回摘要。")

        # 根据评级添加不同的高亮 emoji
        if rating == "S":
            rating_emoji = "🔥"
        elif rating == "A":
            rating_emoji = "⚠️"
        elif rating == "F":
            rating_emoji = "❌"
        else:
            rating_emoji = "ℹ️"

        # --- 组装 Markdown 消息体 ---
        msg = f"""🚨 **发现潜在金狗：${symbol}** 🚨

📊 **Binance 链上数据**：
- **进度**：{progress}% (即将上线外盘) 
- **市值**：{mcap}
- **筹码**：前十占比 {holders_top10}% | 开发者卖出 {dev_sell}%
- **风控**：✅ 审计绝对安全

🐦 **Grok 流量透视 (X)**：
{rating_emoji} **{rating}级共振！**
_{summary}_

⚡ **一键快捷操作**：
[📈 DexScreener 看K线](https://dexscreener.com/solana/{ca})
[🚀 Photon 极速买入](https://photon-sol.tinyastro.io/en/lp/{ca})
`{ca}` (点击自动复制合约)
"""
        logging.info(f"正在向 Telegram 推送代币 ${symbol} 的警报...")
        return self.send_message(msg)


# 实例化提供给其他模块使用
tg_bot = TelegramBot()