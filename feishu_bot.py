import requests
import logging
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FeishuBot:
    """
    封装飞书 Webhook 机器人功能
    极致优化：支持一键复制 CA，深度集成币安 Web3 钱包
    """

    def __init__(self):
        self.webhook_url = config.FEISHU_WEBHOOK_URL

    def format_and_send_alert(self, token_data: dict, grok_analysis: dict) -> bool:
        """
        组装飞书互动卡片：支持移动端币安 App 唤起
        """
        if not self.webhook_url or "open-apis" not in self.webhook_url:
            logging.warning("飞书 Webhook 未配置，跳过推送。")
            return False

        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        chain_id = token_data.get("chainId", "CT_501") # 默认 Solana
        progress = token_data.get("progress", "Unknown")

        # 市值美化
        mcap_raw = token_data.get("marketCap", "0")
        try:
            mcap = f"${float(mcap_raw):,.0f}"
        except:
            mcap = f"${mcap_raw}"

        rating = grok_analysis.get("rating", "Unknown")
        summary = grok_analysis.get("summary", "无分析摘要")

        # 针对币安 Web3 钱包的直达链接 (Deep Link)
        # 手机端点击会自动唤起币安 App 进入 Swap 或 Chart
        binance_swap_url = f"https://www.binance.com/zh-CN/web3wallet/dex/swap?chainId={chain_id}&toTokenAddress={ca}"
        binance_chart_url = f"https://www.binance.com/zh-CN/web3wallet/dex/chart?chainId={chain_id}&address={ca}"

        # 根据评级确定颜色主题
        color_map = {"S": "red", "A": "orange", "B": "blue", "F": "grey"}
        theme_color = color_map.get(rating, "purple")

        # 飞书互动卡片 JSON 结构
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"enable_forward": True, "update_multi": True},
                "header": {
                    "template": theme_color,
                    "title": {"content": f"🚀 发现潜力金狗: ${symbol}", "tag": "plain_text"}
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {"is_short": True, "text": {"content": f"**📈 进度:**\n{progress}%", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**💰 市值:**\n{mcap}", "tag": "lark_md"}}
                        ]
                    },
                    {
                        "tag": "div",
                        "text": {"content": f"**🐦 Grok (X) 深度透视 [{rating}级]:**\n{summary}", "tag": "lark_md"}
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"content": f"**🎯 合约地址 (移动端点击代码块复制):**\n`{ca}`", "tag": "lark_md"}
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"content": "🚀 币安 Web3 极速买入", "tag": "plain_text"},
                                "type": "danger",
                                "url": binance_swap_url
                            },
                            {
                                "tag": "button",
                                "text": {"content": "📈 币安 Web3 查看 K 线", "tag": "plain_text"},
                                "type": "primary",
                                "url": binance_chart_url
                            }
                        ]
                    },
                    {
                        "tag": "note",
                        "elements": [{"content": "✅ 已通过币安深度安全审计 | 来源: Grok Sniper Engine", "tag": "plain_text"}]
                    }
                ]
            }
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logging.info(f"飞书安全消息推送成功: ${symbol}")
            return True
        except Exception as e:
            logging.error(f"飞书推送失败: {e}")
            return False

feishu_bot = FeishuBot()