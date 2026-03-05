import requests
import logging
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class FeishuBot:
    """
    封装飞书 Webhook 机器人功能
    采用富文本卡片格式，展示更专业
    """

    def __init__(self):
        self.webhook_url = config.FEISHU_WEBHOOK_URL

    def format_and_send_alert(self, token_data: dict, grok_analysis: dict) -> bool:
        """
        组装飞书互动卡片并发送
        """
        if not self.webhook_url or "open-apis" not in self.webhook_url:
            logging.warning("飞书 Webhook 未配置，跳过推送。")
            return False

        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        progress = token_data.get("progress", "Unknown")

        # 市值格式化
        mcap_raw = token_data.get("marketCap", "0")
        try:
            mcap = f"${float(mcap_raw):,.2f}"
        except:
            mcap = f"${mcap_raw}"

        holders_top10 = token_data.get("holdersTop10Percent", "Unknown")
        dev_sell = token_data.get("devSellPercent", "Unknown")
        rating = grok_analysis.get("rating", "Unknown")
        summary = grok_analysis.get("summary", "无分析摘要")

        # 根据评级确定颜色主题
        # red, orange, yellow, green, blue, grey
        color_map = {"S": "red", "A": "orange", "B": "blue", "F": "grey"}
        theme_color = color_map.get(rating, "purple")

        # 飞书消息卡片结构
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"enable_forward": True, "update_multi": True},
                "header": {
                    "template": theme_color,
                    "title": {"content": f"🚀 发现潜在金狗: ${symbol}", "tag": "plain_text"}
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {"is_short": True, "text": {"content": f"**📈 进度:**\n{progress}%", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**💰 市值:**\n{mcap}", "tag": "lark_md"}},
                            {"is_short": True,
                             "text": {"content": f"**👥 筹码占比:**\n前10持有 {holders_top10}%", "tag": "lark_md"}},
                            {"is_short": True,
                             "text": {"content": f"**👨‍💻 开发者:**\n已抛售 {dev_sell}%", "tag": "lark_md"}}
                        ]
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"content": f"**🐦 Grok (X) 深度透视 [{rating}级]:**\n{summary}", "tag": "lark_md"}
                    },
                    {
                        "tag": "note",
                        "elements": [{"content": f"合约地址: {ca}", "tag": "plain_text"}]
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"content": "📈 查看 K 线", "tag": "plain_text"},
                                "type": "primary",
                                "url": f"https://dexscreener.com/solana/{ca}"
                            },
                            {
                                "tag": "button",
                                "text": {"content": "🚀 极速买入", "tag": "plain_text"},
                                "type": "danger",
                                "url": f"https://photon-sol.tinyastro.io/en/lp/{ca}"
                            }
                        ]
                    }
                ]
            }
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logging.info(f"飞书消息推送成功: ${symbol}")
            return True
        except Exception as e:
            logging.error(f"飞书推送失败: {e}")
            return False


feishu_bot = FeishuBot()