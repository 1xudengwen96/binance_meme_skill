import requests
import json
import logging
import time
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GrokAPI:
    """
    对接 xAI Grok 的接口，专职负责 Meme 币的社交潜力与病毒式传播分析
    猎人实战版 V5：深度强化叙事套利、Ticker 审美、PvP 防身与资金效率感应
    """

    def __init__(self):
        self.api_key = config.GROK_API_KEY
        self.base_url = config.GROK_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def analyze_meme_potential(self, token: dict, max_retries=2) -> dict:
        """
        调用 Grok 分析代币的社交热度与病毒潜质
        返回格式: {"rating": "S/A/Neutral/F", "summary": "分析摘要"}
        """
        if not self.api_key or self.api_key.startswith("xai-your"):
            logging.warning("⚠️ GROK_API_KEY 未配置，跳过 AI 分析，默认返回 S 级(测试模式)")
            return {"rating": "S", "summary": "[测试模式] 默认放行"}

        symbol = token.get('symbol', 'Unknown')
        ca = token.get('contractAddress', 'Unknown')
        progress = token.get('progress', 0)

        # 获取由主引擎注入的上下文数据
        mcap = token.get('marketCap', 0)
        sm_count = token.get('smart_money_count', 0)
        sm_inflow = token.get('smart_money_inflow', 0.0)

        # [巅峰猎人 Prompt V5]
        prompt = f"""
        你现在是一名在全球 Web3 圈内享有盛誉的顶级 Meme 猎人（Degen Specialist）。
        你的任务是分析 Solana/BSC 链上的原生 Meme 代币：${symbol} 
        合约地址(CA): {ca}
        当前进度: {progress}%
        当前市值(MCAP): ${mcap}
        聪明钱追踪: {sm_count} 个精英地址已潜伏，净流入 ${sm_inflow}

        【深度分析维度】
        1. 病毒基因（Meme Lore）：代币概念是否具备“自传播”属性？Logo/名称是否属于目前流行的“抽象文化”、“动物叙事”或“极简主义”？
        2. Ticker 审美（Ticker Aesthetic）：代号 ${symbol} 是否简短（4字符以内最佳）、是否有力、是否容易在社交媒体（如 X）上被大量打出？
        3. 叙事地位（Narrative Status）：判断它是叙事开创者还是劣质仿盘（Copycat）。严厉打击“第N个龙”、“第N个松鼠”这类 PvP 垃圾。
        4. 资金/关注度错位（Attention Arbitrage）：结合 ${mcap} 市值和社交热度。如果市值极低但有聪明钱（{sm_count}人）持续买入，这是极其强烈的信号。
        5. 真实讨论度：区分“真实 Web3 玩家讨论”与“僵尸 Bot 刷屏”。

        【评级标准 - 猎人铁律】
        - S级（必打金狗）：Ticker 极佳，概念新颖。⚠️【特权】：若 ${symbol} 关联 24 小时内马斯克等大佬推特或全球突发事件（政治/科技），且 Ticker 具备唯一性，无视粉丝量直接评为 S 级。
        - A级（优质标的）：有热度，非仿盘，叙事对齐，且聪明钱 ({sm_count}人) 进场积极。
        - Neutral级（中立/发育期）：【防误杀】纯新币且暂无大规模讨论。只要 Ticker 顺口、非劣质仿盘，必须给 Neutral，给它发育时间。
        - F级（垃圾/割韭菜）：名字拼凑（如 PepeElonDoge）、全是僵尸号刷推、明显的短命 PvP 盘。

        【必须严格遵守的返回格式】
        你只能返回纯 JSON，不能有任何多余的解释。
        示例: {{"rating": "Neutral", "summary": "Ticker($ABC)简洁，概念属于XXX叙事，虽社交暂无讨论，但聪明钱已介入，建议观察。" }}
        """

        payload = {
            "model": config.GROK_MODEL,
            "messages": [
                {"role": "system",
                 "content": "You are a professional Web3 analyst. You output ONLY valid JSON. No markdown, no filler text."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,  # 降低随机性，使判断更稳定
            "max_tokens": 300
        }

        retries = 0
        while retries <= max_retries:
            try:
                logging.info(f"🧠 [Grok] 正在进行深度 Degen 体检: {symbol} (模型: {config.GROK_MODEL})")
                response = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload,
                                         timeout=20)

                if response.status_code != 200:
                    logging.warning(f"⚠️ [Grok] 请求被拒绝: HTTP {response.status_code}")

                response.raise_for_status()
                result_json = response.json()
                content = result_json['choices'][0]['message']['content'].strip()

                # 增强型 JSON 清洗逻辑
                if "{" in content and "}" in content:
                    content = content[content.find("{"):content.rfind("}") + 1]

                parsed_data = json.loads(content)

                rating = str(parsed_data.get("rating", "Neutral")).capitalize()
                if rating not in ["S", "A", "Neutral", "F"]:
                    rating = "Neutral"

                return {
                    "rating": rating,
                    "summary": parsed_data.get("summary", "无法获取 AI 分析摘要。")
                }

            except requests.exceptions.RequestException as e:
                logging.warning(f"⚠️ [Grok] API 网络故障: {e}")
                retries += 1
                time.sleep(2)
            except json.JSONDecodeError as e:
                logging.error(f"❌ [Grok] 解析失败: {e} | 内容: {content[:100]}...")
                return {"rating": "Neutral", "summary": "AI 返回格式异常，防误杀保护中。"}
            except Exception as e:
                logging.error(f"❌ [Grok] 未知错误: {e}")
                return {"rating": "Neutral", "summary": f"系统异常: {str(e)}"}

        return {"rating": "Neutral", "summary": "Grok 重试耗尽，默认进入中性观察池。"}


# 实例化单例
grok_api = GrokAPI()