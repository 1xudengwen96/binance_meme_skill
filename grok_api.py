import requests
import json
import logging
import time
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GrokAPI:
    """
    对接 xAI Grok 的接口，采用【法证级叙事审计】与【注意力套利】模型
    不再做文学创作，只做基于证据链的预期差分析
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

        # 基础数据
        mcap = token.get('marketCap', 0)
        sm_count = token.get('smart_money_count', 0)
        sm_inflow = token.get('smart_money_inflow', 0.0)

        # 核心：注入由 DexScreener 抓取的法证级社交证据包
        social_links = token.get('social_links', [])
        has_socials = token.get('has_socials', False)
        pair_age_minutes = token.get('pair_age_minutes', 0)
        social_status = "社交资产已就位(有推特/TG等)" if has_socials else "暂无官方社交阵地链接"

        # [法证级套利 Prompt V6]
        prompt = f"""
        你现在是一名理性的 Web3 Degen 观察员与链上法证分析师。
        你的任务是基于以下“铁证”，评估代币 ${symbol} 的“注意力预期差”，严禁任何文学修辞和“建议观察”等废话。

        【证据链清单】
        - 代币(Ticker / CA): ${symbol} / {ca}
        - 当前市值(MCAP): ${mcap}
        - 存活时长: {pair_age_minutes} 分钟
        - 社交阵地状态: {social_status} ({', '.join(social_links)})
        - 聪明钱追踪: {sm_count} 人进场，净流入 ${sm_inflow}

        【强制分析逻辑：注意力套利模型】
        1. 搜寻 X (Twitter) 实时热度：去核实该 CA 或 Ticker 的真实讨论量。是否是机器号在刷屏？
        2. 时空对齐核验：如果 Ticker 是马斯克刚发的词汇（如某政治/科技事件），核对【存活时长】是否属于第一批响应的龙头。如果叙事发生了很久但它是新币，判定为碰瓷盘。
        3. 市值/热度预期差：
           - 巨大预期差：全网开始热议/大佬转推，但 MCAP 极低 (低于 $500k)，这是黄金位。
           - 早期潜伏位：存活时间极短 (< 120 分钟)，社交阵地刚建立，虽然 X 上没人聊，但聪明钱在进，这属于健康发育。

        【打分标准 - 必须严格执行】
        - S级 (金狗)：叙事时机完美对齐 + 巨大预期差(热度远超市值) + 聪明钱密集入场。
        - A级 (优质)：热度与市值同步健康上升，有真实的社交基础，非劣质仿盘。
        - Neutral (中性/发育期)：【防误杀保护】链上资金在动(聪明钱>0或进度快)，且社交资产齐全，但 X 上暂无巨大热度。必须给 Neutral，这代表正常的早期埋伏盘。
        - F级 (拦截)：时空碰瓷（热点早过了才发币）、全是低级 Bot 刷屏、明显的割韭菜局。

        【必须严格遵守的返回格式】
        只返回纯 JSON。摘要中必须明确说明你的事实依据（如：热度与市值是否匹配、是否跨时空）。
        示例: {{"rating": "Neutral", "summary": "存活仅30分钟，官推已就位。虽X上暂无广泛讨论，但市值仅3万刀且有聪明钱试水，属于正常极早期阶段，未见碰瓷痕迹。" }}
        """

        payload = {
            "model": config.GROK_MODEL,
            "messages": [
                {"role": "system", "content": "You are a professional Web3 analyst. Output ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,  # 极低温度，保证理性
            "max_tokens": 300
        }

        retries = 0
        while retries <= max_retries:
            try:
                logging.info(
                    f"🧠 [Grok] 正在执行法证级预期差计算: {symbol} (MCAP: ${mcap:,.0f} | 存活: {pair_age_minutes}分钟)")
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
                logging.warning(f"⚠️ [Grok] 请求异常: {e}")
                retries += 1
                time.sleep(2)

        return {"rating": "Neutral", "summary": "AI 网络异常，基于链上数据默认放行进入观察池。"}


grok_api = GrokAPI()