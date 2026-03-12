import requests
import logging
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class FeishuBot:
    """
    封装飞书 Webhook 机器人功能
    升级版：完美解决手机端 CA 复制干扰问题，并新增法证级(存活时间/社交阵地)情报展示
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

        # 提取进阶情报 (聪明钱与热度)
        context = token_data.get("context", {})
        narrative = context.get("narrative_hit")
        smart_money = context.get("smart_money_hit")
        inflow = context.get("inflow_amount", 0)

        # 提取法证级情报 (存活时间与社交链接)
        pair_age = token_data.get("pair_age_minutes", "未知")
        has_socials = token_data.get("has_socials", False)
        social_status = "✅ 官推/TG已挂载" if has_socials else "❌ 暂无社交链接"

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

        color_map = {"S": "red", "A": "orange", "Neutral": "blue", "F": "grey"}
        theme_color = color_map.get(rating, "purple")

        # 构造情报文本
        tags = []
        if narrative: tags.append(f"🏷️ **热门叙事**: {narrative}")
        if smart_money: tags.append(f"🐳 **聪明钱**: 净流入 ${float(inflow):,.0f}")
        tag_content = "\n".join(tags) if tags else "🔹 **热度**: 早期埋伏/未检测到大规模异动"

        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"enable_forward": True, "update_multi": True},
                "header": {
                    "template": theme_color,
                    "title": {"content": f"🚀 发现潜力猎物: ${symbol}", "tag": "plain_text"}
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
                            {"is_short": True, "text": {"content": f"**💰 市值:**\n{mcap}", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**⏱️ 存活时间:**\n{pair_age} 分钟", "tag": "lark_md"}},
                            {"is_short": True, "text": {"content": f"**🌐 社交阵地:**\n{social_status}", "tag": "lark_md"}}
                        ]
                    },
                    {
                        "tag": "div",
                        "text": {"content": f"**🧠 预期差分析 [{rating}级]:**\n{summary}", "tag": "lark_md"}
                    },
                    {"tag": "hr"},
                    {
                        "tag": "div",
                        "text": {"content": "**🎯 合约地址 (手机端长按下方区域即可纯净复制):**", "tag": "lark_md"}
                    },
                    # 【核心修复】：剥离出独立的纯文本块，彻底解决手机端附带多余字符和引号的问题
                    {
                        "tag": "div",
                        "text": {"content": ca, "tag": "plain_text"}
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
                            {"content": "🛡️ 叙事法证与预期差追踪 | 来源: Sniper Engine V5", "tag": "plain_text"}
                        ]
                    }
                ]
            }
        }

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logging.info(f"✅ 飞书消息推送成功: ${symbol}")
            return True
        except Exception as e:
            logging.error(f"❌ 飞书推送失败: {e}")
            return False

feishu_bot = FeishuBot()