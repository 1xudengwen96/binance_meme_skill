import requests
import json
import logging
import time
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GrokAPI:
    """
    对接 xAI Grok 的接口 —— 【金狗专属嗅探模式】
    彻底修复 mcap/inflow 的强制类型转换，确保日志与逻辑 100% 不因格式化崩溃
    """

    def __init__(self):
        self.api_key = config.GROK_API_KEY
        self.base_url = config.GROK_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def analyze_meme_potential(self, token: dict, max_retries=2) -> dict:
        if not self.api_key or self.api_key.startswith("xai-your"):
            return {"rating": "S", "summary": "[测试模式] 默认放行"}

        symbol = token.get('symbol', 'Unknown')
        ca = token.get('contractAddress', 'Unknown')

        # 【铁腕修复】：全字段强制数值化，绝不信任原始输入数据类型
        try:
            mcap = float(token.get('marketCap', 0))
        except:
            mcap = 0.0

        try:
            sm_count = int(token.get('smart_money_count', 0))
        except:
            sm_count = 0

        try:
            sm_inflow = float(token.get('smart_money_inflow', 0.0))
        except:
            sm_inflow = 0.0

        # 获取由 DexScreener 抓取的法证级社交证据包
        social_links = token.get('social_links', [])
        has_socials = token.get('has_socials', False)
        pair_age_minutes = token.get('pair_age_minutes', 0)
        social_status = "✅ 社交资产已就位" if has_socials else "❌ 暂无官方社交阵地"

        # 【金狗终极猎杀 Prompt V8】
        prompt = f"""
        你现在是一名全网最顶尖的 Web3 链上猎手。你的唯一目标是：在垃圾堆中寻找“百倍金狗”。

        【目标情报包】
        - 代币: ${symbol} ({ca})
        - 当前市值: ${mcap:,.0f}
        - 存活时长: {pair_age_minutes} 分钟
        - 社交状态: {social_status} ({', '.join(social_links)})
        - 聪明钱: {sm_count} 人进场，净流入 ${sm_inflow:,.0f}

        【金狗判定法则】
        1. 顶级叙事：去 X (Twitter) 检索。是否关联马斯克、Vitalik 或当前最火爆概念？无热度一律判定为 F。
        2. 聪明钱抱团：若市值 < $200k 且聪明钱 > 2 人，给出 S 级高度评价。
        3. 时空唯一：发币时间必须与叙事爆发点高度重合，滞后蹭热度的一律给 F。

        【打分标准】
        - S级 (超级金狗)：顶级叙事 + 极早期 + 聪明钱抱团抢筹。
        - A级 (优质强庄)：叙事真实，社交活跃，资金稳步流入。
        - Neutral (平庸土狗)：平庸就是罪！没爆发力的通通给 Neutral。
        - F级 (拦截)：垃圾盘、碰瓷盘、收割局。

        【必须返回纯 JSON】
        {{ "rating": "评级", "summary": "依据事实的极简摘要" }}
        """

        payload = {
            "model": config.GROK_MODEL,
            "messages": [
                {"role": "system", "content": "You are a professional Web3 analyst. Output ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 300
        }

        retries = 0
        while retries <= max_retries:
            try:
                # 这里的格式化已通过上面的 float 转换获得 100% 保障
                logging.info(f"🧠 [Grok 金狗审计] {symbol} | 市值: ${mcap:,.0f} | 聪明钱: {sm_count}人")

                response = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload,
                                         timeout=20)
                response.raise_for_status()

                content = response.json()['choices'][0]['message']['content'].strip()
                if "{" in content and "}" in content:
                    content = content[content.find("{"):content.rfind("}") + 1]

                parsed_data = json.loads(content)
                rating = str(parsed_data.get("rating", "Neutral")).capitalize()

                if rating not in ["S", "A", "Neutral", "F"]:
                    rating = "Neutral"

                return {
                    "rating": rating,
                    "summary": parsed_data.get("summary", "无法获取 AI 摘要。")
                }

            except Exception as e:
                logging.warning(f"⚠️ [Grok] 请求异常 (重试 {retries + 1}): {e}")
                retries += 1
                time.sleep(2)

        return {"rating": "Neutral", "summary": "AI 网络异常，默认不买入。"}


grok_api = GrokAPI()