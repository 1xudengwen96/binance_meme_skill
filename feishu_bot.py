import requests
import logging
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class FeishuBot:
    """
    封装飞书 Webhook 机器人功能
    重构版：移除多余的交易跳转，专注专业链上看盘与情报展示，带出完整的AI分析结果
    """

    def __init__(self):
        self.webhook_url = config.FEISHU_WEBHOOK_URL

    def format_and_send_alert(self, token_data: dict, grok_analysis: dict) -> bool:
        """
        组装飞书互动卡片：整合叙事、聪明钱情报与极速看盘链接，展示详细Grok摘要
        """
        if not self.webhook_url or "open-apis" not in self.webhook_url:
            logging.warning("飞书 Webhook 未配置，跳过推送。")
            return False

        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        chain_id = token_data.get("chainId", "CT_501")
        progress = token_data.get("progress", "Unknown")

        # 提取进阶情报
        context = token_data.get("context", {})
        narrative = context.get("narrative_hit")
        smart_money = context.get("smart_money_hit")
        inflow = context.get("inflow_amount", 0)

        # 市值美化
        mcap_raw = token_data.get("marketCap", "0")
        try:
            mcap = f"${float(mcap_raw):,.0f}"
        except:
            mcap = f"${mcap_raw}"

        rating = grok_analysis.get("rating", "Unknown")
        summary = grok_analysis.get("summary", "无分析摘要")

        # 动态组装看盘与浏览器地址
        if chain_id == "CT_501":  # Solana
            chart_url = f"https://dexscreener.com/solana/{ca}"
            explorer_url = f"https://solscan.io/token/{ca}"
        else:  # 默认兼容 BSC 等
            chart_url = f"https://dexscreener.com/bsc/{ca}"
            explorer_url = f"https://bscscan.com/token/{ca}"

        color_map = {"S": "red", "A": "orange", "B": "blue", "F": "grey"}
        theme_color = color_map.get(rating, "purple")

        # 构造情报文本
        tags = []
        if narrative: tags.append(f"🏷️ **热门叙事**: {narrative}")
        if smart_money: tags.append(f"🐳 **聪明钱**: 净流入 ${float(inflow):,.0f}")
        tag_content = "\n".join(tags) if tags else "🔹 **热度**: 普通市场波动"

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
                        "text": {"content": tag_content, "tag": "lark_md"}
                    },
                    {
                        "tag": "div",
                        "fields": [
                            {"is_short": True, "text": {"content": f"**📈 进度:**\n{progress}%", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**💰 市值:**\n{mcap}", "tag": "lark_md"}}
                        ]
                    },
                    {
                        "tag": "div",
                        # 在这里将 summary 拼接进去展示
                        "text": {"content": f"**🐦 Grok (X) 深度透视 [{rating}级]:**\n{summary}", "tag": "lark_md"}
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"content": f"**🎯 合约地址 (电脑端悬浮复制，手机端点击一键复制):**\n`{ca}`", "tag": "lark_md"}
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"content": "📈 查看 K 线 (DexScreener)", "tag": "plain_text"},
                                "type": "primary",
                                "url": chart_url
                            },
                            {
                                "tag": "button",
                                "text": {"content": "🔍 查看大户 (区块浏览器)", "tag": "plain_text"},
                                "type": "default",
                                "url": explorer_url
                            }
                        ]
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"content": "🛡️ 叙事对齐 & 聪明钱追踪 | 来源: Grok Sniper Engine", "tag": "plain_text"}]
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